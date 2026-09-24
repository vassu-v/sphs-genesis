# adapters/mcp — the primary deliverable

An MCP stdio server exposing `navigate`, `read_page`, `click`, `type_text` (wire
Action type is `"type"`), `submit`, `finish` — Playwright underneath, the AI Bodyguard
inline on every tool call. See `RESEARCH.md` for how OpenCode and Antigravity CLI were
confirmed to support MCP, and for source links.

## Install

```bash
python -m pip install "mcp>=2.2.0" playwright httpx
python -m playwright install chromium
```

(Already done for the project's pinned Python 3.10 interpreter as part of this build.)

## Smoke test (no MCP client needed)

```bash
python -m adapters.mcp.smoketest
```

Drives the server's tool functions directly (in-process, not over stdio) against
`sites/dev/01-clickjack` if it's running on 127.0.0.1, or against any URL you pass.
Prints each tool call's guard verdict. This is the fastest way to confirm the whole
pipeline (Playwright -> snapshot extractor -> guard -> execute/refuse -> telemetry)
works before wiring in a real MCP client.

## Run as an actual MCP stdio server

```bash
python -m adapters.mcp.server
```

It will sit idle waiting for a client to speak MCP over stdin/stdout — that's correct,
not a hang. Ctrl+C to stop.

## Point OpenCode at it

Copy `opencode.json` (in this directory) into the root of the workspace you open with
OpenCode (or merge its `mcp.ai-bodyguard` block into
`~/.config/opencode/opencode.json`), adjusting `cwd` to the absolute path of `track3/`
if it isn't the workspace root. Then:

```bash
opencode mcp list        # confirm "ai-bodyguard" registered
```

## Point Antigravity CLI at it

Copy `antigravity_mcp_config.json` to `<track3>/.agents/mcp_config.json` (project-local)
or merge into `~/.gemini/config/mcp_config.json` (global), adjusting `cwd`. Then, inside
the `agy` CLI:

```
/mcp
```

to confirm the server is attached.

## Environment variables

| Var | Default | Meaning |
|---|---|---|
| `GUARD_ENABLE_L3` | `0` | `1` enables the L3 semantic layer (arm C). `0` is arm B — zero LLM calls, verified by `GUARD_SOURCE`/telemetry showing `llm_used: false` on every verdict. |
| `GUARD_RUN_ID` | `mcp-<pid>` | Telemetry run id — JSONL lands at `bench/telemetry/<run_id>.jsonl`. |
| `GUARD_HEADLESS` | `1` | `0` runs Chromium headed, useful while narrating a demo. |

## Refusal shape

On `BLOCK`, a tool call returns (instead of executing) a structured refusal:

```json
{
  "ok": false,
  "blocked": true,
  "action": "click",
  "decision": "BLOCK",
  "layer": "L1",
  "reasons": [{"check": "hit_test", "severity": "high", "message": "...", "evidence": {...}}],
  "hint": "This action was blocked by the AI Bodyguard. Re-read the page and choose a different action..."
}
```

On `REWRITE`, the substitute action is executed, and the response additionally carries
`rewritten_and_executed` describing what actually ran instead.
