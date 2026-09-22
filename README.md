# jev-mcp

MCP server for [TypeSafe Jev](https://docs.typesafe.ai) (System One): one tool,
`evaluate`, whose input is the exact body of `POST /v1/systemone` and whose
output is the exact response. Streamable HTTP transport, built on fastmcp 3.

Why one tool: every Jev client in this lab (Claude Code's `jev.py`, the Hermes
skill, this server) then asks Jev with the same contract, so questions and
results move between them unchanged.

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `JEV_API_KEY` / `JEV_API_KEY_FILE` | TypeSafe key (file wins; contents stripped) | required |
| `JEV_MCP_PATH_SECRET` / `..._FILE` | random path segment; endpoint becomes `/<secret>/mcp` | none → `/mcp` with a warning |
| `JEV_API_URL` | TypeSafe endpoint | `https://api.typesafe.ai/v1/systemone` |
| `JEV_MODEL` | default model | `jev-latest` |
| `JEV_MCP_HOST` / `JEV_MCP_PORT` | bind address | `0.0.0.0` / `8080` |
| `JEV_MCP_TIMEOUT` | seconds per TypeSafe call | `60` |

`GET /healthz` returns `ok` for probes. Any path other than the MCP path and
`/healthz` is 404.

The server does not authenticate callers. When it is reachable from the
internet the path secret is the credential: whoever has the full URL can spend
the key's Jev credits (and nothing else, the process holds no other access).
Treat the URL like a key.

## Run locally

    uv venv && uv pip install -e '.[dev]'
    JEV_API_KEY_FILE=~/Developer/keys/jev/claude.key JEV_MCP_PATH_SECRET=$(openssl rand -hex 24) .venv/bin/jev-mcp
    .venv/bin/pytest

## Image

Built in-cluster with the `lab-image-build` skill (kaniko → Harbor), base
`registry.suse.com/bci/python:3.13`, runs as uid 10001:

    ~/.claude/skills/lab-image-build/scripts/kaniko-build.sh \
      --repo darthzen/jev-mcp --image jev-mcp --tag 0.1.0

Deployment lives in `lab-fleet/09-mcp/jev/` (Deployment, Service, Ingress on
`jev-mcp.ash4d.com`, exposed through the Cloudflare tunnel).

## Clients

    # Claude Code
    claude mcp add --transport http --scope user jev https://jev-mcp.ash4d.com/<secret>/mcp
    # claude.ai / Claude Desktop: Settings → Connectors → Add custom connector → that URL, no OAuth
    # Claude Desktop fallback if the connector flow insists on OAuth:
    "jev": { "command": "npx", "args": ["-y", "mcp-remote", "https://jev-mcp.ash4d.com/<secret>/mcp"] }
