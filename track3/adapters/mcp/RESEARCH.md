# RESEARCH — MCP integration for OpenCode / Antigravity CLI

Researched 2026-09-24 via WebSearch/WebFetch (live docs, not memory). Sources dated below.

## 1. Does OpenCode support MCP? Yes — local (stdio) and remote (HTTP/OAuth) servers.

Source: https://opencode.ai/docs/mcp-servers/ (fetched 2026-09-24), corroborated by
https://opencode.ai/docs/config/ and https://composio.dev/content/mcp-with-opencode.

- Config file: `opencode.json` / `opencode.jsonc`. Either global
  (`~/.config/opencode/opencode.json`) or project-root (`./opencode.json`). If both
  define the same server name, **the project file wins**.
- Local (stdio) server shape:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai-bodyguard": {
      "type": "local",
      "command": ["python", "-m", "adapters.mcp.server"],
      "enabled": true,
      "environment": { "GUARD_CONFIG": "arm-c" },
      "cwd": "."
    }
  }
}
```

- Required fields: `type: "local"`, `command: string[]`.
- Optional: `enabled`, `environment` (env vars), `cwd`, `timeout` (ms, default 5000,
  for the initial tool-list fetch).
- Remote servers use `type: "remote"`, a `url`, and `oauth: true/false` — not needed
  for us since our server runs locally over stdio.
- CLI: `opencode mcp add` (interactive), `opencode mcp list` to confirm registration.

**Conclusion: OpenCode DOES support MCP over stdio.** The brief's premise ("OpenCode
ships no browser tool, so we supply it") is correct and MCP is the right transport —
no fallback/shim needed for OpenCode.

## 2. Antigravity CLI — also MCP, stdio, different config path/shape

Sources: https://antigravity.google/docs/mcp/, https://antigravity.google/docs/cli/features/,
https://composio.dev/content/howto-mcp-antigravity (fetched 2026-09-24).

- Config file: `mcpServers` object (Claude/Cursor-style), at:
  - Global: `~/.gemini/config/mcp_config.json`
  - Project-local: `.agents/mcp_config.json` (this is the one we ship in-repo)
- Shape:

```json
{
  "mcpServers": {
    "ai-bodyguard": {
      "command": "python",
      "args": ["-m", "adapters.mcp.server"],
      "env": { "GUARD_CONFIG": "arm-c" },
      "cwd": "D:/work/genesishackathon/track3"
    }
  }
}
```

- Remote/HTTP servers use `serverUrl`, NOT `url`/`httpUrl` (a documented gotcha —
  legacy key names from Cursor/VS Code configs are silently unsupported). Irrelevant
  to us since we're stdio-only, but worth flagging for anyone copy-pasting configs.
- CLI usage: run `agy`, then `/mcp` inside the session to see/attach configured
  servers.

**Conclusion: Antigravity CLI also speaks MCP over stdio**, with a near-identical
`command`/`args`/`env`/`cwd` server object, just wrapped in `mcpServers` at a
different file path than OpenCode. One server binary, two 5-line config snippets —
this is what "protected by configuration alone" in context.md §2 actually cashes out
to. See `adapters/mcp/opencode.json` and `adapters/mcp/antigravity_mcp_config.json`
for ready-to-paste versions.

## 3. Python MCP SDK — current version and minimal stdio server

Source: https://pypi.org/project/mcp/ (fetched 2026-09-24).

- Latest: **mcp 2.2.0** (released 2026-09-07). Requires Python 3.10+ (classifiers list
  3.10–3.14) — matches this project's pinned Python 3.10.
- Installed locally with the project's Python 3.10 interpreter:
  `C:/Users/Shorya/AppData/Local/Programs/Python/Python310/python.exe -m pip install "mcp>=2.2.0"`.
- High-level API is `mcp.server.fastmcp.FastMCP`: decorate functions with `@mcp.tool()`,
  call `mcp.run(transport="stdio")` in `if __name__ == "__main__"`. This is what
  `adapters/mcp/server.py` uses. It gets you: schema generation from type hints,
  request validation, and stdio transport, in a few lines — no manual JSON-RPC framing.
- Playwright (sync API is not usable inside FastMCP's async tool handlers without a
  background thread, since Playwright's sync API refuses to run inside an already-running
  asyncio loop). We use `playwright.async_api` throughout the MCP server for this reason;
  the Playwright *shim* in `adapters/playwright/` targets the sync API instead, since
  that is what existing Playwright test/harness code typically already uses.

## 3b. Correction found only by actually installing mcp 2.2.0

The tutorials found in step 3 (dated 2026, but apparently written against the 1.x
line) all show `from mcp.server.fastmcp import FastMCP`. Installing the real current
package and importing it fails immediately:

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where
FastMCP was renamed to MCPServer (from mcp.server.mcpserver import MCPServer) ...
see https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver
```

The decorator (`.tool()`) and `.run(transport="stdio")` API are otherwise unchanged, so
this is a pure rename. `adapters/mcp/server.py` imports `MCPServer` and aliases it as
`_MCPServerImpl` with a fallback to the old `FastMCP` import for anyone running an
older SDK pin. Flagging this because every search result and every AI-generated
tutorial currently repeats the stale `fastmcp` import path — a strong example of why
this brief insisted on live docs over memory, and worth a line in the report since the
next person to touch this file will hit the same wall if they copy a tutorial verbatim.

## Net implication for build

No fallback needed — build the MCP server as the primary deliverable exactly as
context.md §2 assumes. Ship both config snippets so the "OpenCode + Antigravity, zero
code change on their side" claim is literally demonstrable, not just asserted.
