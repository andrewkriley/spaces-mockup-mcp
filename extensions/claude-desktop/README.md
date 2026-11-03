# Claude Desktop extension

`spaces-mockup.mcpb` connects Claude Desktop (Windows / macOS) to the hosted
lab server at `https://spaces-mockup.mcp.buildermate.ai/mcp`. It runs on the
Node.js built into Claude Desktop, so attendees don't install anything.
Claude Desktop asks for the bearer token at install time and stores it as a
secret. The token is never in this folder.

- `manifest.json`: extension manifest. The token is the `bearer_token` user setting.
- `server/index.js`: a dependency-free stdio to Streamable HTTP bridge. It
  adds the `Authorization: Bearer` header and drops the server's replies to
  notifications.
- `spaces-mockup.mcpb`: the packed extension that attendees install.

Install steps for attendees are in `docs/new-lab-guide-1.md`.

## Rebuild

```bash
cd extensions/claude-desktop
npx -y @anthropic-ai/mcpb@2.1.2 validate manifest.json
npx -y @anthropic-ai/mcpb@2.1.2 pack . spaces-mockup.mcpb
```

Bump `version` in `manifest.json` when you change the bridge.

## Test without Claude Desktop

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | MCP_BEARER_TOKEN="$(cat ~/.spaces-token)" node server/index.js
```
