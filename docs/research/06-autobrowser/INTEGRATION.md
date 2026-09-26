# Auto Browser — Guard Integration Recommendation

Short architecture doc. Full evidence/citations are in FINDINGS.md in this same directory.

## The one-sentence answer

Auto Browser has no clickjacking/dark-pattern defense today, and its click path (controller/app/browser/services/actions.py::click(), line 61) actually bypasses Playwright's own actionability/hit-test check by doing raw mouse.move/down/up at a getBoundingClientRect()-derived coordinate — so our guard is filling a real, currently-open gap, not duplicating anything. Build it as a standalone MCP interceptor that wraps tool_gateway/gateway.py::McpToolGateway.call_tool(), with no fork of the repo.

## Ranked interception points

1. Gateway-level wrapper around McpToolGateway.call_tool() [RECOMMENDED, no fork]
   - Every MCP client call (HTTP or stdio-bridged) funnels through this single method (controller/app/tool_gateway/gateway.py, lines 144-242) before the tool handler runs.
   - At interception time we have: fully-validated Pydantic arguments (so for browser.execute_action with action="click"/"hover", or browser.drag_drop, we already have selector/element_id/x/y), the session_id, and manager access to run our own page.evaluate() for a hit-test/style read.
   - Implementation shape: a small Python class that holds a reference to the real McpToolGateway, exposes the same call_tool(payload) signature, and either (a) proxies straight through for non-geometric tools, or (b) for click-shaped tools, first resolves the target's intended element + coordinates, calls a new observation method (see "New capability needed" below) to hit-test, and returns an McpToolCallResponse(isError=True, ...) in the same shape the gateway already uses if the hit-test fails — otherwise delegates to the real call_tool().
   - This can literally sit in front of the HTTP layer (a tiny ASGI middleware or a substitute McpToolGateway instance wired into app startup) or, if the team controls the process that starts the controller, as a one-line dependency-injection swap. Neither requires touching gateway.py's source.
   - Residual gap: this happens right before dispatch, not at the exact instant of the mouse event deep in actions.py::click_human_like(). In practice the window between "gateway validates" and "mouse.down() fires" is milliseconds and single-threaded per session (session.lock), so this is a low-risk gap, but it's not zero. If the team is later willing to accept a tiny, well-isolated patch to actions.py (not a fork of surrounding logic, just adding one guard call inside click()/hover()), that would close it completely. Recommend treating this as a stretch goal / potential upstream PR, not a blocker for v1.

2. mesh/policy.py::PolicyEvaluator.evaluate() — REJECTED as the primary point.
   - This is a peer-to-peer capability-delegation system for cross-agent/cross-node grants (rate limits, URL allowlists, expiry), invoked only from controller/app/routes/extensions/mesh.py. It is not on the code path of a normal MCP client's POST /mcp -> call_tool(), so it cannot see per-click page geometry and would require rerouting the whole normal call path through the mesh subsystem to use it — a much bigger change than wrapping call_tool() directly.

3. External proxy MCP server in front of http://127.0.0.1:8000/mcp — good complementary layer, not sufficient alone.
   - Zero coupling to Auto Browser internals, portable across other MCP browser servers, easy to deploy/version independently.
   - But it has no direct Playwright page handle — to run elementFromPoint()/getComputedStyle() it would have to call back into the controller via browser.eval_js (which is approval-gated per FINDINGS.md section 1a) or a new dedicated tool we add server-side anyway. So a pure external proxy still depends on the "new capability" work below; it just relocates where the interception logic lives. Useful for coarse allow/deny lists and centralized logging across multiple backend MCP servers, but the hit-test itself still needs a page-side hook.

4. stdio bridge (scripts/mcp_stdio_bridge.py / uvx auto-browser-mcp) — same limitation as #3, narrower reach (stdio-only clients). Not recommended as the primary point.

## New capability needed (regardless of interception point)

Add one new observation method, following the codebase's existing page.evaluate(SCRIPT, args) idiom (see INTERACTABLES_SCRIPT in controller/app/browser_scripts.py:101-161 as the template):

- hit_test(x, y) -> calls document.elementFromPoint(x, y) in-page, walks el.parentElement to build an ancestry chain, and returns whether a given expected element (by its stamped data-operator-id, the same mechanism INTERACTABLES_SCRIPT already uses) is the returned element or one of its ancestors/descendants.
- style_probe(selector or element_id) -> returns opacity, computed font-size, color, background-color, clip-path, and actual rendered size for a given element, WITHOUT pre-filtering invisible elements the way INTERACTABLES_SCRIPT's isVisible() does today (browser_scripts.py:104-108) — we want the invisible/near-invisible ones surfaced, not silently dropped.

Both can be exposed as either (a) internal helper methods called only by our gateway-wrapper guard (not exposed to the agent as MCP tools at all — the cleanest, most tamper-resistant option, since the agent never gets to invoke or spoof the hit-test itself), or (b) new curated MCP tools (e.g. browser.hit_test) if the team wants them agent-visible for other purposes too. Recommend (a) for the guard's own internal use — the guard should not trust anything it did not compute itself.

## Where to report findings

Auto Browser already has a purpose-built schema for exactly this: WitnessConcern (controller/app/witness.py: code/severity/summary/enforced/details), part of the signed, hash-chained Witness evidence system (witness_signing.py, witness_anchor.py) with existing MCP tools browser.verify_witness / browser.export_witness_bundle. Nothing populates a WitnessConcern from DOM/geometry checks today (see FINDINGS.md section 4) — it's empty, ready-made extension surface. Recommend the guard emit WitnessConcern-shaped records (e.g. code="hit_test_mismatch" or "hidden_text_detected", severity="critical", enforced=True) plus a plain audit.append() call (controller/app/audit.py, the same sink observation.py already uses for pii_redaction events) rather than inventing a new reporting channel.

## What NOT to duplicate

- Approval gates (controller/app/approvals.py) — a human-consent workflow keyed on the agent's self-declared risk category. Orthogonal to us; keep it, our guard runs regardless of whether an action is "governed" or not.
- PII scrubbing (manager.pii_scrubber) — protects outbound screenshot privacy. Unrelated.
- Protection profiles / COMPLIANCE_TEMPLATE — session lifecycle/isolation hygiene. Unrelated.
- Rate limiting (controller/app/rate_limits.py) — generic throttling. Unrelated, but our guard's block events could feed a rate-limit-like circuit breaker later if desired (not needed for v1).

## Concrete next steps

1. Confirm the exact process boundary the team wants: (a) a Python object wrapping McpToolGateway inside the same process (fastest, needs the controller startup wiring to accept a substitute gateway instance — check controller/app/main.py / wherever McpToolGateway is instantiated), or (b) a fully separate reverse-proxy process in front of port 8000 (cleaner isolation, works even against a stock unmodified Auto Browser install, small latency cost).
2. Implement style_probe and hit_test as internal-only async functions colocated with the guard (they do not need to be registered ToolSpecs at all — they just need an event loop with access to the session's Playwright Page object, which the guard already needs to reach one way or another).
3. Implement the guard's decision logic (the actual geometry/style rules: hit-test mismatch => block; opacity/clip-path/font-size heuristics => flag or block per the team's existing detection design from the other research tracks in this project).
4. Wire guard decisions into audit.append() and (optionally, if the team decides it's worth the coupling) a WitnessConcern-shaped payload.
5. Validate end-to-end on Windows 11 using Python 3.12 (NOT 3.10 — controller/pyproject.toml requires >=3.11) per the run instructions in FINDINGS.md section 5, with OPENROUTER_API_KEY and/or GEMINI_API_KEY set for the underlying agent provider.
6. Treat an actions.py::click()/hover() patch (adding the same elementFromPoint check right at the mouse-event call site) as an optional hardening step / potential upstream contribution, not a v1 requirement, given the "no forking" preference.
