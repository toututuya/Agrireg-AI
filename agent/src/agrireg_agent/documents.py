from __future__ import annotations

import hashlib
import json
import unicodedata
from argparse import ArgumentParser
from collections.abc import Iterator
from functools import lru_cache
from itertools import count, islice
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, StringConstraints, ValidationError, field_validator, model_validator

from .config import Settings, get_settings

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[Text, StringConstraints(max_length=128)]
SearchMode = Literal["dense", "bm25", "hybrid", "reranked"]
CANDIDATES = 32
CHUNK_LENGTH = 360
CHUNK_OVERLAP = 48
DENSE_DIM = 1024
_model_lock = Lock()


def _normalize_registration(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFKC", value).strip().upper()
    return value


class DocumentSource(BaseModel):
    document_id: Identifier
    version: Identifier
    title: Annotated[Text, StringConstraints(max_length=256)]
    source_url: HttpUrl
    page: int | None = Field(default=None, ge=1, le=2_147_483_647)
    section: str = Field(default="", max_length=256)
    registration_number: str = Field(default="", max_length=64)

    normalize_registration = field_validator("registration_number", mode="before")(_normalize_registration)

    @field_validator("section", mode="before")
    @classmethod
    def normalize_section(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_locator(self) -> DocumentSource:
        if self.page is None and not self.section:
            raise ValueError("登记文档须提供页码或章节。")
        return self


class SourcePage(DocumentSource):
    text: Text


class DocumentChunk(DocumentSource):
    chunk_id: str
    text: Text


class DocumentSearchRequest(BaseModel):
    query: Annotated[Text, StringConstraints(max_length=512)]
    registration_number: str = Field(default="", max_length=64)
    limit: int = Field(default=5, ge=1, le=10)
    mode: SearchMode = "reranked"

    normalize_registration = field_validator("registration_number", mode="before")(_normalize_registration)


class DocumentHit(DocumentChunk):
    score: float


def read_pages(path: Path) -> Iterator[SourcePage]:
    seen: set[tuple[str, str, int | None, str]] = set()
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                page = SourcePage.model_validate_json(line)
            except ValidationError as exc:
                raise ValueError(f"{path.name} 第 {line_number} 行无效：{exc}") from exc
            key = (page.document_id, page.version, page.page, page.section)
            if key in seen:
                raise ValueError(f"{path.name} 第 {line_number} 行的文档定位重复。")
            seen.add(key)
            yield page


def chunk_page(page: SourcePage) -> Iterator[DocumentChunk]:
    metadata = page.model_dump(exclude={"text"})
    start = 0
    for index in count():
        end = min(start + CHUNK_LENGTH, len(page.text))
        if end < len(page.text):
            earliest = start + CHUNK_LENGTH * 2 // 3
            boundary = max(page.text.rfind(mark, earliest, end) for mark in "\n。！？；")
            if boundary >= earliest:
                end = boundary + 1
        text = page.text[start:end].strip()
        if text:
            locator = (page.document_id, page.version, page.page, page.section, index)
            chunk_id = hashlib.sha256(json.dumps(locator, ensure_ascii=False).encode("utf-8")).hexdigest()
            yield DocumentChunk(chunk_id=chunk_id, text=text, **metadata)
        if end >= len(page.text):
            break
        start = end - CHUNK_OVERLAP


class MilvusDocumentSearch:
    """Versioned document indexing and retrieval through a single Milvus collection."""

    OUTPUT_FIELDS = tuple(DocumentChunk.model_fields)

    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings
        self.collection = settings.milvus_collection
        self.timeout = settings.request_timeout_seconds

    def encode(self, texts: list[str]):
        with _model_lock:
            model = _embedding(self.settings.embedding_model, self.settings.retrieval_device)
        return model.encode(texts, normalize_embeddings=True)

    def prepare_collection(self) -> None:
        from pymilvus import DataType, Function, FunctionType, MilvusClient

        if self.client.has_collection(self.collection, timeout=self.timeout):
            self.client.load_collection(self.collection, timeout=self.timeout)
            return
        schema = MilvusClient.create_schema(auto_id=False)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64, is_primary=True)
        for name, max_bytes in (
            ("document_id", 512), ("version", 512), ("title", 1024),
            ("source_url", 4096), ("section", 1024), ("registration_number", 256),
        ):
            schema.add_field(name, DataType.VARCHAR, max_length=max_bytes)
        schema.add_field("page", DataType.INT32)
        schema.add_field(
            "text", DataType.VARCHAR, max_length=CHUNK_LENGTH * 4,
            enable_analyzer=True, analyzer_params={"type": "chinese"},
        )
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DENSE_DIM)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(Function(
            name="text_bm25", function_type=FunctionType.BM25,
            input_field_names=["text"], output_field_names=["sparse"],
        ))
        indexes = self.client.prepare_index_params()
        indexes.add_index(field_name="dense", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
        self.client.create_collection(
            collection_name=self.collection, schema=schema, index_params=indexes,
            consistency_level="Bounded", timeout=self.timeout,
        )

    def ingest(self, chunks: Iterator[DocumentChunk]) -> int:
        self.prepare_collection()
        total = 0
        while batch := list(islice(chunks, 32)):
            vectors = self.encode([chunk.text for chunk in batch])
            rows = []
            for chunk, vector in zip(batch, vectors, strict=True):
                row = chunk.model_dump(mode="json")
                row["page"] = chunk.page or 0
                row["dense"] = vector.tolist()
                rows.append(row)
            self.client.upsert(self.collection, rows, timeout=self.timeout)
            total += len(rows)
        if total:
            self.client.flush(self.collection, timeout=self.timeout)
        return total

    def search(self, request: DocumentSearchRequest) -> list[DocumentHit]:
        from pymilvus import AnnSearchRequest, RRFRanker

        query = request.query
        mode = request.mode
        if request.registration_number:
            expr = "registration_number == " + json.dumps(request.registration_number, ensure_ascii=False)
        else:
            expr = ""
        limit = CANDIDATES if mode == "reranked" else request.limit
        calls = []
        if mode != "bm25":
            dense = self.encode([query])[0].tolist()
            calls.append(("dense", [dense], {"metric_type": "COSINE"}))
        if mode != "dense":
            calls.append(("sparse", [query], {"metric_type": "BM25"}))
        common = {
            "collection_name": self.collection,
            "output_fields": list(self.OUTPUT_FIELDS),
            "limit": limit,
            "timeout": self.timeout,
        }
        if len(calls) == 1:
            field, data, params = calls[0]
            result = self.client.search(
                data=data, anns_field=field, search_params=params, filter=expr, **common,
            )
        else:
            result = self.client.hybrid_search(
                reqs=[AnnSearchRequest(data, field, params, CANDIDATES, expr=expr) for field, data, params in calls],
                ranker=RRFRanker(), **common,
            )
        hits = [
            DocumentHit.model_validate({
                **hit["entity"],
                "chunk_id": hit["entity"].get("chunk_id", hit.get("id")),
                "page": hit["entity"]["page"] or None,
                "score": hit["distance"],
            })
            for hit in (result[0] if result else [])
        ]
        if mode == "reranked" and hits:
            with _model_lock:
                reranker = _reranker(self.settings.reranker_model, self.settings.retrieval_device)
            scores = reranker.predict([(query, hit.text) for hit in hits])
            hits = [hit.model_copy(update={"score": float(score)}) for hit, score in zip(hits, scores, strict=True)]
            hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:request.limit]


@lru_cache(maxsize=1)
def _embedding(model: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model, device=device or None)


@lru_cache(maxsize=1)
def _reranker(model: str, device: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model, device=device or None, max_length=512)


def build_document_search(settings: Settings) -> MilvusDocumentSearch | None:
    if not settings.milvus_uri:
        return None
    from pymilvus import MilvusClient

    client = MilvusClient(
        uri=settings.milvus_uri,
        token=settings.milvus_token.get_secret_value(),
        timeout=settings.request_timeout_seconds,
    )
    return MilvusDocumentSearch(client, settings)


@lru_cache(maxsize=1)
def get_document_search() -> MilvusDocumentSearch | None:
    return build_document_search(get_settings())


def main() -> None:
    parser = ArgumentParser(description="登记文档入库与检索")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("jsonl", type=Path)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--registration-number", default="")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--mode", choices=("dense", "bm25", "hybrid", "reranked"), default="reranked")
    args = parser.parse_args()

    documents = get_document_search()
    if documents is None:
        parser.error("请配置 AGENT_MILVUS_URI。")
    if args.command == "ingest":
        pages = list(read_pages(args.jsonl))
        if not pages:
            parser.error("输入文件没有文档记录。")
        chunks = (chunk for page in pages for chunk in chunk_page(page))
        print(json.dumps({"chunks": documents.ingest(chunks)}))
    else:
        request = DocumentSearchRequest(
            query=args.query, registration_number=args.registration_number, limit=args.limit, mode=args.mode,
        )
        hits = [hit.model_dump(mode="json") for hit in documents.search(request)]
        print(json.dumps(hits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
