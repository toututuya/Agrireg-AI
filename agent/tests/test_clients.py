import httpx

from agrireg_agent.clients import ControlledTools
from agrireg_agent.config import Settings


def test_controlled_tools_normalize_graph_and_external_evidence(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "127.0.0.1":
            return httpx.Response(
                200,
                json={
                    "found": True,
                    "nodes": [
                        {
                            "id": 7,
                            "name": "Abamectin",
                            "label": "ActiveSubstance",
                            "properties": {"CAS registry number": "71751-41-2"},
                            "evidence": {"dataset": "GDP-KG", "jurisdiction": "Global"},
                        }
                    ],
                    "edges": [],
                },
            )
        return httpx.Response(
            200,
            json={
                "PropertyTable": {
                    "Properties": [
                        {"CID": 9920327, "Title": "Abamectin", "MolecularFormula": "C95H142O28"}
                    ]
                }
            },
        )

    settings = Settings(AGENT_DATA_DIR=tmp_path, AGENT_GRAPH_API_BASE_URL="http://127.0.0.1:4399")
    tools = ControlledTools(settings, transport=httpx.MockTransport(handler))

    graph = tools.search_entity("Abamectin")
    external = tools.external_substance_lookup("Abamectin")

    assert graph["evidence"][0]["source"] == "GDP-KG"
    assert graph["evidence"][0]["properties"]["CAS registry number"] == "71751-41-2"
    assert external["evidence"][0]["source"] == "PubChem"
    assert external["evidence"][0]["url"].endswith("/9920327")

