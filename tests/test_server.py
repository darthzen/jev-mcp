import json

import httpx
import pytest
import respx
from fastmcp import Client

from jev_mcp import server


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.delenv("JEV_API_KEY_FILE", raising=False)


async def test_evaluate_passes_body_through_and_returns_response():
    answers = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 0.8}}}
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(server.API_URL).mock(return_value=httpx.Response(200, json=answers))
        async with Client(server.mcp) as client:
            result = await client.call_tool(
                "evaluate",
                {"state": {"x": 1}, "questions": {"q": {"type": "noul", "instructions": "x==1?"}}},
            )
    sent = json.loads(route.calls[0].request.content)
    assert sent == {
        "state": {"x": 1},
        "questions": {"q": {"type": "noul", "instructions": "x==1?"}},
        "model": server.DEFAULT_MODEL,
    }
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"
    assert result.data == answers


async def test_upstream_error_becomes_tool_error():
    with respx.mock() as mock:
        mock.post(server.API_URL).mock(return_value=httpx.Response(401, text="bad key"))
        async with Client(server.mcp) as client:
            with pytest.raises(Exception, match="TypeSafe HTTP 401"):
                await client.call_tool(
                    "evaluate",
                    {"state": "s", "questions": {"q": {"type": "noul", "instructions": "?"}}},
                )


def test_key_file_wins_and_is_stripped(tmp_path, monkeypatch):
    p = tmp_path / "key"
    p.write_text("from-file\n")
    monkeypatch.setenv("JEV_API_KEY_FILE", str(p))
    assert server._api_key() == "from-file"


def test_mcp_path_requires_secret_shape(monkeypatch):
    monkeypatch.delenv("JEV_MCP_PATH_SECRET_FILE", raising=False)
    monkeypatch.setenv("JEV_MCP_PATH_SECRET", "")
    assert server.mcp_path() == "/mcp"
    monkeypatch.setenv("JEV_MCP_PATH_SECRET", "a" * 24)
    assert server.mcp_path() == "/" + "a" * 24 + "/mcp"
    monkeypatch.setenv("JEV_MCP_PATH_SECRET", "short")
    with pytest.raises(RuntimeError):
        server.mcp_path()
