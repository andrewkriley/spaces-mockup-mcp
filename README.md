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

## Run locally

```bash
git clone git@github.com:andrewkriley/spaces-ghost-mcp.git
cd spaces-ghost-mcp
make venv
make lint
make test
```

`scripts/setup-venv.sh` creates `.venv` and installs `requirements-dev.txt` (Ruff). Runtime still needs no third-party packages. GitHub Actions `ci` runs the same lint + tests in a venv.

### Cursor / Claude Desktop (stdio)

Add to MCP config (absolute path to this clone):

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

Stdio does not need a bearer. The process is local.

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

HTTP clients (Cursor url transport, a sidecar, another agent) must send `Authorization: Bearer <token>`.

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

No live Cisco calls. No cluster, Flux, or Infisical.

## Research notes

Webex Workspaces MCP is Control Hub device and room intelligence ([docs](https://developer.webex.com/mcp/docs/workspaces-mcp-server)). Cisco Spaces Firehose is a partner **stream** ([intro](https://developer.cisco.com/docs/cisco-spaces-firehose/), [event types](https://developer.cisco.com/docs/cisco-spaces-firehose/event-types/)). This server keeps the tool names and the `EventRecord` shape so agents can demo occupancy, overcrowding, and RoomOS drift without tenant PII.

Capacity for ~100 users and ~50 concurrent multi-tool MCP questions (application stack plus AWS vs dedicated hosting) is in [docs/capacity.md](docs/capacity.md).
