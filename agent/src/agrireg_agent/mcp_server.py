from __future__ import annotations

from argparse import ArgumentParser
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import StringConstraints

from .clients import ControlledTools
from .config import Settings, get_settings
from .documents import DocumentHit, DocumentSearchRequest


Entity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def create_mcp_server(settings: Settings, *, port: int = 8092) -> FastMCP:
    server = FastMCP("AgriReg AI", host="127.0.0.1", port=port, stateless_http=True, json_response=True)
    tools = ControlledTools(settings)

    @server.tool()
    def search_entity(keyword: Entity) -> dict[str, Any]:
        """Search the bounded Neo4j entity neighborhood by keyword or alias."""
        return tools.search_entity(keyword)

    @server.tool()
    def find_relation_path(source: Entity, target: Entity) -> dict[str, Any]:
        """Find a bounded relation path between two named entities."""
        return tools.find_relation_path(source, target)

    @server.tool()
    def search_documents(request: DocumentSearchRequest) -> list[DocumentHit]:
        """Search indexed registration documents and return passages with source locators."""
        if tools.documents is None:
            raise ToolError("Registration document search is not configured.")
        return tools.documents.search(request)

    return server


def main() -> None:
    parser = ArgumentParser(description="AgriReg read-only MCP search tools")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--port", type=int, default=8092)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535.")
    create_mcp_server(get_settings(), port=args.port).run(transport=args.transport)


if __name__ == "__main__":
    main()
