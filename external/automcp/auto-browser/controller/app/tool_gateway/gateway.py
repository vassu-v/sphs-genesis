from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from ..action_errors import BrowserActionError
from ..approvals import ApprovalRequiredError
from ..live.calls import LiveCall
from ..models import (
    BrowserActionDecision,
    McpToolCallContent,
    McpToolCallRequest,
    McpToolCallResponse,
)
from ..readiness import run_readiness_checks
from ..tool_inputs import (
    AgentJobIdInput,
    ApprovalDecisionInput,
    ApprovalIdInput,
    AuthProfileNameInput,
    CdpAttachInput,
    CreateCronJobInput,
    CreateProxyPersonaInput,
    CreateSessionRequest,
    CronJobIdInput,
    DeleteMemoryProfileInput,
    DragDropInput,
    EmptyInput,
    EvalJsInput,
    ExecuteActionInput,
    ExportScriptInput,
    FindElementsInput,
    ForkSessionInput,
    GetCookiesInput,
    GetMemoryProfileInput,
    GetNetworkLogInput,
    GetPageHtmlInput,
    GetRemoteAccessInput,
    GetStorageInput,
    HarnessGetStatusInput,
    HarnessGetTraceInput,
    HarnessGraduateInput,
    HarnessListRunsInput,
    HarnessSkillIdInput,
    HarnessStartConvergenceInput,
    ListAgentJobsInput,
    ListApprovalsInput,
    ListAuthProfilesInput,
    ListDownloadsInput,
    ListTabsInput,
    ObserveInput,
    ProxyPersonaNameInput,
    QueueAgentRunInput,
    QueueAgentStepInput,
    ReadinessCheckInput,
    ResumeAgentJobInput,
    SaveAuthProfileInput,
    SaveAuthStateInput,
    SaveMemoryProfileInput,
    ScreenshotInput,
    SessionIdInput,
    SessionTailInput,
    SetCookiesInput,
    SetStorageInput,
    SetViewportInput,
    ShadowBrowseInput,
    ShareSessionInput,
    SnapshotInput,
    TabActionInput,
    TakeoverInput,
    VerifyWitnessInput,
    VisionFindInput,
    WaitForSelectorInput,
)
from .packs import register_all
from .registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

# Bound on the in-page text walk for find_elements' query mode — a
# catastrophically backtracking regex would otherwise hang page.evaluate
# (and the session) indefinitely.
FIND_ELEMENTS_QUERY_TIMEOUT_SECONDS = 10.0

# Tools allowed to create a session on demand when session_id is omitted and no
# session is live — the first call an agent makes is almost always one of these.
# Everything else resolves an omitted session_id only when exactly one session
# is live; creating a session as a side effect of, say, close_tab helps nobody.
IMPLICIT_SESSION_CREATE_TOOLS = frozenset(
    {
        "browser.execute_action",
        "browser.observe",
        "browser.find_elements",
        "browser.screenshot",
        "browser.get_html",
        "browser.snapshot",
        "browser.wait_for_selector",
    }
)

# ── S.H.O.A.V. gateway hooks (owner: C-3/C-4/C-5) ──────────────────────────
# v1 scope: ingress rewrites for observe/snapshot/find_elements/get_html,
# egress hit-test for execute_action click + drag_drop coordinates, post-hoc
# type/submit checks with per-session touched tracking.
#
# NOT gated in v1 (documented gaps, see plan.md section 5): browser.eval_js
# (arbitrary JS bypasses the click path on purpose for probes), upload
# (file path handling), navigate (only resets guard state, never blocked),
# hover (no click dispatched), vision clicks (browser.find_by_vision returns
# coordinates the agent clicks later without a ref), and non-MCP callers of
# manager.execute_decision (later hardening moves egress into actions click).
SHOAV_INGRESS_TOOLS = frozenset(
    {
        "browser.observe",
        "browser.snapshot",
        "browser.find_elements",
        "browser.get_html",
    }
)
SHOAV_INGRESS_HEADER = "[S.H.O.A.V. INGRESS SHIELD]"

# Fallback JS probes used only when the shoav filter package is not
# importable. Kept in sync with shoav-mcp/filters/egress/scripts.py.
_SHOAV_FOCUS_CHECK_SCRIPT = """
(() => {
    const el = document.activeElement;
    if (!el) return { found: false };
    return {
        found: true,
        tag: el.tagName,
        ref: el.getAttribute('data-operator-id'),
        type: el.type || null,
        value: el.value !== undefined ? el.value : null,
    };
})()
"""


def _shoav_hit_test_script(cx: float, cy: float, expected_ref: str | None = None) -> str:
    import json as _json

    ref_js = _json.dumps(expected_ref) if expected_ref is not None else "null"
    return f"""
    (() => {{
        const topEl = document.elementFromPoint({cx}, {cy});
        if (!topEl) return {{ found: false }};
        const style = window.getComputedStyle(topEl);
        const expectedRef = {ref_js};
        let insideTarget = null;
        if (expectedRef !== null) {{
            const target = Array.from(document.querySelectorAll('[data-operator-id]'))
                .find(e => e.getAttribute('data-operator-id') === expectedRef);
            insideTarget = target ? target.contains(topEl) : false;
        }}
        return {{
            found: true,
            inside_target: insideTarget,
            tag: topEl.tagName,
            ref: topEl.getAttribute('data-operator-id'),
            opacity: parseFloat(style.opacity),
            z_index: style.zIndex,
            pointer_events: style.pointerEvents,
        }};
    }})()
    """


def _shoav_selector_hit_test_script(cx: float, cy: float, selector: str) -> str:
    import json as _json

    sel_js = _json.dumps(selector)
    return f"""
    (() => {{
        const topEl = document.elementFromPoint({cx}, {cy});
        if (!topEl) return {{ found: false }};
        const style = window.getComputedStyle(topEl);
        let insideTarget = null;
        try {{
            const target = document.querySelector({sel_js});
            insideTarget = target ? target.contains(topEl) : false;
        }} catch (e) {{
            insideTarget = false;
        }}
        return {{
            found: true,
            inside_target: insideTarget,
            tag: topEl.tagName,
            ref: topEl.getAttribute('data-operator-id'),
            opacity: parseFloat(style.opacity),
            z_index: style.zIndex,
            pointer_events: style.pointerEvents,
        }};
    }})()
    """


class McpToolGateway:
    def __init__(
        self,
        *,
        manager,
        orchestrator,
        job_queue,
        tool_profile: str = "curated",
        cron_service=None,
        share_manager=None,
        proxy_store=None,
        vision_targeter=None,
        harness_service=None,
        metrics=None,
        live_view=None,
        guard=None,
    ):
        self.manager = manager
        self.live_view = live_view
        self.orchestrator = orchestrator
        self.job_queue = job_queue
        self.guard = guard
        # Per-session guard memory (C-5): touched refs, interactables cache
        # for submit-control detection, initial form snapshot, last origin+path.
        self._shoav_sessions: dict[str, dict[str, Any]] = {}
        # Unknown values fall back to curated (same rule as ToolRegistry).
        normalized_profile = (tool_profile or "").strip().lower()
        self.tool_profile = (
            normalized_profile if normalized_profile in ("minimal", "curated", "full") else "curated"
        )
        self.cron_service = cron_service
        self.share_manager = share_manager
        self.proxy_store = proxy_store
        self.vision_targeter = vision_targeter
        self.harness_service = harness_service
        self.metrics = metrics
        self._registry = ToolRegistry(
            tool_profile=self.tool_profile,
            experimental_enabled=self._experimental_enabled,
            name_style=getattr(getattr(manager, "settings", None), "mcp_tool_name_style", "dotted"),
        )
        register_all(self._registry, self)
        if self.vision_targeter is None:
            self._registry.unregister("browser.find_by_vision")
        self._tools = self._registry.tools

    def _experimental_enabled(self, name: str | None) -> bool:
        return name is None

    def list_tools(self) -> list[dict[str, Any]]:
        return self._registry.list_tools()

    async def call_tool(self, payload: McpToolCallRequest) -> McpToolCallResponse:
        started = time.perf_counter()
        known_spec = self._registry.get(payload.name)
        # Metrics, phases and the timeline use the canonical dotted name whichever spelling
        # the client sent (browser_observe and browser.observe are the same tool).
        canonical_name = known_spec.name if known_spec is not None else payload.name
        metric_tool = canonical_name if known_spec is not None else "__unknown__"
        status = "error"
        live_call = LiveCall(self.live_view, self.manager, canonical_name, payload.arguments) if self.live_view else None
        try:
            try:
                response = await self._call_tool(payload, live_call)
            except BaseException:
                # Cancellation or a bug escaping _call_tool: still close the timeline entry.
                if live_call is not None:
                    # shield: a second cancel must not lose the end event
                    await asyncio.shield(
                        live_call.finish(self._error_response("Tool call aborted"), error="Tool call aborted")
                    )
                raise
            if live_call is not None:
                response = await asyncio.shield(live_call.finish(response))
            if response._omit_structured:
                response.structuredContent = None
            status = "error" if response.isError else "ok"
            duration_seconds = time.perf_counter() - started
            response.meta = self._tool_response_meta(
                existing=response.meta,
                tool=metric_tool,
                status=status,
                duration_seconds=duration_seconds,
            )
            return response
        finally:
            if self.metrics is not None:
                duration_seconds = time.perf_counter() - started
                try:
                    self.metrics.record_mcp_tool_call(
                        tool=metric_tool,
                        status=status,
                        duration_seconds=duration_seconds,
                    )
                except Exception:
                    logger.warning("failed to record MCP tool metrics for %s", metric_tool, exc_info=True)

    async def _call_tool(self, payload: McpToolCallRequest, live_call: LiveCall | None = None) -> McpToolCallResponse:
        spec = self._registry.get(payload.name)
        if spec is None:
            return self._error_response(f"Unknown tool: {payload.name}")

        try:
            raw_arguments = dict(payload.arguments or {})
            policy_profile = self._pop_policy_profile(spec, raw_arguments)
            policy_approval_id = self._pop_policy_approval_id(spec, raw_arguments)
            if spec.name == "browser.eval_js" and policy_profile != "governed":
                return self._error_response("browser.eval_js requires workflow_profile=governed")
            if (
                spec.name == "harness.start_convergence"
                and raw_arguments.get("session_id")
                and raw_arguments.get("mock_final_observation") is None
                and policy_profile != "governed"
            ):
                return self._error_response(
                    "harness.start_convergence with a live session requires workflow_profile=governed"
                )
            if spec.name.startswith("harness.") and self.harness_service is None:
                return self._error_response(
                    "harness service unavailable - check controller startup logs and HARNESS_* config"
                )
            arguments = spec.input_model.model_validate(raw_arguments)
            arguments = await self._resolve_implicit_session(spec, arguments, live_call)
            if live_call is not None:
                await live_call.begin(getattr(arguments, "session_id", None))
            approval = await self._require_governed_tool_approval(
                spec,
                arguments,
                workflow_profile=policy_profile,
                approval_id=policy_approval_id,
            )
            egress_block = await self._shoav_egress_check(spec, arguments, live_call)
            if egress_block is not None:
                return egress_block
            result = await spec.handler(arguments)
            if approval is not None:
                await self.manager.approvals.mark_executed(approval.id)
            posthoc_block = await self._shoav_posthoc_check(spec, arguments, result, live_call)
            if posthoc_block is not None:
                return posthoc_block
            if isinstance(result, dict):
                ingress_block = await self._shoav_ingress_check(spec, arguments, result, live_call)
                if ingress_block is not None:
                    return ingress_block
            structured, content = self._pack_result(result)
            response = McpToolCallResponse(content=content, structuredContent=structured, isError=False)
            response._omit_structured = isinstance(result, dict) and isinstance(result.get("_mcp_text"), str)
            return response
        except ApprovalRequiredError as exc:
            detail = exc.payload
            return McpToolCallResponse(
                content=[McpToolCallContent(text=json.dumps(detail, ensure_ascii=False))],
                structuredContent=detail,
                isError=True,
            )
        except BrowserActionError as exc:
            detail = exc.payload
            return McpToolCallResponse(
                content=[McpToolCallContent(text=json.dumps(detail, ensure_ascii=False))],
                structuredContent=detail,
                isError=True,
            )
        except ValidationError as exc:
            # Invalid tool arguments — report the field errors so the calling
            # agent can fix its call, instead of "Tool execution failed".
            details = "; ".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" if err.get("loc") else err["msg"]
                for err in exc.errors()
            )
            return self._error_response(f"Invalid arguments for {payload.name}: {details}")
        except (ValueError, KeyError, RuntimeError) as exc:
            # Handlers raise these with operator-facing messages ("Provide
            # source_selector or source_x/source_y", "Memory profile not found").
            # Surface them so the calling agent can self-correct, instead of
            # collapsing them into the opaque catch-all below.
            message = str(exc.args[0]) if exc.args else exc.__class__.__name__
            return self._error_response(message)
        except Exception:
            logger.exception("tool %s failed", payload.name)
            return self._error_response("Tool execution failed")

    @staticmethod
    def _pack_result(result: Any) -> tuple[Any, list[McpToolCallContent]]:
        """Split a handler result into structuredContent and MCP content blocks.

        Handlers may put two private keys in a dict result: `_mcp_images` (image blocks,
        base64) and `_mcp_text` (plain text that replaces the JSON dump as content[0]).
        Both are removed from structuredContent, so base64 and bulky text are never
        duplicated there or recorded by the live view. content[0] stays a text block.
        """
        if not isinstance(result, dict) or not ("_mcp_images" in result or "_mcp_text" in result):
            return result, [McpToolCallContent(text=json.dumps(result, ensure_ascii=False))]
        structured = {k: v for k, v in result.items() if k not in ("_mcp_images", "_mcp_text")}
        text = result.get("_mcp_text")
        first = text if isinstance(text, str) else json.dumps(structured, ensure_ascii=False)
        content = [McpToolCallContent(text=first)]
        for block in result.get("_mcp_images") or []:
            content.append(McpToolCallContent(type="image", data=block["data"], mimeType=block["mimeType"]))
        return structured, content

    @staticmethod
    def _error_response(message: str) -> McpToolCallResponse:
        return McpToolCallResponse(
            content=[McpToolCallContent(text=message)],
            structuredContent={"error": message},
            isError=True,
        )

    # ── S.H.O.A.V. hooks (C-3 ingress, C-4 egress, C-5 post-hoc) ──────────

    def _shoav_mode(self) -> str:
        if self.guard is None:
            return "off"
        mode = getattr(self.guard, "mode", None)
        if mode is None:
            mode = os.getenv("SHOAV_GUARD_MODE", "observe")
        mode = str(mode).strip().lower()
        return mode if mode in ("off", "observe", "enforce") else "observe"

    @staticmethod
    def _shoav_fail_closed() -> bool:
        return os.getenv("SHOAV_GUARD_FAIL", "open").strip().lower() == "closed"

    def _shoav_state(self, session_id: str | None) -> dict[str, Any]:
        key = session_id or "__no_session__"
        state = self._shoav_sessions.get(key)
        if state is None:
            state = {
                "touched": set(),
                "interactables": [],
                "form_snapshot": None,
                "last_origin_path": None,
            }
            self._shoav_sessions[key] = state
        return state

    def _shoav_reset(self, session_id: str | None) -> None:
        self._shoav_sessions.pop(session_id or "__no_session__", None)

    @staticmethod
    def _shoav_origin_path(url: Any) -> str | None:
        if not isinstance(url, str) or not url:
            return None
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
        except Exception:
            return None

    def _shoav_note_navigation(self, session_id: str | None, url: Any) -> None:
        if not session_id or not url:
            return
        current = self._shoav_origin_path(url)
        if current is None:
            return
        state = self._shoav_state(session_id)
        previous = state.get("last_origin_path")
        if previous is None:
            state["last_origin_path"] = current
            return
        if previous != current:
            kept_url = current
            self._shoav_reset(session_id)
            self._shoav_state(session_id)["last_origin_path"] = kept_url

    async def _shoav_emit(
        self,
        live_call: LiveCall | None,
        *,
        stage: str,
        tool: str,
        verdict: str,
        reason: str,
        findings: Any = None,
        target: dict[str, Any] | None = None,
        enforced: bool = False,
    ) -> None:
        try:
            if live_call is None:
                return
            emit = getattr(live_call, "guard", None)
            if not callable(emit):
                return
            payload: dict[str, Any] = {
                "stage": stage,
                "tool": tool,
                "verdict": verdict,
                "reason": reason,
                "enforced": enforced,
            }
            if findings is not None:
                payload["findings"] = findings
            if target is not None:
                payload["target"] = target
            result = emit(payload)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.warning("shoav guard event emit failed", exc_info=True)

    @staticmethod
    def _shoav_verdict_str(decision: Any) -> str:
        verdict = None
        if isinstance(decision, dict):
            verdict = decision.get("verdict")
        else:
            verdict = getattr(decision, "verdict", None)
        text = str(getattr(verdict, "value", verdict) or "ALLOW").strip().upper()
        return text if text in ("ALLOW", "REWRITE", "BLOCK", "ESCALATE") else "ALLOW"

    @staticmethod
    def _shoav_reason(decision: Any, default: str) -> str:
        if isinstance(decision, dict):
            for key in ("reason", "summary", "telemetry"):
                value = decision.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:2000]
        else:
            for key in ("reason", "summary", "telemetry"):
                value = getattr(decision, key, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:2000]
        return default

    @staticmethod
    def _shoav_findings(decision: Any) -> Any:
        if isinstance(decision, dict):
            findings = decision.get("findings")
            if isinstance(findings, dict):
                count = 0
                for value in findings.values():
                    if isinstance(value, list):
                        count += len(value)
                return {"count": count, "groups": sorted(findings.keys())}
            if isinstance(findings, list):
                return {"count": len(findings)}
            return {"count": 0}
        findings = getattr(decision, "findings", None)
        if isinstance(findings, list):
            return {"count": len(findings)}
        return {"count": 0}

    def _shoav_block_response(
        self, reason: str, *, tool: str, stage: str, verdict: str, findings: Any = None
    ) -> McpToolCallResponse:
        detail = {"error": reason, "shoav": {"tool": tool, "stage": stage, "verdict": verdict}}
        if findings is not None:
            detail["shoav"]["findings"] = findings
        text = json.dumps(detail, ensure_ascii=False)
        return McpToolCallResponse(
            content=[McpToolCallContent(text=text)],
            structuredContent={"error": reason, "shoav": detail["shoav"]},
            isError=True,
        )

    # -- C-3 ingress ------------------------------------------------------

    async def _shoav_ingress_check(
        self, spec: Any, arguments: Any, result: dict[str, Any], live_call: LiveCall | None
    ) -> McpToolCallResponse | None:
        mode = self._shoav_mode()
        if mode == "off" or spec.name not in SHOAV_INGRESS_TOOLS:
            return None
        if spec.name == "browser.observe" and getattr(arguments, "preset", None) == "fast":
            return None
        try:
            payload = await self._shoav_build_ingress_payload(spec.name, arguments, result)
            if payload is None:
                return None
            decision = await self._shoav_run_ingress(payload)
            if decision is None:
                return None
            verdict = self._shoav_verdict_str(decision)
            reason = self._shoav_reason(decision, f"ingress {verdict.lower()} for {spec.name}")
            findings = self._shoav_findings(decision)
            session_id = getattr(arguments, "session_id", None)
            if spec.name == "browser.observe" and isinstance(result.get("interactables"), list):
                state = self._shoav_state(session_id)
                state["interactables"] = result["interactables"]
                if state.get("form_snapshot") is None:
                    state["form_snapshot"] = self._shoav_form_snapshot(result)
                self._shoav_note_navigation(session_id, result.get("url"))
            enforced = mode == "enforce" and verdict in ("REWRITE", "BLOCK")
            await self._shoav_emit(
                live_call, stage="ingress", tool=spec.name, verdict=verdict,
                reason=reason, findings=findings, enforced=enforced,
            )
            if mode == "observe" or verdict == "ALLOW":
                if verdict != "ALLOW":
                    note = {"verdict": verdict, "summary": reason, "enforced": False}
                    if isinstance(findings, dict):
                        note["findings"] = findings.get("count", 0)
                    result["_shoav"] = note
                return None
            if verdict == "BLOCK":
                return self._shoav_block_response(
                    reason, tool=spec.name, stage="ingress", verdict=verdict, findings=findings,
                )
            if verdict == "REWRITE":
                self._shoav_apply_rewrite(spec.name, result, decision, reason, findings)
            return None
        except Exception as exc:
            logger.warning("shoav ingress hook failed for %s: %s", spec.name, exc, exc_info=True)
            await self._shoav_emit(
                live_call, stage="ingress", tool=spec.name, verdict="ALLOW",
                reason=f"guard error, failed open: {exc}", enforced=False,
            )
            if self._shoav_fail_closed():
                return self._shoav_block_response(
                    f"Guard unavailable, failing closed: {exc}",
                    tool=spec.name, stage="ingress", verdict="BLOCK",
                )
            return None

    async def _shoav_build_ingress_payload(
        self, tool: str, arguments: Any, result: dict[str, Any]
    ) -> dict[str, Any] | None:
        if tool == "browser.observe":
            ocr = result.get("ocr") or {}
            ocr_text = ""
            if isinstance(ocr, dict):
                blocks = ocr.get("blocks") or []
                parts = []
                for block in blocks:
                    if isinstance(block, dict):
                        for key in ("text", "content"):
                            if block.get(key):
                                parts.append(str(block[key]))
                                break
                    elif isinstance(block, str):
                        parts.append(block)
                ocr_text = " ".join(parts)
                if not ocr_text and isinstance(ocr.get("text"), str):
                    ocr_text = ocr["text"]
            payload = {
                "tool": tool,
                "interactables": result.get("interactables") or [],
                "text_excerpt": result.get("text_excerpt") or "",
                "ocr_text": ocr_text,
                "accessibility_outline": result.get("accessibility_outline") or {},
            }
            style_facts = await self._shoav_style_facts(getattr(arguments, "session_id", None))
            if style_facts is not None:
                payload["style_facts"] = style_facts
            return payload
        if tool == "browser.snapshot":
            text = result.get("_mcp_text")
            if not isinstance(text, str):
                return None
            return {"tool": tool, "text": text}
        if tool == "browser.find_elements":
            elements = result.get("elements") or []
            parts = []
            if isinstance(elements, list):
                for el in elements:
                    if isinstance(el, dict):
                        for key in ("text", "context_text", "match"):
                            value = el.get(key)
                            if value:
                                parts.append(str(value))
            return {"tool": tool, "text": "\n".join(parts), "elements": elements}
        if tool == "browser.get_html":
            content = result.get("content")
            if not isinstance(content, str):
                return None
            return {"tool": tool, "text": content}
        return None

    async def _shoav_style_facts(self, session_id: str | None) -> list[dict] | None:
        if not session_id:
            return None
        try:
            from shoav_mcp.filters.ingress.scripts import STYLE_PROBE_SCRIPT as _probe
        except Exception:
            try:
                from filters.ingress.scripts import STYLE_PROBE_SCRIPT as _probe  # type: ignore
            except Exception:
                return None
        try:
            session = await self.manager.get_session(session_id)
            facts = await session.page.evaluate(_probe)
            return facts if isinstance(facts, list) else None
        except Exception:
            return None

    @staticmethod
    def _shoav_form_snapshot(result: dict[str, Any]) -> list[dict]:
        nodes = ((result.get("accessibility_outline") or {}).get("nodes")) or []
        snapshot = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            role = node.get("role")
            if role not in ("checkbox", "switch"):
                continue
            snapshot.append(
                {
                    "ref": node.get("name") or node.get("description") or role,
                    "type": role,
                    "checked": node.get("checked"),
                    "label": node.get("name") or node.get("description"),
                }
            )
        return snapshot

    async def _shoav_run_ingress(self, payload: dict[str, Any]) -> Any | None:
        decide = getattr(self.guard, "decide_ingress", None)
        if callable(decide):
            outcome = decide(payload)
            if asyncio.iscoroutine(outcome):
                outcome = await outcome
            return outcome
        try:
            from shoav_mcp.filters.ingress.engine import IngressFilter as _IngressFilter
        except Exception:
            try:
                from filters.ingress.engine import IngressFilter as _IngressFilter  # type: ignore
            except Exception:
                return None
        style_facts = payload.get("style_facts")
        engine_payload = {
            "interactables": payload.get("interactables", []),
            "text_excerpt": payload.get("text_excerpt", payload.get("text", "")),
            "accessibility_outline": payload.get("accessibility_outline", {}),
        }
        outcome = _IngressFilter().process(engine_payload, style_facts=style_facts)
        return {
            "verdict": outcome.get("verdict"),
            "findings": outcome.get("findings"),
            "sanitized": outcome.get("payload"),
            "telemetry": outcome.get("telemetry"),
        }

    def _shoav_apply_rewrite(
        self, tool: str, result: dict[str, Any], decision: Any, reason: str, findings: Any
    ) -> None:
        sanitized: Any = None
        if isinstance(decision, dict):
            sanitized = decision.get("sanitized")
            if sanitized is None and isinstance(decision.get("payload"), dict):
                sanitized = decision["payload"]
        else:
            sanitized = getattr(decision, "sanitized", None)
        telemetry = reason if isinstance(reason, str) else SHOAV_INGRESS_HEADER
        if tool == "browser.snapshot" and isinstance(result.get("_mcp_text"), str):
            clean = result["_mcp_text"]
            if isinstance(sanitized, str):
                clean = sanitized
            elif isinstance(sanitized, dict) and isinstance(sanitized.get("_mcp_text"), str):
                clean = sanitized["_mcp_text"]
            elif isinstance(sanitized, dict) and isinstance(sanitized.get("text"), str):
                clean = sanitized["text"]
            header = telemetry.splitlines()[0] if telemetry else SHOAV_INGRESS_HEADER
            result["_mcp_text"] = f"{header}\n{clean}"
        elif tool == "browser.get_html" and isinstance(result.get("content"), str):
            if isinstance(sanitized, str):
                result["content"] = sanitized
            elif isinstance(sanitized, dict):
                for key in ("content", "text", "sanitized"):
                    if isinstance(sanitized.get(key), str):
                        result["content"] = sanitized[key]
                        break
        elif tool == "browser.observe":
            if isinstance(sanitized, dict):
                if isinstance(sanitized.get("interactables"), list):
                    result["interactables"] = sanitized["interactables"]
                if isinstance(sanitized.get("text_excerpt"), str):
                    result["text_excerpt"] = sanitized["text_excerpt"]
        elif tool == "browser.find_elements":
            if isinstance(sanitized, dict) and isinstance(sanitized.get("elements"), list):
                result["elements"] = sanitized["elements"]
        note: dict[str, Any] = {"verdict": "REWRITE", "summary": reason, "enforced": True}
        if isinstance(findings, dict):
            note["findings"] = findings.get("count", 0)
        reordered = {"_shoav": note}
        reordered.update(result)
        result.clear()
        result.update(reordered)

    # -- C-4 egress -------------------------------------------------------

    async def _shoav_egress_check(
        self, spec: Any, arguments: Any, live_call: LiveCall | None
    ) -> McpToolCallResponse | None:
        mode = self._shoav_mode()
        if mode == "off":
            return None
        try:
            if spec.name == "browser.execute_action":
                decision = getattr(arguments, "action", None)
                if decision is None or getattr(decision, "action", None) != "click":
                    return None
                return await self._shoav_click_check(arguments, decision, live_call, mode)
            if spec.name == "browser.drag_drop":
                return await self._shoav_drag_check(arguments, live_call, mode)
            return None
        except Exception as exc:
            logger.warning("shoav egress hook failed: %s", exc, exc_info=True)
            await self._shoav_emit(
                live_call, stage="egress", tool=spec.name, verdict="ALLOW",
                reason=f"guard error, failed open: {exc}", enforced=False,
            )
            if self._shoav_fail_closed():
                return self._shoav_block_response(
                    f"Guard unavailable, failing closed: {exc}",
                    tool=spec.name, stage="egress", verdict="BLOCK",
                )
            return None

    async def _shoav_click_check(
        self, arguments: Any, decision: Any, live_call: LiveCall | None, mode: str
    ) -> McpToolCallResponse | None:
        session_id = getattr(arguments, "session_id", None)
        element_id = getattr(decision, "element_id", None)
        selector = getattr(decision, "selector", None)
        x = getattr(decision, "x", None)
        y = getattr(decision, "y", None)
        target = {"element_id": element_id} if element_id else ({"selector": selector} if selector else {"x": x, "y": y})
        if element_id:
            probe = await self._shoav_probe_element_id(session_id, element_id)
        elif selector and (x is None or y is None):
            probe = await self._shoav_probe_selector(session_id, selector)
        elif x is not None and y is not None:
            probe = await self._shoav_probe_coords(session_id, float(x), float(y), None)
        else:
            return None
        if probe is None:
            return None
        verdict, reason = await self._shoav_decide_click(
            expected_ref=element_id, hit=probe["hit"], selector_only=probe["selector_only"],
            coord_only=probe["coord_only"],
        )
        enforced = mode == "enforce" and verdict in ("BLOCK", "ESCALATE")
        await self._shoav_emit(
            live_call, stage="egress", tool="browser.execute_action", verdict=verdict,
            reason=reason, target=target, enforced=enforced,
        )
        if verdict in ("BLOCK", "ESCALATE") and mode == "enforce":
            if verdict == "ESCALATE":
                reason = f"{reason} Re-observe before retrying, or request human takeover."
            return self._shoav_block_response(
                reason, tool="browser.execute_action", stage="egress", verdict=verdict,
            )
        return None

    async def _shoav_probe_element_id(self, session_id: str | None, element_id: str) -> dict[str, Any] | None:
        session = await self.manager.get_session(session_id)
        page = session.page
        selector = f'[data-operator-id="{element_id}"]'
        locator = page.locator(selector).first
        try:
            await locator.scroll_into_view_if_needed()
        except Exception:
            pass
        box = await locator.bounding_box()
        if not box:
            return None
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        script = self._shoav_hit_script(cx, cy, element_id)
        hit = await page.evaluate(script)
        if not isinstance(hit, dict):
            return None
        return {"hit": hit, "selector_only": False, "coord_only": False}

    async def _shoav_probe_selector(self, session_id: str | None, selector: str) -> dict[str, Any] | None:
        session = await self.manager.get_session(session_id)
        page = session.page
        locator = page.locator(selector).first
        try:
            await locator.scroll_into_view_if_needed()
        except Exception:
            pass
        box = await locator.bounding_box()
        if not box:
            return None
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        hit = await page.evaluate(_shoav_selector_hit_test_script(cx, cy, selector))
        if not isinstance(hit, dict):
            return None
        return {"hit": hit, "selector_only": True, "coord_only": False}

    async def _shoav_probe_coords(
        self, session_id: str | None, cx: float, cy: float, expected_ref: str | None
    ) -> dict[str, Any] | None:
        session = await self.manager.get_session(session_id)
        hit = await session.page.evaluate(self._shoav_hit_script(cx, cy, expected_ref))
        if not isinstance(hit, dict):
            return None
        return {"hit": hit, "selector_only": False, "coord_only": expected_ref is None}

    def _shoav_hit_script(self, cx: float, cy: float, expected_ref: str | None) -> str:
        try:
            from shoav_mcp.filters.egress.scripts import build_hit_test_script as _build
        except Exception:
            try:
                from filters.egress.scripts import build_hit_test_script as _build  # type: ignore
            except Exception:
                return _shoav_hit_test_script(cx, cy, expected_ref)
        try:
            return _build(cx, cy, expected_ref)
        except TypeError:
            try:
                return _build(cx, cy)  # type: ignore
            except Exception:
                return _shoav_hit_test_script(cx, cy, expected_ref)

    async def _shoav_decide_click(
        self, *, expected_ref: str | None, hit: dict, selector_only: bool, coord_only: bool
    ) -> tuple[str, str]:
        decide = getattr(self.guard, "decide_egress", None) if self.guard is not None else None
        if callable(decide):
            outcome = decide({"expected_ref": expected_ref, "hit_result": hit})
            if asyncio.iscoroutine(outcome):
                outcome = await outcome
            verdict = self._shoav_verdict_str(outcome)
            reason = self._shoav_reason(outcome, "egress decision")
            if verdict in ("BLOCK", "ESCALATE", "ALLOW"):
                return verdict, reason
        try:
            from shoav_mcp.filters.egress.engine import EgressFilter as _EgressFilter
        except Exception:
            try:
                from filters.egress.engine import EgressFilter as _EgressFilter  # type: ignore
            except Exception:
                return self._shoav_local_click_verdict(expected_ref, hit, selector_only, coord_only)
        if coord_only or selector_only:
            return self._shoav_local_click_verdict(expected_ref, hit, selector_only, coord_only)
        outcome = _EgressFilter().verify_click(expected_ref or "", hit)
        verdict = self._shoav_verdict_str(outcome)
        return verdict, self._shoav_reason(outcome, "click verification")

    @staticmethod
    def _shoav_local_click_verdict(
        expected_ref: str | None, hit: dict, selector_only: bool, coord_only: bool
    ) -> tuple[str, str]:
        if not hit.get("found"):
            return "ESCALATE", "No element found at target coordinates, page may have changed."
        if hit.get("inside_target") is True:
            return "ALLOW", "Target coordinate verified clean."
        if not selector_only and not coord_only and expected_ref and hit.get("ref") == expected_ref:
            return "ALLOW", "Target coordinate verified clean."
        try:
            opacity = float(hit.get("opacity", 1.0))
        except (TypeError, ValueError):
            opacity = 1.0
        try:
            z_index = int(hit.get("z_index", "0"))
        except (TypeError, ValueError):
            z_index = 0
        pointer_events = hit.get("pointer_events", "auto")
        decoy = (opacity < 0.1 and pointer_events != "none") or z_index > 9000
        if decoy:
            return (
                "BLOCK",
                f"Clickjacking overlay suspected: <{hit.get('tag')}> occludes intended target.",
            )
        if coord_only:
            return "ALLOW", "Coordinate decoy check passed."
        return (
            "ESCALATE",
            f"Target mismatch: topmost element is <{hit.get('tag')}>. Page state may have changed.",
        )

    async def _shoav_drag_check(
        self, arguments: Any, live_call: LiveCall | None, mode: str
    ) -> McpToolCallResponse | None:
        session_id = getattr(arguments, "session_id", None)
        points: list[tuple[str, Any]] = []
        for label, sel, px, py in (
            ("source", getattr(arguments, "source_selector", None),
             getattr(arguments, "source_x", None), getattr(arguments, "source_y", None)),
            ("target", getattr(arguments, "target_selector", None),
             getattr(arguments, "target_x", None), getattr(arguments, "target_y", None)),
        ):
            if sel:
                points.append((label, ("selector", sel)))
            elif px is not None and py is not None:
                points.append((label, ("coords", float(px), float(py))))
        if not points:
            return None
        session = await self.manager.get_session(session_id)
        page = session.page
        for label, point in points:
            if point[0] == "selector":
                locator = page.locator(point[1]).first
                try:
                    await locator.scroll_into_view_if_needed()
                except Exception:
                    pass
                box = await locator.bounding_box()
                if not box:
                    continue
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
            else:
                cx, cy = point[1], point[2]
            hit = await page.evaluate(self._shoav_hit_script(cx, cy, None))
            if not isinstance(hit, dict):
                continue
            verdict, reason = self._shoav_local_click_verdict(None, hit, False, True)
            if verdict == "BLOCK":
                await self._shoav_emit(
                    live_call, stage="egress", tool="browser.drag_drop", verdict=verdict,
                    reason=f"drag {label}: {reason}",
                    target={"drag_point": label}, enforced=mode == "enforce",
                )
                if mode == "enforce":
                    return self._shoav_block_response(
                        f"drag {label}: {reason}",
                        tool="browser.drag_drop", stage="egress", verdict=verdict,
                    )
        return None

    # -- C-5 post-hoc -----------------------------------------------------

    async def _shoav_posthoc_check(
        self, spec: Any, arguments: Any, result: Any, live_call: LiveCall | None
    ) -> McpToolCallResponse | None:
        mode = self._shoav_mode()
        if mode == "off":
            return None
        try:
            if spec.name == "browser.close_session":
                self._shoav_reset(getattr(arguments, "session_id", None))
                return None
            if spec.name != "browser.execute_action":
                return None
            decision = getattr(arguments, "action", None)
            if decision is None:
                return None
            session_id = getattr(arguments, "session_id", None)
            action = getattr(decision, "action", None)
            if isinstance(result, dict):
                self._shoav_note_navigation(session_id, result.get("url"))
            if action == "navigate":
                self._shoav_note_navigation(session_id, getattr(decision, "url", None))
                return None
            element_id = getattr(decision, "element_id", None)
            if action in ("click", "select_option", "type") and element_id and session_id:
                self._shoav_state(session_id)["touched"].add(element_id)
            if action == "type":
                return await self._shoav_type_check(session_id, decision, live_call, mode)
            if action == "press" and str(getattr(decision, "key", "")).lower() == "enter":
                return await self._shoav_submit_check(session_id, live_call, mode, trigger="press Enter")
            if action == "click" and self._shoav_is_submit_control(session_id, element_id):
                return await self._shoav_submit_check(session_id, live_call, mode, trigger="submit control")
            return None
        except Exception as exc:
            logger.warning("shoav posthoc hook failed: %s", exc, exc_info=True)
            if self._shoav_fail_closed():
                return self._shoav_block_response(
                    f"Guard unavailable, failing closed: {exc}",
                    tool=spec.name, stage="posthoc", verdict="BLOCK",
                )
            return None

    def _shoav_is_submit_control(self, session_id: str | None, element_id: str | None) -> bool:
        if not session_id or not element_id:
            return False
        for node in self._shoav_state(session_id).get("interactables") or []:
            if not isinstance(node, dict):
                continue
            if node.get("element_id") != element_id:
                continue
            node_type = str(node.get("type") or "").lower()
            label = str(node.get("label") or node.get("name") or "").lower()
            if node_type in ("submit", "button") or "submit" in label or "place order" in label:
                return True
            return False
        return False

    async def _shoav_type_check(
        self, session_id: str | None, decision: Any, live_call: LiveCall | None, mode: str
    ) -> McpToolCallResponse | None:
        element_id = getattr(decision, "element_id", None)
        selector = getattr(decision, "selector", None)
        expected_ref = element_id or selector
        if not session_id or not expected_ref:
            return None
        expected_value = getattr(decision, "text", "") or ""
        sensitive = bool(getattr(decision, "sensitive", False))
        try:
            session = await self.manager.get_session(session_id)
            focus_script = self._shoav_focus_script()
            focus = await session.page.evaluate(focus_script)
        except Exception as exc:
            logger.warning("shoav focus probe failed: %s", exc, exc_info=True)
            return None
        if not isinstance(focus, dict):
            return None
        verdict, reason = await self._shoav_decide_input(
            expected_ref, expected_value, focus, sensitive=sensitive
        )
        target: dict[str, Any] = {"element_id": element_id} if element_id else {"selector": selector}
        enforced = mode == "enforce" and verdict == "BLOCK"
        await self._shoav_emit(
            live_call, stage="posthoc", tool="browser.execute_action", verdict=verdict,
            reason=reason, target=target, enforced=enforced,
        )
        if verdict == "BLOCK" and mode == "enforce":
            return self._shoav_block_response(
                reason, tool="browser.execute_action", stage="posthoc", verdict=verdict,
            )
        return None

    def _shoav_focus_script(self) -> str:
        try:
            from shoav_mcp.filters.egress.scripts import FOCUS_CHECK_SCRIPT as _script
            return _script
        except Exception:
            try:
                from filters.egress.scripts import FOCUS_CHECK_SCRIPT as _script  # type: ignore
                return _script
            except Exception:
                return _SHOAV_FOCUS_CHECK_SCRIPT

    async def _shoav_decide_input(
        self, expected_ref: str, expected_value: str, focus: dict, *, sensitive: bool
    ) -> tuple[str, str]:
        if sensitive or str(focus.get("type") or "").lower() == "password":
            if focus.get("ref") == expected_ref or (
                expected_ref and not str(expected_ref).startswith("[") and focus.get("ref") == expected_ref
            ):
                return "ALLOW", "Input focus verified intact (value compare skipped for sensitive field)."
            if focus.get("found") and not focus.get("ref") and expected_ref.startswith("["):
                return "ALLOW", "Input focus verified intact (value compare skipped for sensitive field)."
            return (
                "BLOCK",
                f"Input focus deflection detected: expected {expected_ref!r}, "
                f"got {focus.get('ref')!r}.",
            )
        decide = getattr(self.guard, "decide_egress", None) if self.guard is not None else None
        if callable(decide):
            try:
                outcome = decide(
                    {"check": "input", "expected_ref": expected_ref,
                     "expected_value": expected_value, "focus_result": focus}
                )
                if asyncio.iscoroutine(outcome):
                    outcome = await outcome
                verdict = self._shoav_verdict_str(outcome)
                if verdict in ("ALLOW", "BLOCK", "ESCALATE"):
                    return verdict, self._shoav_reason(outcome, "input verification")
            except Exception:
                pass
        try:
            from shoav_mcp.filters.egress.engine import EgressFilter as _EgressFilter
        except Exception:
            try:
                from filters.egress.engine import EgressFilter as _EgressFilter  # type: ignore
            except Exception:
                ref_ok = focus.get("ref") == expected_ref
                val_ok = focus.get("value") == expected_value
                if ref_ok and val_ok:
                    return "ALLOW", "Input focus and value verified intact."
                return "BLOCK", "Input focus deflection detected."
        outcome = _EgressFilter().verify_input(expected_ref, expected_value, focus)
        return self._shoav_verdict_str(outcome), self._shoav_reason(outcome, "input verification")

    async def _shoav_submit_check(
        self, session_id: str | None, live_call: LiveCall | None, mode: str, *, trigger: str
    ) -> McpToolCallResponse | None:
        if not session_id:
            return None
        state = self._shoav_state(session_id)
        snapshot = state.get("form_snapshot") or []
        touched = state.get("touched") or set()
        verdict, reason, flags = await self._shoav_decide_submission(snapshot, touched)
        if verdict != "ESCALATE":
            return None
        await self._shoav_emit(
            live_call, stage="posthoc", tool="browser.execute_action", verdict=verdict,
            reason=f"{trigger}: {reason}", findings={"count": len(flags)}, enforced=mode == "enforce",
        )
        if mode == "enforce":
            return self._shoav_block_response(
                f"{reason} Re-observe the form before submitting, or request human takeover.",
                tool="browser.execute_action", stage="posthoc", verdict=verdict,
                findings={"count": len(flags)},
            )
        return None

    async def _shoav_decide_submission(
        self, snapshot: list[dict], touched: set[str]
    ) -> tuple[str, str, list[dict]]:
        decide = getattr(self.guard, "decide_egress", None) if self.guard is not None else None
        if callable(decide):
            try:
                outcome = decide({"check": "submission", "snapshot": snapshot, "touched": sorted(touched)})
                if asyncio.iscoroutine(outcome):
                    outcome = await outcome
                verdict = self._shoav_verdict_str(outcome)
                if verdict in ("ALLOW", "ESCALATE", "BLOCK"):
                    flags = []
                    if isinstance(outcome, dict) and isinstance(outcome.get("flags"), list):
                        flags = outcome["flags"]
                    return verdict, self._shoav_reason(outcome, "submission check"), flags
            except Exception:
                pass
        try:
            from shoav_mcp.filters.egress.engine import EgressFilter as _EgressFilter
            from shoav_mcp.filters.session_state import SessionState as _SessionState
        except Exception:
            try:
                from filters.egress.engine import EgressFilter as _EgressFilter  # type: ignore
                from filters.session_state import SessionState as _SessionState  # type: ignore
            except Exception:
                flags = [
                    item for item in snapshot
                    if item.get("checked") and item.get("ref") not in touched
                ]
                if flags:
                    return "ESCALATE", (
                        f"{len(flags)} untouched pre-checked field(s) at submission."
                    ), flags
                return "ALLOW", "No untouched pre-checked fields.", []
        fake = _SessionState(initial_form_snapshot=snapshot, touched_refs=set(touched))
        outcome = _EgressFilter().verify_submission(fake)
        flags = outcome.get("flags", []) if isinstance(outcome, dict) else []
        return self._shoav_verdict_str(outcome), self._shoav_reason(outcome, "submission check"), flags

    async def _resolve_implicit_session(
        self, spec: Any, arguments: BaseModel, live_call: LiveCall | None = None
    ) -> BaseModel:
        """Resolve an omitted session_id against the live session set.

        Exactly one live session → target it. None live → create one on demand,
        but only for observe/act tools (IMPLICIT_SESSION_CREATE_TOOLS). Anything
        ambiguous stays an explicit, actionable error rather than a guess.
        """
        if not isinstance(arguments, SessionIdInput) or arguments.session_id:
            return arguments
        # list_sessions() also returns stored records of closed/interrupted sessions;
        # only sessions with a live browser count for implicit targeting.
        sessions = [item for item in await self.manager.list_sessions() if item.get("live", True) is not False]
        if len(sessions) == 1:
            return arguments.model_copy(update={"session_id": sessions[0]["id"]})
        if not sessions:
            if spec.name in IMPLICIT_SESSION_CREATE_TOOLS:
                created = await self.manager.create_session()
                if live_call is not None:
                    live_call.created = created
                return arguments.model_copy(update={"session_id": created["id"]})
            raise BrowserActionError(
                f"{spec.name} needs a session and none are live — create one with "
                "browser.create_session (or call an observe/act tool, which creates "
                "one on demand).",
                code="no_session",
                action=spec.name,
            )
        ids = ", ".join(str(item.get("id")) for item in sessions)
        raise BrowserActionError(
            f"session_id is required when multiple sessions are live ({ids}).",
            code="ambiguous_session",
            action=spec.name,
        )

    @staticmethod
    def _tool_response_meta(
        *,
        existing: dict[str, Any] | None,
        tool: str,
        status: str,
        duration_seconds: float,
    ) -> dict[str, Any]:
        meta = dict(existing or {})
        meta.setdefault("tool", tool)
        meta.setdefault("status", status)
        meta.setdefault("latency_ms", round(duration_seconds * 1000, 2))
        return meta

    @staticmethod
    def _pop_policy_profile(spec: ToolSpec, raw_arguments: dict[str, Any]) -> str:
        profile = str(raw_arguments.pop("policy_profile", "") or raw_arguments.get("workflow_profile") or "fast")
        if "workflow_profile" not in spec.input_model.model_fields:
            raw_arguments.pop("workflow_profile", None)
        return profile

    @staticmethod
    def _pop_policy_approval_id(spec: ToolSpec, raw_arguments: dict[str, Any]) -> str | None:
        approval_id = raw_arguments.get("approval_id")
        if "approval_id" not in spec.input_model.model_fields:
            approval_id = raw_arguments.pop("approval_id", approval_id)
        governed_approval_id = raw_arguments.pop("governed_approval_id", None)
        return str(governed_approval_id or approval_id) if governed_approval_id or approval_id else None

    async def _require_governed_tool_approval(
        self,
        spec: ToolSpec,
        arguments: BaseModel,
        *,
        workflow_profile: str,
        approval_id: str | None,
    ):
        if workflow_profile != "governed" or spec.governed_kind is None:
            return None
        session_id = getattr(arguments, "session_id", None)
        if not session_id:
            return None
        decision = getattr(arguments, "action", None)
        if not isinstance(decision, BrowserActionDecision):
            decision = BrowserActionDecision(
                action="request_human_takeover",
                reason=f"Approve governed MCP tool call {spec.name}",
                risk_category=spec.governed_kind if spec.governed_kind != "dynamic" else "write",
            )
        return await self.manager.require_governed_approval(
            session_id,
            decision,
            approval_id=approval_id,
        )

    async def _create_session(self, payload: CreateSessionRequest) -> dict[str, Any]:
        return await self.manager.create_session(
            name=payload.name,
            start_url=payload.start_url,
            storage_state_path=payload.storage_state_path,
            auth_profile=payload.auth_profile,
            memory_profile=payload.memory_profile,
            proxy_persona=payload.proxy_persona,
            request_proxy_server=payload.proxy_server,
            request_proxy_username=payload.proxy_username,
            request_proxy_password=payload.proxy_password,
            user_agent=payload.user_agent,
            protection_mode=payload.protection_mode,
            totp_secret=payload.totp_secret,
        )

    async def _list_sessions(self, _: EmptyInput) -> list[dict[str, Any]]:
        return await self.manager.list_sessions()

    async def _save_memory_profile(self, payload: SaveMemoryProfileInput) -> dict[str, Any]:
        if self.manager.memory is None:
            raise RuntimeError("Memory profiles are not enabled.")
        await self.manager.get_session(payload.session_id)
        profile = await self.manager.memory.save(
            payload.profile_name,
            goal_summary=payload.goal_summary,
            completed_steps=payload.completed_steps,
            discovered_selectors=payload.discovered_selectors,
            notes=payload.notes,
            metadata={"session_id": payload.session_id},
        )
        return profile.model_dump()

    async def _get_memory_profile(self, payload: GetMemoryProfileInput) -> dict[str, Any]:
        if self.manager.memory is None:
            raise RuntimeError("Memory profiles are not enabled.")
        profile = await self.manager.memory.get(payload.profile_name)
        if profile is None:
            raise KeyError(f"Memory profile not found: {payload.profile_name!r}")
        return profile.model_dump()

    async def _list_memory_profiles(self, _: EmptyInput) -> list[dict[str, Any]]:
        if self.manager.memory is None:
            return []
        return await self.manager.memory.list()

    async def _delete_memory_profile(self, payload: DeleteMemoryProfileInput) -> dict[str, Any]:
        if self.manager.memory is None:
            raise RuntimeError("Memory profiles are not enabled.")
        deleted = await self.manager.memory.delete(payload.profile_name)
        return {"name": payload.profile_name, "deleted": deleted}

    async def _get_session(self, payload: SessionIdInput) -> dict[str, Any]:
        return await self.manager.get_session_record(payload.session_id)

    async def _observe(self, payload: ObserveInput) -> dict[str, Any]:
        return await self.manager.observe(payload.session_id, limit=payload.limit, preset=payload.preset)

    async def _screenshot(self, payload: ScreenshotInput) -> dict[str, Any]:
        return await self.manager.capture_screenshot(
            payload.session_id,
            label=payload.label,
            image=payload.image,
            format=payload.format,
            scale=payload.scale,
            quality=payload.quality,
            full_page=payload.full_page,
            selector=payload.selector,
        )

    async def _snapshot(self, payload: SnapshotInput) -> dict[str, Any]:
        return await self.manager.snapshot(
            payload.session_id,
            selector=payload.selector,
            depth=payload.depth,
            max_chars=payload.max_chars,
            offset=payload.offset,
            viewport_only=payload.viewport_only,
            include=payload.include,
        )

    async def _get_console(self, payload: SessionTailInput) -> dict[str, Any]:
        return await self.manager.get_console_messages(payload.session_id, limit=payload.limit)

    async def _get_page_errors(self, payload: SessionTailInput) -> dict[str, Any]:
        return await self.manager.get_page_errors(payload.session_id, limit=payload.limit)

    async def _get_request_failures(self, payload: SessionTailInput) -> dict[str, Any]:
        return await self.manager.get_request_failures(payload.session_id, limit=payload.limit)

    async def _stop_trace(self, payload: SessionIdInput) -> dict[str, Any]:
        return await self.manager.stop_trace(payload.session_id)

    async def _list_auth_profiles(self, _: ListAuthProfilesInput) -> list[dict[str, Any]]:
        return await self.manager.list_auth_profiles()

    async def _get_auth_profile(self, payload: AuthProfileNameInput) -> dict[str, Any]:
        return await self.manager.get_auth_profile(payload.profile_name)

    async def _list_downloads(self, payload: ListDownloadsInput) -> list[dict[str, Any]]:
        return await self.manager.list_downloads(payload.session_id)

    async def _list_tabs(self, payload: ListTabsInput) -> list[dict[str, Any]]:
        return await self.manager.list_tabs(payload.session_id)

    async def _activate_tab(self, payload: TabActionInput) -> dict[str, Any]:
        return await self.manager.activate_tab(payload.session_id, payload.index)

    async def _close_tab(self, payload: TabActionInput) -> dict[str, Any]:
        return await self.manager.close_tab(payload.session_id, payload.index)

    async def _execute_action(self, payload: ExecuteActionInput) -> dict[str, Any]:
        return await self.manager.execute_decision(
            payload.session_id,
            payload.action,
            approval_id=payload.approval_id,
        )

    async def _save_auth_state(self, payload: SaveAuthStateInput) -> dict[str, Any]:
        return await self.manager.save_storage_state(payload.session_id, payload.path)

    async def _save_auth_profile(self, payload: SaveAuthProfileInput) -> dict[str, Any]:
        return await self.manager.save_auth_profile(payload.session_id, payload.profile_name)

    async def _takeover(self, payload: TakeoverInput) -> dict[str, Any]:
        return await self.manager.request_human_takeover(payload.session_id, payload.reason)

    async def _close_session(self, payload: SessionIdInput) -> dict[str, Any]:
        return await self.manager.close_session(payload.session_id)

    async def _list_approvals(self, payload: ListApprovalsInput) -> list[dict[str, Any]]:
        return await self.manager.list_approvals(status=payload.status, session_id=payload.session_id)

    async def _approve_approval(self, payload: ApprovalDecisionInput) -> dict[str, Any]:
        return await self.manager.approve(payload.approval_id, comment=payload.comment)

    async def _reject_approval(self, payload: ApprovalDecisionInput) -> dict[str, Any]:
        return await self.manager.reject(payload.approval_id, comment=payload.comment)

    async def _execute_approval(self, payload: ApprovalIdInput) -> dict[str, Any]:
        return await self.manager.execute_approval(payload.approval_id)

    async def _list_agent_jobs(self, payload: ListAgentJobsInput) -> list[dict[str, Any]]:
        return await self.job_queue.list_jobs(status=payload.status, session_id=payload.session_id)

    async def _get_agent_job(self, payload: AgentJobIdInput) -> dict[str, Any]:
        return await self.job_queue.get_job(payload.job_id)

    async def _resume_agent_job(self, payload: ResumeAgentJobInput) -> dict[str, Any]:
        return await self.job_queue.resume_job(payload.job_id, max_steps=payload.max_steps)

    async def _discard_agent_job(self, payload: AgentJobIdInput) -> dict[str, Any]:
        return await self.job_queue.discard_job(payload.job_id)

    async def _cancel_agent_job(self, payload: AgentJobIdInput) -> dict[str, Any]:
        return await self.job_queue.cancel_job(payload.job_id)

    async def _queue_agent_step(self, payload: QueueAgentStepInput) -> dict[str, Any]:
        await self.manager.get_session(payload.session_id)
        return await self.job_queue.enqueue_step(payload.session_id, payload.request)

    async def _queue_agent_run(self, payload: QueueAgentRunInput) -> dict[str, Any]:
        await self.manager.get_session(payload.session_id)
        return await self.job_queue.enqueue_run(payload.session_id, payload.request)

    async def _list_providers(self, _: EmptyInput) -> list[dict[str, Any]]:
        return [item.model_dump() for item in self.orchestrator.list_providers()]

    def _get_harness_service(self):
        if self.harness_service is not None:
            return self.harness_service
        raise RuntimeError("Harness service is not initialized")

    async def _harness_start_convergence(self, payload: HarnessStartConvergenceInput) -> dict[str, Any]:
        service = self._get_harness_service()
        use_live_session = payload.session_id is not None and payload.mock_final_observation is None
        record = await service.start_convergence(
            payload.contract,
            mock_final_observation=payload.mock_final_observation,
            orchestrator=self.orchestrator if use_live_session else None,
            session_id=payload.session_id,
            provider=payload.provider,
            max_attempts=payload.max_attempts,
        )
        return record.model_dump(mode="json")

    async def _harness_get_status(self, payload: HarnessGetStatusInput) -> dict[str, Any]:
        return self._get_harness_service().get_status(payload.run_id)

    async def _harness_get_trace(self, payload: HarnessGetTraceInput) -> dict[str, Any]:
        return self._get_harness_service().get_trace(payload.run_id, attempt_index=payload.attempt_index)

    async def _harness_list_runs(self, payload: HarnessListRunsInput) -> list[dict[str, Any]]:
        return self._get_harness_service().list_runs(status=payload.status, limit=payload.limit)

    async def _harness_list_candidates(self, _: EmptyInput) -> list[dict[str, Any]]:
        return self._get_harness_service().list_candidates()

    async def _harness_get_candidate(self, payload: HarnessSkillIdInput) -> dict[str, Any]:
        return self._get_harness_service().get_candidate(payload.skill_id)

    async def _harness_check_drift(self, payload: HarnessSkillIdInput) -> dict[str, Any]:
        return await self._get_harness_service().check_drift(payload.skill_id)

    async def _harness_check_all_drifts(self, _: EmptyInput) -> list[dict[str, Any]]:
        return await self._get_harness_service().check_all_drifts()

    async def _harness_graduate(self, payload: HarnessGraduateInput) -> dict[str, Any]:
        return self._get_harness_service().graduate(payload.run_id)

    async def _get_remote_access(self, payload: GetRemoteAccessInput) -> dict[str, Any]:
        if payload.session_id and payload.session_id not in self.manager.sessions:
            record = await self.manager.get_session_record(payload.session_id)
            return record["remote_access"]
        return self.manager.get_remote_access_info(payload.session_id)

    async def _readiness_check(self, payload: ReadinessCheckInput) -> dict[str, Any]:
        report = run_readiness_checks(self.manager.settings, mode=payload.mode)
        return report.to_dict()

    # ── Extended tool handlers ──────────────────────────────────────────────

    async def _get_network_log(self, payload: GetNetworkLogInput) -> dict[str, Any]:
        return await self.manager.get_network_log(
            payload.session_id,
            limit=payload.limit,
            method=payload.method,
            url_contains=payload.url_contains,
        )

    async def _verify_witness(self, payload: VerifyWitnessInput) -> dict[str, Any]:
        return await self.manager.verify_witness_chain(payload.session_id)

    async def _export_witness_bundle(self, payload: VerifyWitnessInput) -> dict[str, Any]:
        return await self.manager.export_witness_bundle(payload.session_id)

    async def _fork_session(self, payload: ForkSessionInput) -> dict[str, Any]:
        return await self.manager.fork_session(
            payload.session_id,
            name=payload.name,
            start_url=payload.start_url,
        )

    async def _eval_js(self, payload: EvalJsInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        result = await session.page.evaluate(payload.expression)
        return {"session_id": payload.session_id, "result": result}

    async def _wait_for_selector(self, payload: WaitForSelectorInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        await session.page.wait_for_selector(
            payload.selector,
            timeout=payload.timeout_ms,
            state=payload.state,
        )
        return {"session_id": payload.session_id, "selector": payload.selector, "state": payload.state}

    async def _get_html(self, payload: GetPageHtmlInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        if payload.text_only:
            text = await session.page.evaluate("() => document.body ? document.body.innerText : ''")
            return {"session_id": payload.session_id, "content": text, "type": "text"}
        html = await session.page.content()
        return {"session_id": payload.session_id, "content": html, "type": "html"}

    async def _find_elements(self, payload: FindElementsInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        if payload.query is not None:
            evaluate = session.page.evaluate(
                """([query, isRegex, context, limit]) => {
                    let matcher = null;
                    if (isRegex) {
                        try {
                            matcher = new RegExp(query, 'gi');
                        } catch (e) {
                            return {__invalid_regex: String((e && e.message) || e)};
                        }
                    }
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
                    const results = [];
                    let node;
                    while ((node = walker.nextNode()) && results.length < limit) {
                        const text = node.textContent || '';
                        if (!text.trim()) continue;
                        let matchIndex = -1;
                        let matchText = '';
                        if (isRegex) {
                            matcher.lastIndex = 0;
                            const m = matcher.exec(text);
                            if (m) { matchIndex = m.index; matchText = m[0]; }
                        } else {
                            const idx = text.toLowerCase().indexOf(query.toLowerCase());
                            if (idx !== -1) { matchIndex = idx; matchText = text.substr(idx, query.length); }
                        }
                        if (matchIndex === -1) continue;
                        const el = node.parentElement;
                        if (!el) continue;
                        const r = el.getBoundingClientRect();
                        const start = Math.max(0, matchIndex - context);
                        const end = Math.min(text.length, matchIndex + matchText.length + context);
                        results.push({
                            tag: el.tagName.toLowerCase(),
                            text: text.trim().substring(0, 200),
                            match: matchText,
                            context_text: text.substring(start, end).trim(),
                            value: el.value || null,
                            href: el.href || null,
                            id: el.id || null,
                            class: (typeof el.className === 'string' ? el.className : el.getAttribute('class')) || null,
                            visible: r.width > 0 && r.height > 0,
                            x: Math.round(r.x), y: Math.round(r.y),
                            width: Math.round(r.width), height: Math.round(r.height),
                        });
                    }
                    return results;
                }""",
                [payload.query, payload.regex, payload.context, payload.limit],
            )
            try:
                elements = await asyncio.wait_for(evaluate, timeout=FIND_ELEMENTS_QUERY_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                raise BrowserActionError(
                    f"find_elements query timed out after "
                    f"{FIND_ELEMENTS_QUERY_TIMEOUT_SECONDS:g}s — the pattern may "
                    "backtrack catastrophically on this page's text",
                    code="query_timeout",
                    action="find_elements",
                ) from None
            if isinstance(elements, dict) and "__invalid_regex" in elements:
                raise BrowserActionError(
                    f"Invalid regular expression: {elements['__invalid_regex']}",
                    code="invalid_regex",
                    action="find_elements",
                )
            return {"session_id": payload.session_id, "query": payload.query, "elements": elements}

        elements = await session.page.evaluate(
            """([selector, limit]) => {
                const els = [...document.querySelectorAll(selector)].slice(0, limit);
                return els.map(el => {
                    const r = el.getBoundingClientRect();
                    return {
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.substring(0, 200) || '',
                        value: el.value || null,
                        href: el.href || null,
                        id: el.id || null,
                        class: (typeof el.className === 'string' ? el.className : el.getAttribute('class')) || null,
                        visible: r.width > 0 && r.height > 0,
                        x: Math.round(r.x), y: Math.round(r.y),
                        width: Math.round(r.width), height: Math.round(r.height),
                    };
                });
            }""",
            [payload.selector, payload.limit],
        )
        return {"session_id": payload.session_id, "selector": payload.selector, "elements": elements}

    async def _drag_drop(self, payload: DragDropInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)

        # Resolve source coordinates
        if payload.source_selector:
            box = await session.page.locator(payload.source_selector).first.bounding_box()
            sx = box["x"] + box["width"] / 2 if box else 0
            sy = box["y"] + box["height"] / 2 if box else 0
        elif payload.source_x is not None and payload.source_y is not None:
            sx, sy = payload.source_x, payload.source_y
        else:
            raise ValueError("Provide source_selector or source_x/source_y")

        # Resolve target coordinates
        if payload.target_selector:
            box = await session.page.locator(payload.target_selector).first.bounding_box()
            tx = box["x"] + box["width"] / 2 if box else 0
            ty = box["y"] + box["height"] / 2 if box else 0
        elif payload.target_x is not None and payload.target_y is not None:
            tx, ty = payload.target_x, payload.target_y
        else:
            raise ValueError("Provide target_selector or target_x/target_y")

        await session.page.mouse.move(sx, sy)
        await session.page.mouse.down()
        await session.page.mouse.move(tx, ty, steps=10)
        await session.page.mouse.up()
        return {"session_id": payload.session_id, "from": {"x": sx, "y": sy}, "to": {"x": tx, "y": ty}}

    async def _set_viewport(self, payload: SetViewportInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        await session.page.set_viewport_size({"width": payload.width, "height": payload.height})
        return {"session_id": payload.session_id, "width": payload.width, "height": payload.height}

    async def _get_cookies(self, payload: GetCookiesInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        cookies = await session.context.cookies(urls=payload.urls)
        return {"session_id": payload.session_id, "cookies": cookies}

    async def _set_cookies(self, payload: SetCookiesInput) -> dict[str, Any]:
        session = await self.manager.get_session(payload.session_id)
        await session.context.add_cookies(payload.cookies)
        return {"session_id": payload.session_id, "set": len(payload.cookies)}

    async def _get_local_storage(self, payload: GetStorageInput) -> dict[str, Any]:
        if payload.storage_type not in {"local", "session"}:
            raise ValueError(f"Invalid storage_type: {payload.storage_type!r}")
        session = await self.manager.get_session(payload.session_id)
        if payload.key:
            script = f"() => window.{payload.storage_type}Storage.getItem({payload.key!r})"
            value = await session.page.evaluate(script)
            return {"session_id": payload.session_id, "key": payload.key, "value": value}
        script = (
            f"() => Object.fromEntries("
            f"Object.keys(window.{payload.storage_type}Storage).map("
            f"k => [k, window.{payload.storage_type}Storage.getItem(k)]))"
        )
        data = await session.page.evaluate(script)
        return {"session_id": payload.session_id, "storage": data}

    async def _set_local_storage(self, payload: SetStorageInput) -> dict[str, Any]:
        if payload.storage_type not in {"local", "session"}:
            raise ValueError(f"Invalid storage_type: {payload.storage_type!r}")
        session = await self.manager.get_session(payload.session_id)
        script = f"([k, v]) => window.{payload.storage_type}Storage.setItem(k, v)"
        await session.page.evaluate(script, [payload.key, payload.value])
        return {"session_id": payload.session_id, "key": payload.key, "set": True}

    async def _export_script(self, payload: ExportScriptInput) -> dict[str, Any]:
        from ..playwright_export import export_session_script

        session = await self.manager.get_session(payload.session_id)
        start_url = session.page.url
        return await export_session_script(
            payload.session_id,
            self.manager.audit,
            start_url=start_url,
            viewport_w=self.manager.settings.default_viewport_width,
            viewport_h=self.manager.settings.default_viewport_height,
        )

    async def _cdp_attach(self, payload: CdpAttachInput) -> dict[str, Any]:
        return await self.manager.cdp_attach(payload.cdp_url)

    async def _find_by_vision(self, payload: VisionFindInput) -> dict[str, Any]:
        if self.vision_targeter is None:
            raise RuntimeError("Vision targeting is not available — set ANTHROPIC_API_KEY to enable it.")
        session = await self.manager.get_session(payload.session_id)
        if payload.take_screenshot:
            screenshot = await self.manager.capture_screenshot(payload.session_id, label="vision")
            screenshot_path = screenshot["screenshot_path"]
        else:
            # Use the most recent screenshot if available
            screenshots = sorted(
                session.artifact_dir.glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not screenshots:
                raise RuntimeError("No screenshots available — take one first")
            screenshot_path = str(screenshots[0])

        result = await self.vision_targeter.find_element(screenshot_path, payload.description)
        return {"session_id": payload.session_id, **result}

    async def _share_session(self, payload: ShareSessionInput) -> dict[str, Any]:
        if self.share_manager is None:
            raise RuntimeError("Session sharing is not configured")
        await self.manager.get_session(payload.session_id)  # verify session exists
        return self.share_manager.create_token(
            payload.session_id,
            ttl_seconds=payload.ttl_minutes * 60,
        )

    async def _enable_shadow_browse(self, payload: ShadowBrowseInput) -> dict[str, Any]:
        return await self.manager.enable_shadow_browse(payload.session_id)

    async def _list_proxy_personas(self, _: EmptyInput) -> list[dict[str, Any]]:
        if self.proxy_store is None:
            return []
        return self.proxy_store.list_personas()

    async def _create_proxy_persona(self, payload: CreateProxyPersonaInput) -> dict[str, Any]:
        if self.proxy_store is None:
            raise RuntimeError("No PROXY_PERSONA_FILE configured")
        return self.proxy_store.set_persona(
            payload.name,
            server=payload.server,
            username=payload.username,
            password=payload.password,
            description=payload.description,
        )

    async def _delete_proxy_persona(self, payload: ProxyPersonaNameInput) -> dict[str, Any]:
        if self.proxy_store is None:
            raise RuntimeError("No PROXY_PERSONA_FILE configured")
        deleted = self.proxy_store.delete_persona(payload.name)
        return {"name": payload.name, "deleted": deleted}

    async def _list_cron_jobs(self, _: EmptyInput) -> list[dict[str, Any]]:
        if self.cron_service is None:
            return []
        return await self.cron_service.list_jobs()

    async def _create_cron_job(self, payload: CreateCronJobInput) -> dict[str, Any]:
        if self.cron_service is None:
            raise RuntimeError("Cron service not initialized")
        return await self.cron_service.create_job(
            name=payload.name,
            goal=payload.goal,
            provider=payload.provider,
            schedule=payload.schedule,
            start_url=payload.start_url,
            auth_profile=payload.auth_profile,
            proxy_persona=payload.proxy_persona,
            max_steps=payload.max_steps,
            enabled=payload.enabled,
            webhook_enabled=payload.webhook_enabled,
        )

    async def _delete_cron_job(self, payload: CronJobIdInput) -> dict[str, Any]:
        if self.cron_service is None:
            raise RuntimeError("Cron service not initialized")
        deleted = await self.cron_service.delete_job(payload.job_id)
        return {"job_id": payload.job_id, "deleted": deleted}

    async def _trigger_cron_job(self, payload: CronJobIdInput) -> dict[str, Any]:
        if self.cron_service is None:
            raise RuntimeError("Cron service not initialized")
        return await self.cron_service.trigger_job(payload.job_id)

    async def _pii_scrubber_status(self, _: EmptyInput) -> dict[str, Any]:
        return self.manager.get_pii_scrubber_status()
