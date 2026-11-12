#!/usr/bin/env node
// stdio <-> Streamable HTTP bridge for the spaces-mockup lab server.
// Reads JSON-RPC messages (one per line) from stdin, POSTs them to the
// remote MCP endpoint with the bearer token, and writes replies to stdout.
// No dependencies: uses the fetch built into Node 18+.

const URL_ = process.env.MCP_SERVER_URL || "https://spaces-mockup.mcp.buildermate.ai/mcp";
// Forgive common paste mistakes: surrounding whitespace or quotes, and a
// leading "Bearer " copied along with the token. An unexpanded
// ${user_config...} placeholder means Claude Desktop has no token saved.
function cleanToken(raw) {
  let t = (raw || "").trim().replace(/^["']+|["']+$/g, "").trim();
  t = t.replace(/^bearer\s+/i, "").trim();
  if (t.startsWith("${")) t = "";
  return t;
}
const TOKEN = cleanToken(process.env.MCP_BEARER_TOKEN);
const NO_TOKEN_MSG =
  "No bearer token is set for spaces-mockup. In Claude Desktop open Settings > Extensions > " +
  "Spaces Mockup (Lab) > Configure, paste the token, save, then turn the extension off and on.";
let sessionId = null;

const log = (...a) => console.error("[spaces-mockup]", ...a);
const send = (msg) => process.stdout.write(JSON.stringify(msg) + "\n");
const fail = (id, message) => {
  if (id !== undefined && id !== null) send({ jsonrpc: "2.0", id, error: { code: -32000, message } });
};

if (!TOKEN) log(NO_TOKEN_MSG);

async function forward(msg) {
  if (!TOKEN) return fail(msg.id, NO_TOKEN_MSG);

  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
    Authorization: `Bearer ${TOKEN}`,
  };
  if (sessionId) headers["Mcp-Session-Id"] = sessionId;

  let res;
  try {
    res = await fetch(URL_, { method: "POST", headers, body: JSON.stringify(msg) });
  } catch (e) {
    log("network error:", e.message);
    return fail(msg.id, `Cannot reach ${URL_}: ${e.message}`);
  }

  const sid = res.headers.get("mcp-session-id");
  if (sid) sessionId = sid;

  if (res.status === 401) {
    log("401 from server: bearer token rejected");
    return fail(
      msg.id,
      "spaces-mockup rejected the bearer token (HTTP 401). The token is set but wrong. " +
        "Open Settings > Extensions > Spaces Mockup (Lab) > Configure, paste the token from the " +
        "Box folder again (only the token, without 'Bearer'), save, then turn the extension off and on."
    );
  }
  if (!res.ok && res.status !== 202) {
    const text = await res.text().catch(() => "");
    log(`HTTP ${res.status}:`, text.slice(0, 300));
    return fail(msg.id, `spaces-mockup returned HTTP ${res.status}`);
  }

  const body = await res.text();
  if (!body.trim()) return; // 202 / notification ack
  // Notifications have no id and must not get a reply. This server sometimes
  // answers them with an error carrying a stale id, so drop it.
  if (msg.id === undefined || msg.id === null) return;

  const type = res.headers.get("content-type") || "";
  if (type.includes("text/event-stream")) {
    for (const block of body.split(/\r?\n\r?\n/)) {
      const data = block
        .split(/\r?\n/)
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (data) {
        try { send(JSON.parse(data)); } catch { log("bad SSE data:", data.slice(0, 200)); }
      }
    }
  } else {
    try {
      const parsed = JSON.parse(body);
      for (const m of Array.isArray(parsed) ? parsed : [parsed]) send(m);
    } catch {
      log("bad JSON response:", body.slice(0, 200));
      fail(msg.id, "spaces-mockup returned an unreadable response");
    }
  }
}

let buf = "";
let queue = Promise.resolve();
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buf += chunk;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { log("ignoring non-JSON input"); continue; }
    // Keep messages in order: initialize must finish before the next request.
    queue = queue.then(() => forward(msg)).catch((e) => log("error:", e.message));
  }
});
process.stdin.on("end", () => queue.then(() => process.exit(0)));
