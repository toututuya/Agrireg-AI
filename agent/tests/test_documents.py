import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from agrireg_agent.api import app
from agrireg_agent.config import Settings
from agrireg_agent.documents import (
    DocumentSearchRequest,
    MilvusDocumentSearch,
    SourcePage,
    chunk_page,
    get_document_search,
    read_pages,
)


def source_page(**changes):
    data = {
        "document_id": "sample",
        "version": "v1",
        "title": "合成登记示例",
        "source_url": "https://example.org/sample",
        "page": 2,
        "section": "登记状态",
        "registration_number": " ｐｄＡ００１ ",
        "text": "本段为检索样例。有关登记信息见附录。" * 40,
    }
    return SourcePage(**(data | changes))


def test_chunks_preserve_provenance_and_version():
    page = source_page()
    chunks = list(chunk_page(page))
    assert len(chunks) > 1
    assert chunks == list(chunk_page(page))
    assert all(chunk.page == 2 and chunk.registration_number == "PDA001" for chunk in chunks)
    assert str(chunks[0].source_url) == "https://example.org/sample"
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert chunks[0].chunk_id != next(chunk_page(source_page(version="v2"))).chunk_id
    assert all(len(chunk.text) <= 360 for chunk in chunks)


def test_jsonl_rejects_repeated_locator(tmp_path):
    document = source_page().model_dump_json()
    path = tmp_path / "pages.jsonl"
    path.write_text(f"{document}\n{document}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="第 2 行的文档定位重复"):
        list(read_pages(path))


def test_hybrid_filters_both_legs_and_predicts_only_on_candidates(monkeypatch):
    import agrireg_agent.documents as documents

    ann_request = Mock(side_effect=lambda data, field, params, limit, **kwargs: (field, data, kwargs["expr"]))
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(AnnSearchRequest=ann_request, RRFRanker=Mock()))
    texts = ["历史登记条目", "当前登记条目"]
    chunks = [next(chunk_page(source_page(page=i + 1, text=text))) for i, text in enumerate(texts)]
    client = Mock()
    client.hybrid_search.return_value = [[
        {"entity": chunk.model_dump(mode="json"), "distance": 0.03 - i / 100}
        for i, chunk in enumerate(chunks)
    ]]
    model = Mock()
    model.predict.return_value = [0.2, 0.7]
    monkeypatch.setattr(documents, "_reranker", lambda *_: model)
    service = MilvusDocumentSearch(client, Settings(AGENT_MILVUS_COLLECTION="registration_docs"))
    service.encode = Mock(return_value=[Mock(tolist=lambda: [0.2])])
    request = DocumentSearchRequest(query=" 哪一条仍有效？ ", registration_number="ｐｄａ００１", limit=1)

    response = service.search(request)

    assert [hit.text for hit in response] == ["当前登记条目"]
    assert response[0].page == 2
    assert client.hybrid_search.call_args.kwargs["reqs"] == [
        ("dense", [[0.2]], 'registration_number == "PDA001"'),
        ("sparse", ["哪一条仍有效？"], 'registration_number == "PDA001"'),
    ]
    model.predict.assert_called_once_with([("哪一条仍有效？", text) for text in texts])


def test_bm25_does_not_load_embedding_or_reranker(monkeypatch):
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(AnnSearchRequest=Mock(), RRFRanker=Mock()))
    client = Mock()
    client.search.return_value = [[]]
    service = MilvusDocumentSearch(client, Settings(AGENT_MILVUS_COLLECTION="registration_docs"))
    service.encode = Mock()

    assert service.search(DocumentSearchRequest(query="测试", mode="bm25")) == []
    assert client.search.call_args.kwargs["anns_field"] == "sparse"
    assert client.search.call_args.kwargs["data"] == ["测试"]
    service.encode.assert_not_called()


def test_default_api_reports_disabled_and_rejects_bad_input():
    app.dependency_overrides[get_document_search] = lambda: None
    try:
        with TestClient(app) as client:
            assert client.post("/api/agent/documents/search", json={"query": "登记"}).status_code == 503
            assert client.post("/api/agent/documents/search", json={"query": " "}).status_code == 422
    finally:
        del app.dependency_overrides[get_document_search]


def test_real_milvus_lite_ingestion_and_chinese_bm25(tmp_path):
    pymilvus = pytest.importorskip("pymilvus")
    pytest.importorskip("milvus_lite")
    pytest.importorskip("jieba")
    client = pymilvus.MilvusClient(str(tmp_path / "docs.db"))
    service = MilvusDocumentSearch(client, Settings(AGENT_MILVUS_COLLECTION="test_documents"))
    service.encode = Mock(side_effect=lambda texts: [Mock(tolist=lambda: [1.0] + [0.0] * 1023) for _ in texts])
    chunks = [
        next(chunk_page(source_page(document_id="rice", text="水稻登记条目。水稻样例。"))),
        next(chunk_page(source_page(document_id="apple", text="苹果登记条目。苹果样例。", registration_number="PDA002"))),
    ]
    try:
        assert service.ingest(iter(chunks)) == 2
        assert service.ingest(iter(chunks)) == 2
        client.release_collection("test_documents")
        service = MilvusDocumentSearch(client, Settings(AGENT_MILVUS_COLLECTION="test_documents"))
        request = DocumentSearchRequest(query="水稻", registration_number="PDA001", mode="bm25")
        hits = service.search(request)
        assert [(hit.document_id, hit.page) for hit in hits] == [("rice", 2)]
        assert service.search(request.model_copy(update={"registration_number": "PDA999"})) == []
    finally:
        client.close()
