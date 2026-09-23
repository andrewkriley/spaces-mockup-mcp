# spaces-ghost-mcp

Read-only MCP that answers **Webex Workspaces** and **Cisco Spaces Firehose** questions from a synthetic **Ghost Campus** dataset. Clients query it as if a live Control Hub org and Firehose pull channel were connected.

It does **not** wrap `https://mcp.webexapis.com` and it does **not** open a Cisco Spaces partner stream. Identities are `@ghost.example` only. No Cisco API keys.

Python 3.12+, standard library only. Dev tools (Ruff) live in a local `.venv`. Runs on a workstation (stdio or loopback HTTP). Not a Kubernetes service.

## Tools

Sixteen Workspaces names plus three Firehose pulls. All reads.

| Group | Tools |
| --- | --- |
| Locations | `location_search` |
| Workspaces | `workspace_search`, `workspace_metrics`, `workspace_aggregated_usage_metrics`, `workspace_aggregated_capacity_utilization`, `workspace_aggregated_popularity_metrics` |
| Devices | `device_search`, `device_event_history`, `device_aggregated_event_history`, `device_error_code_detail_search`, `product_lifecycle`, `device_configuration_list`, `device_configuration_schema`, `device_configuration_diff`, `device_configuration_template_list`, `device_configuration_template_diff` |
| Firehose | `firehose_health`, `firehose_events`, `firehose_latest` |

Occupancy is a clock-shifted 24-hour weekday replay. Hour 17 is near “now”, so Boardroom North still overcrowds at the morning stand-up (peak 12 in a 10-seat room).

## Demo server

A public Ghost Campus instance is at `https://spaces-ghost.apps.andrewriley.info`. Same 19 read-only tools as a local clone. `/health` is open; `/mcp` needs a bearer.

Get `MCP_BEARER_TOKEN` from Infisical. Do not commit the real value. Replace `<MCP_BEARER_TOKEN>` below.

**Cursor** — `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "url": "https://spaces-ghost.apps.andrewriley.info/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>"
      }
    }
  }
}
```

**Claude Code** — `.mcp.json` or `~/.claude.json`:

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "type": "http",
      "url": "https://spaces-ghost.apps.andrewriley.info/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>"
      }
    }
  }
}
```

Or:

```bash
claude mcp add-json spaces-ghost '{"type":"http","url":"https://spaces-ghost.apps.andrewriley.info/mcp","headers":{"Authorization":"Bearer <MCP_BEARER_TOKEN>"}}'
```

Claude Desktop’s `claude_desktop_config.json` is stdio-only. Use a local stdio clone, or bridge with `mcp-remote` pointing at the same HTTPS URL and bearer.

Check the door:

```bash
curl -s https://spaces-ghost.apps.andrewriley.info/health
curl -s https://spaces-ghost.apps.andrewriley.info/mcp \
  -H "Authorization: Bearer <MCP_BEARER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"firehose_latest","arguments":{}}}'
```

`/health` returns `{"status":"ok","server":"spaces-ghost"}`. `/mcp` without a valid bearer returns `401`.

## Run locally

```bash
git clone git@github.com:andrewkriley/spaces-ghost-mcp.git
cd spaces-ghost-mcp
make venv
make lint
make test
```

`scripts/setup-venv.sh` creates `.venv` and installs `requirements-dev.txt` (Ruff). Runtime still needs no third-party packages. GitHub Actions `ci` runs the same lint + tests in a venv.

### Client JSON (stdio)

Stdio is the local path. No bearer. Run `make venv` first. Replace `/absolute/path/to/spaces-ghost-mcp` with your clone (Windows: `.venv\Scripts\python.exe` and `server.py`). If the file already has other servers, add only the `"spaces-ghost"` object under `mcpServers`.

#### Cursor

Project (open this repo): `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/server.py", "--stdio"]
    }
  }
}
```

All projects: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "command": "/absolute/path/to/spaces-ghost-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/spaces-ghost-mcp/server.py", "--stdio"]
    }
  }
}
```

Cursor Settings → MCP, or save the file and restart Cursor.

#### Claude Desktop

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`  
Windows: `%APPDATA%\Claude\claude_desktop_config.json`  

Settings → Developer → Edit Config, then fully quit and reopen Claude Desktop.

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "command": "/absolute/path/to/spaces-ghost-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/spaces-ghost-mcp/server.py", "--stdio"]
    }
  }
}
```

Claude Desktop only launches stdio servers from this file. Do not put a `url` entry here.

#### Claude Code

This project: `.mcp.json` in the repo root  
Your user config: `mcpServers` in `~/.claude.json`

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "type": "stdio",
      "command": "/absolute/path/to/spaces-ghost-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/spaces-ghost-mcp/server.py", "--stdio"]
    }
  }
}
```

Or:

```bash
claude mcp add-json spaces-ghost '{"type":"stdio","command":"/absolute/path/to/spaces-ghost-mcp/.venv/bin/python","args":["/absolute/path/to/spaces-ghost-mcp/server.py","--stdio"]}'
```

Add `--scope user` to write `~/.claude.json`, or `--scope project` to write `.mcp.json`. Start a new Claude Code session after saving.

### HTTP on loopback

```bash
cp .env.example .env
./run.sh
```

Listens on `127.0.0.1:8080` by default.

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/mcp \
  -H "Authorization: Bearer local-dev" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"firehose_latest","arguments":{}}}'
```

Override with `LISTEN`, `MCP_BEARER_TOKEN`, or `DATASET_PATH`. Binding to `0.0.0.0` is optional and not the default.

HTTP clients (Cursor url transport, Claude Code `type: http`, a sidecar) must send `Authorization: Bearer <token>`.

Cursor (`~/.cursor/mcp.json` or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer local-dev"
      }
    }
  }
}
```

Claude Code (`.mcp.json` or `~/.claude.json`):

```json
{
  "mcpServers": {
    "spaces-ghost": {
      "type": "http",
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer local-dev"
      }
    }
  }
}
```

Claude Desktop does not take a `url` in `claude_desktop_config.json`. Use the stdio block above.

## Dataset

`dataset.py` builds deterministic Ghost Campus (Sydney): North/South buildings, six workspaces, five RoomOS devices, Firehose `EventRecord` envelopes. `dataset.json` is the checked-in artifact.

```bash
python3 dataset.py   # rewrite dataset.json
```

## Tests and lint

```bash
make venv          # once
make lint          # ruff check + format --check
make test          # test_server.py + test_repo.py
```

No live Cisco calls. The demo bearer lives in Infisical; a local `./run.sh` still uses `.env` / `local-dev`.

## Research notes

Webex Workspaces MCP is Control Hub device and room intelligence ([docs](https://developer.webex.com/mcp/docs/workspaces-mcp-server)). Cisco Spaces Firehose is a partner **stream** ([intro](https://developer.cisco.com/docs/cisco-spaces-firehose/), [event types](https://developer.cisco.com/docs/cisco-spaces-firehose/event-types/)). This server keeps the tool names and the `EventRecord` shape so agents can demo occupancy, overcrowding, and RoomOS drift without tenant PII.

Capacity for ~100 users and ~50 concurrent multi-tool MCP questions (application stack plus AWS vs dedicated hosting) is in [docs/capacity.md](docs/capacity.md).
