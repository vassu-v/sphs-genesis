# Auto Browser — Findings for the click-safety guard

Source analysed (read-only): `<repo>\external\auto-browser\` (MIT license).
All line numbers below are from the checked-out tree as of this analysis.

---

## 1. THE LOAD-BEARING QUESTION — can we get computed styles / bbox / ancestry / elementFromPoint?

**Short answer: not out of the box from the observation/DOM-summary payload, but yes via the existing `browser.eval_js` tool, and observation.py is a clean, already-factored extension point if we'd rather add a dedicated field.**

### 1a. What the observation payload already contains, field by field

`controller/app/browser/services/observation.py::observation_payload()` (lines 60-154) builds different payloads per `preset`:

- `session` - session summary dict (id, status, url, etc., from `manager._session_summary`)
- `url`, `title` - plain strings
- `active_element` - from `ACTIVE_ELEMENT_SCRIPT` (browser_scripts.py lines 163-175): `{tag, element_id, name, id, label}` for `document.activeElement`. No bbox, no computed style, no ancestry.
- `text_excerpt` - squashed `document.body.innerText`, truncated (`PAGE_SUMMARY_SCRIPT`, browser_scripts.py lines 177-228)
- `dom_outline` - `{headings[], forms[], counts{links,buttons,inputs,forms}}`, also from `PAGE_SUMMARY_SCRIPT`. Headings/forms only; no generic element list, no bbox, no style.
- `accessibility_outline` - from Playwright's native `page.accessibility.snapshot(interesting_only=True)` (observation.py lines 238-316): `{available, root_role, root_name, focused, role_counts, nodes[]}` where each node is `{role, name, value, description, focused, disabled, selected, checked, expanded, pressed, depth}`, capped at `ACCESSIBILITY_NODE_LIMIT = 30`. This is the AX tree, not the box tree - no coordinates, no CSS, no DOM parent/child pointers, and it filters to `interesting_only` nodes (hidden/decorative nodes drop out - the opposite of what an overlay-detector needs).
- `ocr` - Tesseract text blocks with pixel boxes from the *rendered screenshot*, only in `normal`/`rich` presets (and only when not skipped per `_extract_ocr_if_needed`, lines 156-175). Gives bounding boxes but for OCR'd text blocks, not DOM elements, and is redacted for PII before the agent sees it (`_scrub_screenshot_if_needed` lines 318-351).
- `interactables` - from `INTERACTABLES_SCRIPT` (browser_scripts.py lines 101-161): for each visible interactive element (`a, button, input, textarea, select, [role=button/link/textbox], [contenteditable], [tabindex]`), returns `{element_id, selector_hint, tag, type, role, label, disabled, href, bbox:{x,y,width,height}}`. This is the closest thing to a geometry feed that ships today - real `getBoundingClientRect()` boxes, capped at `limit` (default 40, up to 200 for `rich`). Visibility check is shallow: `rect.width>0 && rect.height>0 && style.visibility!=='hidden' && style.display!=='none'` (lines 103-107) - does NOT check `opacity`, `clip-path`, `pointer-events`, z-index/stacking, or off-screen tricks, and does not check whether the element is actually the topmost hit at its own center (no `elementFromPoint`).
- `screenshot_path`/`screenshot_url`, `console_messages`, `page_errors`, `request_failures`, `tabs`, `recent_downloads`, `takeover_url`, `remote_access`, `preset` - operational/session metadata, not DOM-safety data.

None of the above gives full computed style (opacity, colors, `clip-path`, `z-index`), DOM ancestry (parent chain to `<body>`), or `document.elementFromPoint()` results. The flagship clickjacking check (click target vs. `elementFromPoint` at its center) does not exist anywhere in this codebase.

### 1b. `browser.find_elements` - a second, independent geometry source

`gateway.py::_find_elements()` (lines 582-673), registered in `controller/app/tool_gateway/packs/dom.py` (lines 50-61), is a second MCP-exposed tool (curated AND full) that runs its own inline `page.evaluate` and returns, per matched element: `tag, text, value, href, id, class, visible (width>0&&height>0), x, y, width, height`. Same shallow visibility test as `INTERACTABLES_SCRIPT`; still no computed style, no ancestry, no elementFromPoint.

### 1c. `browser.eval_js` - the actual extension point that already exists

`controller/app/tool_gateway/packs/dom.py` lines 17-27 registers a ToolSpec named `browser.eval_js` with `input_model=EvalJsInput`, `handler=gateway._eval_js`, `governed_kind="write"`.

Handler, `gateway.py` lines 560-563:
```
async def _eval_js(self, payload: EvalJsInput) -> dict[str, Any]:
    session = await self.manager.get_session(payload.session_id)
    result = await session.page.evaluate(payload.expression)
    return {"session_id": payload.session_id, "result": result}
```

This is a raw, unsandboxed `page.evaluate(arbitrary_js_string)` - it can call `document.elementFromPoint(x, y)`, walk `.parentElement` for ancestry, and read `getComputedStyle(el)` for any property, in one call, today, with zero code changes to Auto Browser. The only gate is at `gateway.py` line 180-181:

```
if spec.name == "browser.eval_js" and policy_profile != "governed":
    return self._error_response("browser.eval_js requires workflow_profile=governed")
```

Every call must set `workflow_profile=governed` (alias handled in `_pop_policy_profile`, lines 296-301). Because its `governed_kind="write"`, going through `_require_governed_tool_approval` (lines 311-335) would additionally require an operator approval unless the caller already supplies `governed_approval_id`/`approval_id`. That approval requirement is real friction for a guard that needs to run this check on every click with no human in the loop - see section 3.

### 1d. If we want it as a first-class field instead of an eval_js call

`BrowserObservationService.page_summary()` (observation.py lines 227-236) already composes three separate `page.evaluate` calls into one dict. Adding a fourth call - e.g. a new `CLICK_SAFETY_SCRIPT` that, for a given `(x, y)` or `element_id`, returns `{elementFromPoint_matches: bool, hit_tag, hit_selector, ancestry: [...], computed_style: {opacity, fontSize, color, backgroundColor, clipPath, pointerEvents, zIndex}}` - is a same-shaped, low-risk addition at this exact location (line 228 area), or as a new method beside `accessibility_outline()` (line 238). `observation.py` lines 227-236 (`page_summary`) is the natural seam; no fork of the click-execution path is required to add read-only geometry/style data.

---

## 2. THE FULL TOOL SURFACE - curated vs full

Source of truth: `controller/app/tool_gateway/registry.py` (`ToolRegistry.register`, filters by `spec.profiles`, default `("curated","full")`) and the six pack files under `controller/app/tool_gateway/packs/` (`core.py`, `dom.py`, `operations.py`, `diagnostics.py`, `session_ops.py`, `storage.py` - `harness.py` not read in full but is exclusively `profiles=("full",)`-gated per `docs/mcp-clients.md` lines 195-205).

### Curated profile (default) - every tool NOT tagged `profiles=("full",)`

From `packs/core.py`:
- `browser.create_session` (name?, start_url?, storage_state_path?, auth_profile?, memory_profile?, proxy_persona?, proxy_server/username/password?, user_agent?, protection_mode?, totp_secret?) -> session record
- `browser.save_memory_profile` (profile_name, goal_summary, completed_steps, discovered_selectors, notes) -> profile dict; `governed_kind="write"`
- `browser.get_memory_profile` (profile_name) -> profile dict
- `browser.list_memory_profiles` () -> list
- `browser.list_sessions` () -> list of session summaries
- `browser.get_session` (session_id) -> live summary or persisted record
- `browser.observe` (session_id?, limit=40, preset?) -> the observation payload from section 1a
- `browser.screenshot` (session_id?, label) -> `{session, url, screenshot_path, screenshot_url, takeover_url}`
- `browser.get_console` / `browser.get_page_errors` / `browser.get_request_failures` (session_id, limit) -> tail lists
- `browser.stop_trace` (session_id) -> trace artifact path
- `browser.list_auth_profiles` () / `browser.get_auth_profile` (profile_name) -> profile metadata
- `browser.list_downloads` (session_id) -> download records
- `browser.list_tabs` / `browser.activate_tab` / `browser.close_tab` (session_id, index) -> tab lists; close_tab is `governed_kind="write"`
- `browser.execute_action` (session_id, action: BrowserActionDecision, approval_id?) -> the main actuator; `governed_kind="dynamic"` (risk category comes from the decision itself - see section 3)
- `browser.save_auth_profile` (session_id, profile_name) -> `governed_kind="account_change"`
- `browser.request_human_takeover` (session_id, reason) -> `governed_kind="write"`
- `browser.close_session` (session_id) -> `governed_kind="write"`

From `packs/dom.py` (all curated+full):
- `browser.eval_js` (session_id, expression) -> `{session_id, result}`; `governed_kind="write"`, plus the hard `workflow_profile=governed` gate described in section 1c
- `browser.wait_for_selector` (session_id, selector, timeout_ms, state)
- `browser.get_html` (session_id, text_only?) -> full HTML or innerText
- `browser.find_elements` (session_id, selector? | query?, regex?, context?, limit?) -> element list with bbox (see section 1b)
- `browser.drag_drop` (session_id, source_selector|source_x/y, target_selector|target_x/y) -> `governed_kind="write"`
- `browser.set_viewport` (session_id, width, height)
- `browser.find_by_vision` (session_id, description, take_screenshot?) -> vision-model coordinate guess (only registered if a vision targeter/Anthropic key is configured - unregistered otherwise, `gateway.py` lines 134-135)

From `packs/diagnostics.py` (curated unless noted):
- `browser.readiness_check` (mode?) -> pass/warn/fail report (encryption, operator identity, bearer token, isolation, Witness audit, host allowlist, PII scrubbing, upload approval)
- `browser.get_network_log` (session_id, limit, method?, url_contains?) -> PII-scrubbed HTTP log
- `browser.verify_witness` / `browser.export_witness_bundle` (session_id) -> hash-chain verification / portable evidence bundle
- `browser.export_script` - full only
- `browser.pii_scrubber_status` - full only
- `browser.get_remote_access` - full only

From `packs/session_ops.py`: `browser.fork_session` is curated; `browser.cdp_attach`, `browser.share_session`, `browser.enable_shadow_browse` are full only.

From `packs/storage.py`: `browser.get_cookies`, `browser.set_cookies`, `browser.get_local_storage`, `browser.set_local_storage` are all full only.

### Full profile adds (on top of curated)

- Approval admin: `browser.list_approvals`, `browser.approve_approval`, `browser.reject_approval`, `browser.execute_approval`
- Agent job queue: `browser.list_agent_jobs`, `browser.get_agent_job`, `browser.resume_agent_job`, `browser.discard_agent_job`, `browser.cancel_agent_job`, `browser.queue_agent_step`, `browser.queue_agent_run`
- Provider introspection: `browser.list_providers`
- Remote-access admin: `browser.get_remote_access`
- Cookie/storage tools (all four, `packs/storage.py`)
- Session/CDP admin: `browser.cdp_attach`, `browser.share_session`, `browser.enable_shadow_browse`
- Proxy/cron ops (`packs/operations.py`, all full-only): `browser.list_proxy_personas`, `browser.create_proxy_persona`, `browser.delete_proxy_persona`, `browser.list_cron_jobs`, `browser.create_cron_job`, `browser.delete_cron_job`, `browser.trigger_cron_job`
- `browser.export_script`, `browser.pii_scrubber_status`
- `browser.delete_memory_profile` (`governed_kind="destructive"`)
- `browser.save_auth_state` (`governed_kind="account_change"`)
- `harness.*` (start_convergence, get_status, get_trace, list_runs, list_candidates, get_candidate, check_drift, check_all_drifts, graduate) - note `docs/mcp-clients.md` lines 184-186 say the three read-only harness introspection tools are actually exposed in curated too; the mutating ones need full.

Important nuance: README/docs describe curated as hiding "approval admin tools, built-in agent queue tools, provider introspection tools, remote-access admin tools" - but per the actual registry code, cookie/local-storage read-write, CDP attach, and proxy/cron management are ALSO full-only, which the docs prose doesn't call out explicitly. Treat the registry (`registry.py` + packs) as ground truth over the README's summary.

---

## 3. WHERE A GUARD SLOTS IN - ranked

Ranking (cleanest -> most invasive): (1) an external MCP proxy in front of `/mcp` > (2) `gateway.py::call_tool()` as a fork-free monkey-patch/wrapper > (3) `mesh/policy.py::evaluate()` (wrong layer, not usable as-is) > (4) the stdio bridge (thin passthrough, same limitation as external proxy but weaker).

### `mesh/policy.py::PolicyEvaluator.evaluate()` (lines 137-165) - what it does today

This is agent-to-agent capability delegation for the mesh feature, NOT a per-tool-call browser-safety policy. It answers "does peer X's `DelegationRequest` for `capability` (e.g. `tool:browser.click`) have a matching `CapabilityGrant` from a default-deny grant list?" Constraint evaluators actually implemented: `_check_expires_at` (grant TTL), `_check_rate_limit` (rolling per-hour counter), `_check_url_allowlist` (fnmatch against `request.arguments["url"]` or `["start_url"]` only - NOT against click targets, selectors, or coordinates). Grants match by exact capability string or a `"prefix:*"` wildcard (lines 167-185). It cannot express our checks: there is no hook here that sees rendered page state, geometry, or computed style - `DelegationRequest.arguments` is whatever the calling peer sent, unvalidated against the live DOM. Using this layer would mean teaching it about a capability type it was never designed for, effectively rewriting it. Not recommended.

### `gateway.py::call_tool()` (lines 144-169, wrapping `_call_tool()` lines 171-242) - the addressable seam

Every MCP tool call - including `browser.execute_action` (the click/type/etc. actuator) and `browser.eval_js` - passes through this single method. At call time we have: the resolved Pydantic `arguments` (post-`model_validate`, so a `BrowserActionDecision` for `execute_action`, including `action`, `element_id`/`selector`/`x`/`y`), and a live `session.page` reachable via `self.manager.get_session(...)`. A guard hooked here (a fork-free wrapper class composing `McpToolGateway` and overriding `call_tool`, or a decorator around the constructed instance's `call_tool`) has full page state available BEFORE the click happens: it can resolve the target's on-page coordinates the same way `actions.py::resolve_target/locator_center` does (lines 733-750, 489-496) and run `document.elementFromPoint()` at that point via one extra `page.evaluate()`, then reject the call by returning an `McpToolCallResponse(isError=True, ...)` - exactly the shape `_error_response()` already returns (lines 244-250). This does not require forking: `McpToolGateway` is a plain class constructed by the FastAPI app; a thin subclass or wrapper placed between the ASGI route and the gateway achieves interception without touching auto-browser source. Best fork-free integration point INSIDE the process.

### External proxy in front of `http://127.0.0.1:8000/mcp` - the best fork-free integration point OUTSIDE the process

`docs/mcp-clients.md` documents the MCP transport as a normal streamable-HTTP JSON-RPC endpoint (`POST /mcp` with `MCP-Session-Id`/`MCP-Protocol-Version` headers, `tools/call` method) - an MCP-spec-compliant reverse proxy can inspect every `tools/call` request/response pair without any code change to Auto Browser at all - cleanest way to "protect an agent we did not write." Limitation: the proxy sees only the JSON tool-call payload, not page state - to run our `elementFromPoint` check, the proxy itself needs a way to query the page. Two sub-options: (a) the proxy also holds a `browser.eval_js` credential and, upon seeing an inbound `browser.execute_action` click, first calls `browser.eval_js` itself (governed, see section 1c friction) to get the hit-test result, then either forwards or blocks the original call; (b) the proxy calls `browser.observe`/`browser.find_elements` for bbox data and re-implements `elementFromPoint`'s stacking-context logic itself - harder and less reliable than asking the real browser. (a) is preferred: it reuses the browser's own compositor for ground truth. This option is architecturally the cleanest (zero coupling to Auto Browser internals, fully add-on), but pays a real latency/approval cost per click because of the `governed` + approval-queue requirement on `eval_js` (section 1c) unless the deployment is configured to auto-approve a pre-registered guard identity.

### The stdio bridge (`scripts/mcp_stdio_bridge.py` / `uvx auto-browser-mcp`)

Per `docs/mcp-clients.md` lines 18-25, this is a stdio<->HTTP bridge with no logic of its own - intercepting here is equivalent to the external-proxy option but only for stdio-transport clients, and offers no additional page-state access. Not preferred over a direct HTTP proxy.

### Recommendation

Given the "we strongly prefer not to fork" constraint: build the guard as (1) an external MCP-aware proxy in front of `/mcp` that, for any `browser.execute_action` call with `action in {click, hover}`, first issues its own `browser.eval_js` call (as a pre-registered, auto-approved guard operator/approval workflow - this requires an operator-side deployment change, not a source change, e.g. a standing approval or an approval webhook auto-approver) running an elementFromPoint + computed-style script against the resolved target, and blocks/allows accordingly before relaying the original call. Fall back to (2) an in-process wrapper around `McpToolGateway.call_tool` only if we control the controller's process and want to avoid the second network round trip and governed-approval friction of driving `eval_js` externally.

---

## 4. SAFETY MACHINERY THAT ALREADY EXISTS - and whether it overlaps our plan

| Mechanism | What it does | Where | Overlaps our clickjacking/hidden-text plan? |
|---|---|---|---|
| Approval gates (`ApprovalKind`: write/upload/post/payment/account_change/destructive) | Per-action risk classification (`BrowserActionDecision.risk_category`, `models.py` line 302, defaulted in `validate_action_requirements` lines 346-379) drives whether `execute_decision` (`actions.py` lines 243-330) must pause for a human/API approval before running. `fast` profile approves only high-risk categories; `governed` profile approves every non-read action (`docs/llm-adapters.md` lines 129-133). | `actions.py::require_decision_approval` (331-389), `approvals.py` (not fully read) | NO OVERLAP. This is intent-based risk classification set by the calling LLM/agent itself (`risk_category` is self-declared as part of the decision), not a structural/geometric check of what's actually on screen. A hostile page's fake "Cancel" button that is really a fake "Subscribe" button sails through this gate unchanged - the agent still thinks it's clicking Cancel. This is exactly the gap we exist to fill. |
| Audit events | Structured event log (`_events.emit_observe`, `_events.emit_approval`, etc.) plus an MCP resource `browser://audit/events` (`docs/mcp-clients.md` lines 117-118). | `controller/app/events.py` (not read in full) | No overlap - after-the-fact logging, not a pre-click gate. |
| PII scrubbing | Regex/OCR-based redaction of screenshots and network logs (`pii_scrubber.screenshot(...)`, `observation.py` lines 318-351; `gateway.py::_pii_scrubber_status`). | `controller/app/pii/` (inferred, not opened) | No overlap - protects OUTBOUND data leakage (what the agent's screenshot/log shows a downstream consumer), not inbound manipulation of the agent by the page. Different threat direction entirely. |
| Witness receipts | Ed25519-signed hash-chain of "what happened" receipts, each with before/after observation snapshots, `action_class`, `approval` status, and free-text `concerns` (`WitnessConcern{code, severity, summary, enforced, details}`, `witness.py` lines 40-45). Exportable, independently verifiable bundle (`browser.export_witness_bundle`). | `controller/app/witness.py` (666 lines, partially read) | PARTIAL OVERLAP IN SHAPE ONLY, NOT SUBSTANCE. `WitnessConcern` is a generic "flag anything, with a severity and whether it was enforced" container - if we wanted to record our guard's verdict (e.g. `code="overlay_click_blocked"`) inside the existing evidence trail rather than build our own logging, this schema is reusable. But nothing today populates a `WitnessConcern` from DOM geometry - it's an empty vessel for future concern types, not a working detector. Legitimate place to plug our guard's OUTPUT, not a place that already does our job. |
| Protection modes / policy presets | `ProtectionMode` (referenced in `witness.py` import, `models.py`) and a `COMPLIANCE_TEMPLATE=strict` env knob (README lines 214, 222) tightening encryption/audit/isolation settings. | `controller/app/models.py`, README table around lines 210-222 | No overlap - deployment/compliance postures (encryption at rest, session isolation, audit strictness), not content-safety heuristics. |
| Action verification (`action_verification`, `actions.py` lines 651-730) | Post-action heuristic: did URL/title/active-element/text/DOM-counts change in a way consistent with the claimed action succeeding? | `actions.py` | NO OVERLAP, but related enough to flag. Checks "did clicking do something" after the fact using DOM diffing - not "was the thing I clicked actually the thing I saw" before the fact. Conceptually adjacent (both DOM-diff-flavored, both deterministic/structural rather than LLM-judgment) but solves a different problem (executional success vs. click-target legitimacy) and runs AFTER the click already happened, too late for a guard whose job is to refuse the click. |
| Stealth init script | Anti-bot-detection patches (webdriver flag, plugins, canvas noise, WebGL vendor strings) injected via `add_init_script` (`browser_scripts.py` lines 7-98). | `browser_scripts.py` | No overlap, opposite concern (evading site defenses, not defending the agent from the site). |

Bottom line for the pitch: Auto Browser's safety story is entirely about (a) whether this agent is authorized/should-pause before a self-declared risky action, and (b) proving after the fact what happened - a governance and evidence layer. It has ZERO existing mechanism that inspects the page's actual rendered geometry or CSS to determine whether what the agent perceives matches what a user would perceive. The clickjacking/`elementFromPoint` check and the hidden-text-via-computed-style check are both genuinely absent, not just under-exposed. This is a real, defensible gap, not a rediscovery of something they already ship.

---

## 5. HOW TO RUN IT ON WINDOWS 11

### Docker Compose path (the one the README treats as canonical)

```
git clone https://github.com/LvcidPsyche/auto-browser.git
cd auto-browser
docker compose up --build
```
Requires Docker Desktop (with WSL2 backend) - hard, real dependency: the Dockerfile pins `python:3.11-slim` (per `controller/pyproject.toml` comment) and Makefile targets (`make doctor`, `make test`, `make smoke-isolation`) all shell out to bash scripts under `scripts/` via `./scripts/doctor.sh` etc. - these Makefile targets will NOT run under native PowerShell without Git Bash/WSL providing `bash`/`make`. `docker compose up --build` itself is a plain Docker CLI invocation and works fine from PowerShell once Docker Desktop is installed. After it's up:
- API docs: `http://127.0.0.1:8000/docs`
- Operator dashboard: `http://127.0.0.1:8000/dashboard`
- MCP endpoint: `http://127.0.0.1:8000/mcp`

Optional readiness check (needs bash): `cp .env.example .env` then `make doctor` - run from Git Bash/WSL, not PowerShell directly, per README line 95 ("Run `make doctor` from a normal terminal with local Docker access").

### Native Python path (no Docker) - version constraint that conflicts with the user's stated default

`controller/pyproject.toml` line 12: `requires-python = ">=3.11"`. The user's global default is Python 3.10 unless a project needs otherwise - this project needs otherwise: 3.10 is explicitly incompatible; use the system's Python 3.12 install instead. CI runs 3.11 and 3.14 (README line 54); 3.12 is untested by their own CI but satisfies the version floor. Native run would mean `cd controller && pip install -e .` plus `playwright install chromium` and running the FastAPI app directly (uvicorn) - not documented as a supported path in README/docs (Docker Compose is the only quickstart given), so treat this as UNVERIFIED/AMBIGUOUS: no `uvicorn app.main:app` invocation or equivalent is shown anywhere in the docs read.

### MCP client config snippets

stdio (from `docs/mcp-clients.md` lines 57-75, matches `examples/claude_desktop_config.json` per the doc): the Claude Desktop config points `command` at `uvx`, `args` at `["auto-browser-mcp"]`, with env vars `AUTO_BROWSER_BASE_URL=http://127.0.0.1:8000/mcp` and `AUTO_BROWSER_BEARER_TOKEN` (empty if unauthenticated). Requires `uv`/`uvx` installed (works on Windows). Repo-checkout alternative: point `command` at `python3` (on Windows: the `python` launcher or an explicit `python.exe` path) with `args: ["/ABSOLUTE/PATH/TO/auto-browser/scripts/mcp_stdio_bridge.py"]` - use a Windows-style absolute path.

HTTP - point any MCP-HTTP-capable client directly at `http://127.0.0.1:8000/mcp` (needs the controller already running, e.g. via `docker compose up`); set an `Authorization` bearer header if `AUTO_BROWSER_BEARER_TOKEN`/equivalent is configured (readiness check flags a missing bearer token per `browser.readiness_check`, diagnostics.py lines 24-33).

Set `MCP_TOOL_PROFILE=full` as an environment variable on the controller to get the full tool surface from section 2.

---

## 6. MODEL ADAPTERS - OpenRouter and Gemini confirmed

Confirmed against `controller/app/providers/`:

- `gemini_adapter.py` - a native, dedicated adapter (not the generic OpenAI-compatible one): builds requests to `{gemini_base_url}/models/{model}:generateContent` (line 95) with `responseMimeType: application/json` and `responseJsonSchema` (per `docs/llm-adapters.md` lines 66-70). Config: presumably `GEMINI_API_KEY` / `gemini_base_url` / model settings (exact env var names not confirmed - `Settings` class not opened in this pass; treat as AMBIGUOUS, verify in `controller/app/settings.py` or `.env.example` before relying on the name).
- `openai_compatible.py` - the generic multi-profile adapter (lines ~39-90 define provider profiles as dataclasses: `provider, api_key_attr, base_url_attr, model_attr, env_var`). Confirmed profiles include:
  - `provider="openrouter"`, `api_key_attr="openrouter_api_key"`, `base_url_attr="openrouter_base_url"`, `model_attr="openrouter_model"`, `env_var="OPENROUTER_API_KEY"` (lines 49-54) - this is the native `openrouter` provider the README claims, confirmed in code, not just marketing copy.
  - `xai`, `deepseek`, `minimax`, and a fully generic `openai_compatible` profile (custom `base_url_attr="openai_compatible_base_url"`, line 89) for self-hosted/other endpoints (Ollama, vLLM, LM Studio, Azure, Together, Groq, Fireworks per README line 45).
  - Requests POST to `{base_url}/chat/completions` (line 206) - standard OpenAI-shape function calling with, per README, "a content-parse fallback for endpoints that ignore `tool_choice`."
- `browser.list_providers` (full profile only, `gateway.py::_list_providers` lines 482-483) returns the live `ProviderRegistry` list - the authoritative runtime way to confirm which providers/models are actually configured in a given deployment, rather than trusting static code.

Practical implication for this project: since we have OpenRouter and Gemini keys (not OpenAI), both are first-class, natively-named providers here - no shimming needed. Set `OPENROUTER_API_KEY` (and optionally `openrouter_model`/`openrouter_base_url` overrides) for OpenRouter, and whatever Gemini-specific env var `gemini_adapter.py`'s `Settings` binding actually names (verify before use - flagged as ambiguous above) for Gemini.

---

## Ambiguities flagged (do not treat as resolved)

1. Exact `Settings` field/env-var names backing `gemini_base_url`, `gemini_api_key`, `openrouter_base_url` defaults were not verified against `controller/app/settings.py` - only their usage sites were read.
2. Native (non-Docker) run path is not documented anywhere in README/docs; the only verified run path is `docker compose up --build`. Treat manual `uvicorn`/`pip install -e .` instructions above as inferred, not confirmed against a working example in the repo.
3. `harness.py` pack contents (harness.* tool descriptions/params) were not read in full - only cross-referenced via docs and grep. If harness tools matter to the pitch, read `controller/app/tool_gateway/packs/harness.py` before citing exact parameters.
4. `controller/app/approvals.py`, `controller/app/events.py`, and `controller/app/pii/*` were referenced but not opened - statements about their exact behavior are inferred from call sites in `gateway.py`/`actions.py`/`witness.py`, not from their own source.
5. Whether a real deployment can configure an "auto-approve" identity for `governed`-gated tools like `eval_js` (needed to make the external-proxy guard practical without a human in the loop for every click) was not confirmed - `approvals.py` was not read. This is the single most important follow-up for the integration plan in INTEGRATION.md.
