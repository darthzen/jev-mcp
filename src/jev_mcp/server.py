"""MCP server for TypeSafe Jev (System One).

One tool, `evaluate`, that takes the exact body of POST /v1/systemone and
returns the exact response. Same contract as the jev.py helpers used from
Claude Code and Hermes, so every client asks Jev the same way.

Configuration (environment):
  JEV_API_KEY / JEV_API_KEY_FILE            TypeSafe key (file wins if both set)
  JEV_MCP_PATH_SECRET / _FILE               random segment; the MCP endpoint is
                                            /<secret>/mcp. Unset -> /mcp, with a
                                            warning: the URL is then not a
                                            credential.
  JEV_API_URL       default https://api.typesafe.ai/v1/systemone
  JEV_MODEL         default jev-latest
  JEV_MCP_HOST      default 0.0.0.0
  JEV_MCP_PORT      default 8080
  JEV_MCP_TIMEOUT   seconds per TypeSafe call, default 60
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from jev_mcp import __version__

log = logging.getLogger("jev_mcp")

API_URL = os.environ.get("JEV_API_URL", "https://api.typesafe.ai/v1/systemone")
DEFAULT_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
TIMEOUT = float(os.environ.get("JEV_MCP_TIMEOUT", "60"))

INSTRUCTIONS = """Jev (TypeSafe System One) returns typed judgments with calibrated
probabilities instead of prose. Use `evaluate` before any decision: choosing between
options, classifying, ranking, or judging whether a condition holds. Put the evidence
in `state` as named fields, the judgment in each question's `instructions`, and the
possible answers in `criteria`. Read the probabilities: act on a choice when it is
clearly ahead; when the distribution is flat, say so and gather more evidence."""


def _from_env_or_file(env_name: str) -> str:
    """Return a setting from <env_name>_FILE (stripped file contents) or <env_name>."""
    path = os.environ.get(f"{env_name}_FILE")
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get(env_name, "").strip()


def _api_key() -> str:
    key = _from_env_or_file("JEV_API_KEY")
    if not key:
        raise RuntimeError("JEV_API_KEY or JEV_API_KEY_FILE must be set")
    return key


mcp = FastMCP("jev", instructions=INSTRUCTIONS, version=__version__)


@mcp.tool(
    name="evaluate",
    description=(
        "Ask Jev (TypeSafe System One) for typed judgments. Body mirrors POST "
        "/v1/systemone exactly. `state` is the evidence (a JSON object with named "
        "fields, or text). `questions` maps an id to {type, instructions, criteria}: "
        "type 'choice' picks one key of `criteria` (map option -> description) and "
        "returns choice, confidence, probabilities; type 'noul' has no criteria and "
        "returns noul = probability the condition holds; type 'score' places state on "
        "an ordered scale whose levels are the items of `criteria` -- for 'score' this "
        "is an ordered LIST, not a map (2-10 levels, each a concrete description; a "
        "level's number is its position in the list, starting at 0) -- and returns "
        "score, confidence, probabilities. Note the asymmetry: 'choice' criteria is a "
        "map, 'score' criteria is a list; sending a map for 'score' is rejected 422. "
        "Reference "
        "state fields in instructions with backticks, e.g. `pod_state`. Include a "
        "none_of_these / other option when nothing may fit. Independent questions in "
        "one call run in parallel."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
)
async def evaluate(
    state: dict[str, Any] | list[Any] | str,
    questions: dict[str, dict[str, Any]],
    model: str | None = None,
) -> dict[str, Any]:
    """Call TypeSafe and return its response unchanged."""
    if not questions:
        raise ToolError("questions must contain at least one question")
    body = {"state": state, "questions": questions, "model": model or DEFAULT_MODEL}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                API_URL,
                json=body,
                headers={"Authorization": f"Bearer {_api_key()}"},
            )
    except httpx.HTTPError as e:
        raise ToolError(f"TypeSafe unreachable: {e.__class__.__name__}: {e}") from e
    if r.status_code >= 400:
        raise ToolError(f"TypeSafe HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def mcp_path() -> str:
    secret = _from_env_or_file("JEV_MCP_PATH_SECRET")
    if not secret:
        log.warning("JEV_MCP_PATH_SECRET is unset; serving on /mcp with no URL secret")
        return "/mcp"
    if "/" in secret or len(secret) < 16:
        raise RuntimeError("JEV_MCP_PATH_SECRET must be a single path segment of 16+ chars")
    return f"/{secret}/mcp"


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("JEV_MCP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    _api_key()  # fail fast at startup, before anything is listening
    host = os.environ.get("JEV_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("JEV_MCP_PORT", "8080"))
    path = mcp_path()
    shown = path if path == "/mcp" else "/<secret>/mcp"
    log.info("jev-mcp %s serving on %s:%s path=%s api=%s", __version__, host, port, shown, API_URL)
    mcp.run(
        transport="http",
        host=host,
        port=port,
        path=path,
        stateless_http=True,
        # Behind Cloudflare -> cloudflared -> Traefik the Host header is the
        # public name; DNS-rebinding protection would reject it.
        allowed_hosts=["*"],
        show_banner=False,
        # The request path carries the URL secret; keep it out of pod logs.
        uvicorn_config={"access_log": False},
    )


if __name__ == "__main__":
    main()
