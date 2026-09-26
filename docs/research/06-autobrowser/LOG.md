# Analysis Log — Auto Browser

2026-09-24T00:00 — Started analysis of D:\work\genesishackathon\external\auto-browser (read-only). Goal: determine whether Auto Browser can supply computed styles / bbox / ancestry / elementFromPoint for a deterministic clickjacking/dark-pattern guard, enumerate its full MCP tool surface, find the cleanest interception point, catalogue existing safety machinery for overlap, and document how to run it on Windows 11 with OpenRouter/Gemini keys.

2026-09-24T00:05 — Read controller/app/browser/services/observation.py in full (352 lines). Confirmed observation payload shape for all four perception presets (fast/text/normal/rich). No elementFromPoint, no computed-style dump, no full ancestry chain anywhere in this file.

2026-09-24T00:10 — Read controller/app/tool_gateway/gateway.py in full (848 lines). Found `browser.eval_js` (`_eval_js`, line 560-563) — a raw `page.evaluate(payload.expression)` with no sandboxing beyond a `workflow_profile=governed` gate (line 180-181). Found `browser.find_elements` (`_find_elements`, line 582-673) which already returns per-element bounding boxes via `getBoundingClientRect()`. Found `browser.eval_js` is the only unrestricted JS-eval tool.

2026-09-24T00:15 — Read controller/app/mesh/policy.py in full (186 lines). This is NOT a per-click content-safety policy — it is an agent-mesh capability-delegation evaluator (default-deny grants between peer nodes, url_allowlist / rate-limit / expiry only). Does not evaluate page content, geometry, or overlays. No overlap with our planned clickjacking check.

2026-09-24T00:20 — Read controller/app/tool_gateway/registry.py (188 lines) and all pack files (core.py, dom.py, operations.py, diagnostics.py, session_ops.py, storage.py) to build the complete curated vs full tool inventory (harness.py pack not yet opened — deferred, not required for click-safety analysis).

2026-09-24T00:30 — Read controller/app/browser/services/actions.py in full (751 lines). This is the critical file: `click()` (line 61) resolves a target via `resolve_target()` then calls `click_human_like()` (line 527) which does raw `page.mouse.move/down/up` at a bounding-box-center coordinate obtained from `locator_center()` (`getBoundingClientRect()` center). It explicitly avoids Playwright's own `locator.click()` actionability check in the coordinate path (only falls back to `locator.click()` if `locator_center()` returns None). This means Playwright's built-in "element receives pointer events at this point" guard is bypassed for the common path — there is no elementFromPoint check anywhere in the click pipeline today.

2026-09-24T00:35 — Read controller/app/witness.py (first 120 of 666 lines) and controller/app/rate_limits.py (first 60 of 128 lines). Witness = Ed25519-signed audit/evidence hash-chain of receipts (what happened, approval status, before/after observation diffs) — not a real-time content-safety check. rate_limits.py = generic sliding-window limiter, used elsewhere for request throttling, unrelated to DOM safety.

2026-09-24T00:40 — Read docs/mcp-clients.md and docs/llm-adapters.md in full. Confirmed curated-vs-full tool profile split, MCP resource set, and that risk_category-driven approvals happen in the controller, not the model. Confirmed provider adapters: native `openai`, `claude`, `gemini` adapters plus a generic `openai_compatible.py` multi-profile adapter that includes a native `openrouter` profile (env `OPENROUTER_API_KEY`, `openrouter_base_url`, `openrouter_model`).

2026-09-24T00:45 — Checked controller/pyproject.toml: `requires-python = ">=3.11"`, CI runs 3.11 and 3.14, Dockerfile pins `python:3.11-slim`. Note: this conflicts with the user's global CLAUDE.md default of Python 3.10 — 3.10 will not satisfy this project's requirement; 3.12 will.

2026-09-24T00:50 — Checked Makefile: `doctor`, `test`, `smoke-isolation` targets all shell out to bash scripts under scripts/ and assume Docker — not natively runnable from PowerShell without Git Bash/WSL, though `docker compose up --build` itself works fine from PowerShell with Docker Desktop.

2026-09-24T00:55 — Wrote FINDINGS.md and INTEGRATION.md. No source files modified. No commands run against the running system — this was a static, read-only code review.
