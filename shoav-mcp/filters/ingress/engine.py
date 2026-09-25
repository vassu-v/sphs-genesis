"""IngressFilter: orchestrates the pure rules into ALLOW/REWRITE/BLOCK.

Designed to degrade gracefully: it always runs the checks that work from
Auto Browser's *existing* payload fields (text injections, node/token
budget, pre-checked toggles from accessibility_outline), and additionally
runs the computed-style hidden-node check only when style_facts (from
scripts.STYLE_PROBE_SCRIPT, not yet wired into Auto Browser) is supplied,
and the mutation-flood check only when a live mutation_rate is supplied
(also not yet wired in — needs a connector-side MutationObserver).
"""

from __future__ import annotations

from ..constants import INGRESS_NODE_BUDGET_TRIGGER
from ..session_state import SessionState
from ..types import Verdict
from . import rules


class IngressFilter:
    def process(
        self,
        payload: dict,
        *,
        style_facts: list[dict] | None = None,
        session_state: SessionState | None = None,
        mutation_rate: float | None = None,
        form_controls: list[dict] | None = None,
    ) -> dict:
        """payload: an Auto Browser observation-shaped dict, at minimum
        {"interactables": [...], "text_excerpt": "...",
         "accessibility_outline": {"nodes": [...]}}. Missing keys are
        treated as empty, so a partial payload degrades rather than errors.

        form_controls: when supplied, a list of control dicts straight from
        FORM_STATE_SCRIPT output ({element_id/ref, tag, type, checked,
        label, name}). Correlation prefers ref, then element_id, then name.
        When None (default), falls back to the accessibility_outline path.
        """
        interactables = list(payload.get("interactables", []))
        text_excerpt = payload.get("text_excerpt", "") or ""
        ax_nodes = (payload.get("accessibility_outline") or {}).get("nodes", [])

        text_findings = rules.find_text_injections(text_excerpt)
        style_result = {"stripped": [], "skipped_benign": []}
        if style_facts is not None:
            style_result = rules.find_hidden_textful_nodes(style_facts)
            stripped_refs = {entry["ref"] for entry in style_result["stripped"]}
            interactables = [
                node for node in interactables
                if node.get("element_id") not in stripped_refs
            ]

        hidden_texts = [entry.get("text") or entry.get("snippet") or "" for entry in style_result["stripped"]]
        clean_text, removed_count = rules.sanitize_text(text_excerpt, hidden_texts)
        truncated_text, text_was_compacted = rules.truncate_text_excerpt(clean_text)

        node_count_before_budget = len(interactables)
        compacted_interactables, node_was_compacted = rules.compact_node_budget(interactables)
        was_compacted = node_was_compacted or text_was_compacted

        if form_controls is not None:
            normalized_controls = [
                {
                    "ref": control.get("ref")
                    or control.get("element_id")
                    or control.get("name"),
                    "type": control.get("type"),
                    "checked": bool(control.get("checked")),
                    "label": control.get("label") or control.get("name"),
                }
                for control in form_controls
            ]
        else:
            normalized_controls = [
                {
                    "ref": node.get("ref") or node.get("element_id") or node.get("name") or node.get("role"),
                    "type": "checkbox" if node.get("role") in ("checkbox", "switch") else node.get("role"),
                    "checked": bool(node.get("checked")),
                    "label": node.get("name") or node.get("description"),
                }
                for node in ax_nodes
                if node.get("role") in ("checkbox", "switch")
            ]
        form_controls = normalized_controls
        prechecked = rules.flag_prechecked_toggles(form_controls)
        if session_state is not None:
            prechecked = [
                item for item in prechecked
                if item.get("ref") not in session_state.touched_refs
            ]
            if session_state.initial_form_snapshot is None:
                session_state.initial_form_snapshot = form_controls

        # gross node flood, well past ordinary compaction — see BLOCK step in
        # PLAN_AND_ROUGH_SKETCH.md 3.1 step 4. 4x the trigger is a deliberately
        # conservative floor: compaction alone handles ordinary large pages.
        node_flood = node_count_before_budget > INGRESS_NODE_BUDGET_TRIGGER * 4
        mutation_flood, mutation_reason = (
            rules.evaluate_mutation_rate(mutation_rate) if mutation_rate is not None
            else (False, None)
        )
        flooding = node_flood or mutation_flood

        stripped_count = len(style_result["stripped"])
        finding_count = len(text_findings) + len(prechecked) + removed_count

        telemetry_lines = ["[S.H.O.A.V. INGRESS SHIELD]"]
        findings = {
            "text_injections": text_findings,
            "hidden_nodes": style_result,
            "prechecked_toggles": prechecked,
        }

        if flooding:
            if node_flood:
                telemetry_lines.append(
                    f"status: blocked (node flood — {node_count_before_budget} nodes, "
                    f"budget is {INGRESS_NODE_BUDGET_TRIGGER})"
                )
            if mutation_flood:
                telemetry_lines.append(f"status: blocked (mutation flood — {mutation_reason})")
            return {
                "verdict": Verdict.BLOCK,
                "telemetry": "\n".join(telemetry_lines),
                "payload": None,
                "findings": findings,
            }

        if stripped_count == 0 and finding_count == 0 and not was_compacted:
            telemetry_lines.append("status: allowed (clean)")
            return {
                "verdict": Verdict.ALLOW,
                "telemetry": "\n".join(telemetry_lines),
                "payload": {
                    **payload,
                    "interactables": compacted_interactables,
                    "text_excerpt": truncated_text,
                },
                "findings": {**findings, "text_injections": [], "prechecked_toggles": []},
            }

        telemetry_lines.append("status: rewritten")
        telemetry_lines.append(f"- hidden nodes stripped: {stripped_count}")
        telemetry_lines.append(f"- text/comment injection findings: {len(text_findings)}")
        telemetry_lines.append(f"- text removals from excerpt (hidden text, zero-width chars, injected sentences): {removed_count}")
        telemetry_lines.append(f"- pre-checked consent-like toggles flagged: {len(prechecked)}")
        telemetry_lines.append(
            f"- context compaction: {node_count_before_budget} -> "
            f"{len(compacted_interactables)} nodes"
            if node_was_compacted else "- context compaction: not needed"
        )
        telemetry_lines.append(
            "- text excerpt truncated: token budget exceeded"
            if text_was_compacted else "- text excerpt: within token budget"
        )

        return {
            "verdict": Verdict.REWRITE,
            "telemetry": "\n".join(telemetry_lines),
            "payload": {
                **payload,
                "interactables": compacted_interactables,
                "text_excerpt": truncated_text,
            },
            "findings": findings,
        }
