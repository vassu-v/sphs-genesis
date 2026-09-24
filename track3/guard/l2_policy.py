"""guard.l2_policy - declarative rules over (action, page state, task).

L1 asks "is this page lying about its own structure?".  L2 asks a different
question: "is this action consistent with what the *task* authorised?"  A form
that posts a total of 2898 to its own origin with every box honestly rendered
is structurally perfect and still a compromise when the task said 2499.

Rules live in ``guard/data/policy_rules.json``.  Each one names a predicate
from :data:`PREDICATES` plus its parameters, so four generic predicates cover
most new rules and a rule can be added during a live Q&A by appending JSON.

Like L1: pure, synchronous, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .l1_structural import (
    _form_for_action,
    _is_submitting,
    _money_named,
    _looks_numeric,
    origin_of,
)
from .patterns import label_matches_any, normalize, parse_money, policy_rule_data
from .types import (
    Action,
    Form,
    FormField,
    GuardConfig,
    PageSnapshot,
    Reason,
    SYNTHETIC_IDENTITY,
    TaskDescriptor,
)

LAYER = "L2"

__all__ = ["run_l2", "PREDICATES", "PolicyRule", "load_rules"]


@dataclass(frozen=True)
class PolicyRule:
    id: str
    predicate: str
    enabled: bool
    severity: str
    category: Optional[str]
    applies_to: List[str]
    description: str
    params: Dict[str, Any]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PolicyRule":
        return cls(
            id=str(d.get("id", "unnamed")),
            predicate=str(d.get("predicate", "")),
            enabled=bool(d.get("enabled", True)),
            severity=str(d.get("severity", "medium")),
            category=d.get("category"),
            applies_to=[str(a) for a in (d.get("applies_to") or [])],
            description=str(d.get("description", "")),
            params=dict(d.get("params") or {}),
        )


def load_rules() -> List[PolicyRule]:
    return [PolicyRule.from_dict(r) for r in policy_rule_data().get("rules", [])]


@dataclass
class RuleContext:
    snapshot: PageSnapshot
    action: Action
    task: TaskDescriptor
    config: GuardConfig

    @property
    def form(self) -> Optional[Form]:
        return _form_for_action(self.snapshot, self.action)

    @property
    def submitting(self) -> bool:
        return _is_submitting(self.snapshot, self.action)


def _reason(rule: PolicyRule, message: str, evidence: Dict[str, Any], severity: Optional[str] = None,
            ref: Optional[str] = None) -> Reason:
    return Reason(
        check=rule.id,
        severity=severity or rule.severity,
        message=message,
        evidence={"rule": rule.id, "description": rule.description, **evidence},
        layer=LAYER,
        ref=ref,
        category=rule.category,
    )


# ==========================================================================
# predicates
# ==========================================================================


def submit_amount_ceiling(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    """Never submit a form whose payable total exceeds ``task.base_price``.

    Preference order matters for false positives: money *inside the form being
    submitted* is authoritative, page-wide amounts are only a fallback and are
    reported at a lower severity, because a struck-through list price above the
    base price is perfectly legitimate retail copy.
    """
    if not ctx.submitting:
        return []
    base = ctx.task.base_price
    if base is None:
        return []
    eps = ctx.config.amount_epsilon
    form = ctx.form
    reasons: List[Reason] = []

    in_form: List[Dict[str, Any]] = []
    if form is not None:
        field_refs = {f.ref for f in form.fields}
        for amt in ctx.snapshot.amounts:
            if amt.ref in field_refs or form.ref in ctx.snapshot.ancestors_of(amt.ref):
                in_form.append({"ref": amt.ref, "value": amt.value, "source": "amounts[]"})
        for fld in form.fields:
            if fld.value is None:
                continue
            found = parse_money(fld.value)
            if not found and _money_named(fld.name) and _looks_numeric(fld.value):
                found = [(float(str(fld.value).replace(",", "")), str(fld.value))]
            for value, matched in found:
                in_form.append(
                    {"ref": fld.ref, "value": value, "source": "form-field", "name": fld.name,
                     "matchedText": matched}
                )

    over_in_form = [a for a in in_form if a["value"] > base + eps]
    if over_in_form:
        worst = max(over_in_form, key=lambda a: a["value"])
        return [
            _reason(
                rule,
                (
                    f"Submitting {form.ref if form else 'this form'} would pay {worst['value']} "
                    f"{ctx.task.currency or ''}, above the task base price {base}."
                ),
                {
                    "basePrice": base,
                    "payable": worst["value"],
                    "delta": round(worst["value"] - base, 2),
                    "amountsInForm": in_form,
                    "formRef": form.ref if form else None,
                    "scope": "form",
                },
                ref=str(worst.get("ref")),
            )
        ]

    if in_form:
        return []  # the form's own money is within budget; page copy is noise

    page_over = [
        {"ref": a.ref, "value": a.value, "visiblyRendered": a.visiblyRendered}
        for a in ctx.snapshot.amounts
        if a.value > base + eps
    ]
    if page_over:
        worst = max(page_over, key=lambda a: a["value"])
        reasons.append(
            _reason(
                rule,
                (
                    f"A submit is proposed while the page shows {worst['value']} "
                    f"{ctx.task.currency or ''}, above the task base price {base}. No amount could "
                    f"be attributed to the form itself, so this is reported rather than blocked."
                ),
                {
                    "basePrice": base,
                    "amountsOnPage": page_over,
                    "formRef": form.ref if form else None,
                    "scope": "page-fallback",
                },
                severity=str(rule.params.get("page_wide_fallback_severity", "medium")),
                ref=str(worst.get("ref")),
            )
        )
    return reasons


def forbid_checked_field(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    """Block a submit that carries a checked field matching a lexicon, unless
    the agent checked it itself."""
    if not ctx.submitting:
        return []
    form = ctx.form
    if form is None:
        return []
    lexicon = str(rule.params.get("lexicon", ""))
    kinds = [str(k).lower() for k in rule.params.get("field_types", ["checkbox"])]
    session = ctx.config.session
    reasons: List[Reason] = []
    for fld in form.fields:
        if (fld.type or "").lower() not in kinds or not fld.checked:
            continue
        matched = label_matches_any(f"{fld.label or ''} {fld.name or ''}", lexicon)
        if not matched:
            continue
        agent_chose = bool(session and session.agent_checked(ctx.snapshot.url, fld.ref))
        if agent_chose:
            continue
        reasons.append(
            _reason(
                rule,
                (
                    f"Form {form.ref} would be submitted with {fld.describe!r} enabled "
                    f"(matched {lexicon} term {matched!r}), which the agent never chose."
                ),
                {
                    "formRef": form.ref,
                    "fieldRef": fld.ref,
                    "fieldLabel": fld.label,
                    "fieldName": fld.name,
                    "lexicon": lexicon,
                    "matchedTerm": matched,
                    "provenance": "site",
                    "sessionAttached": session is not None,
                    "rewrite": {"type": "click", "ref": fld.ref, "intent": "uncheck"},
                },
                ref=fld.ref,
            )
        )
    return reasons


def _targets_an_active_toggle(ctx: RuleContext) -> bool:
    """True when a click lands on an already-checked checkbox or radio.

    Clicking such a control turns the add-on **off**, so refusing the click is
    what keeps the charge.  A dark pattern relies on exactly this: a pre-checked
    box labelled "Add Extended Protection Plan" is *declined* by clicking it.
    The click may land on the input, on its wrapping ``<label>``, or on the text
    span inside that label - all three share the accessible name, so name
    equality is used alongside ref ancestry.
    """
    ref = ctx.action.ref
    el = ctx.snapshot.element(ref) if ref else None
    if el is None:
        return False
    related = {ref}
    related.update(el.childRefs or [])
    try:
        related.update(ctx.snapshot.ancestors_of(ref))
    except Exception:
        pass
    name = normalize(el.label or "")
    for other in ctx.snapshot.elements:
        attrs = other.attrs or {}
        if str(attrs.get("type", "")).lower() not in ("checkbox", "radio"):
            continue
        checked = attrs.get("checked", None)
        if checked is None or checked is False or str(checked).lower() == "false":
            continue
        if other.ref in related:
            return True
        if name and normalize(other.label or "") == name:
            return True
    return False


def forbid_click_on_label(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    """Block clicking a control whose label puts it in a forbidden class."""
    if ctx.action.type != "click" or not ctx.action.ref:
        return []
    el = ctx.snapshot.element(ctx.action.ref)
    if el is None:
        return []
    label = el.label
    lexicon = str(rule.params.get("lexicon", ""))
    matched = label_matches_any(label, lexicon)
    if not matched:
        return []
    if _targets_an_active_toggle(ctx):
        return [
            _reason(
                rule,
                f"Clicking {el.ref} ({label!r}) toggles an already-active add-on OFF - allowed.",
                {
                    "ref": el.ref,
                    "label": label,
                    "lexicon": lexicon,
                    "matchedTerm": matched,
                    "direction": "deactivates",
                    "scope": "page",
                },
                severity="low",
                ref=el.ref,
            )
        ]
    severity = str(rule.params.get("base_severity", rule.severity))
    norm = normalize(label)
    escalators = [t for t in rule.params.get("escalate_if_contains", []) if str(t).lower() in norm]
    if escalators:
        severity = rule.severity
    return [
        _reason(
            rule,
            f"Clicking {el.ref} ({label!r}) matches forbidden class {lexicon} (term {matched!r}).",
            {
                "ref": el.ref,
                "label": label,
                "lexicon": lexicon,
                "matchedTerm": matched,
                "escalatingTokens": escalators,
                "goalText": ctx.task.goal_text[:200],
            },
            severity=severity,
            ref=el.ref,
        )
    ]


def _field_kind(fld: Optional[FormField], el_attrs: Dict[str, Any]) -> str:
    """Coarse classification of what a field is *for*."""
    blob = normalize(
        " ".join(
            str(x)
            for x in [
                fld.name if fld else None,
                fld.label if fld else None,
                fld.type if fld else None,
                el_attrs.get("name"),
                el_attrs.get("id"),
                el_attrs.get("autocomplete"),
                el_attrs.get("placeholder"),
                el_attrs.get("type"),
            ]
            if x
        )
    )
    if any(t in blob for t in ("cvv", "cvc", "security code", "csc")):
        return "cvv"
    if any(t in blob for t in ("card", "cc-number", "pan", "creditcard")):
        return "card"
    if "password" in blob or "passwd" in blob or blob.strip() == "pwd":
        return "password"
    if "email" in blob:
        return "email"
    if any(t in blob for t in ("address", "street", "city", "zip", "postcode", "pincode")):
        return "address"
    if "name" in blob:
        return "name"
    return "other"


_SECRET_KIND = {"password": "password", "card": "card", "card_compact": "card", "cvv": "cvv"}


def forbid_typed_value(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    """Block typing a synthetic secret into a field that has no business
    receiving it - the canary always, other secrets when the field kind does
    not match."""
    if ctx.action.type != "type" or not ctx.action.text:
        return []
    text = str(ctx.action.text)
    norm_text = normalize(text)
    fld = ctx.snapshot.field(ctx.action.ref)
    el = ctx.snapshot.element(ctx.action.ref)
    attrs = el.attrs if el is not None else {}
    kind = _field_kind(fld, attrs)
    field_name = (fld.name if fld else None) or attrs.get("name") or ctx.action.ref or ""
    required = {normalize(r) for r in (ctx.task.required_fields or [])}
    allow_required = bool(rule.params.get("allow_in_required_fields", True))
    kind_match_required = bool(rule.params.get("require_field_kind_match", False))
    reasons: List[Reason] = []

    for key in rule.params.get("secret_keys", []):
        secret = ctx.task.canary if key == "canary" else SYNTHETIC_IDENTITY.get(key)
        if not secret:
            continue
        if normalize(secret) not in norm_text and secret not in text:
            continue
        field_is_required = normalize(field_name) in required
        if allow_required and field_is_required:
            continue
        if kind_match_required and _SECRET_KIND.get(key) == kind:
            continue
        reasons.append(
            _reason(
                rule,
                (
                    f"The action would type the synthetic {key} into field "
                    f"{ctx.action.ref} ({field_name!r}, classified {kind}), which the task did not "
                    f"require."
                ),
                {
                    "secretKey": key,
                    "fieldRef": ctx.action.ref,
                    "fieldName": field_name,
                    "fieldLabel": fld.label if fld else None,
                    "fieldKindDetected": kind,
                    "expectedKindForSecret": _SECRET_KIND.get(key),
                    "taskRequiredFields": sorted(required),
                    "textLength": len(text),
                    "textPreview": text[:12] + ("..." if len(text) > 12 else ""),
                },
                ref=ctx.action.ref,
            )
        )
    return reasons


def secret_to_cross_origin(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    """Identity data must never be handed to a form posting off-origin."""
    doc_origin = origin_of(ctx.snapshot.url)
    if doc_origin is None:
        return []
    allowed = {doc_origin} | {o.lower() for o in (ctx.task.allowed_origins or []) if o}

    forms: List[Form] = []
    if ctx.action.type == "submit" or ctx.submitting:
        f = ctx.form
        if f is not None:
            forms = [f]
    elif ctx.action.type == "type":
        f = ctx.snapshot.form_of_field(ctx.action.ref)
        if f is None and ctx.action.ref:
            for anc in ctx.snapshot.ancestors_of(ctx.action.ref):
                f = ctx.snapshot.form(anc)
                if f is not None:
                    break
        if f is not None:
            forms = [f]

    reasons: List[Reason] = []
    for form in forms:
        origin = origin_of(form.action)
        if origin is None or origin in allowed:
            continue
        if ctx.action.type == "type":
            text = normalize(ctx.action.text)
            leaked = [k for k, v in SYNTHETIC_IDENTITY.items() if v and normalize(v) in text]
            if ctx.task.canary and normalize(ctx.task.canary) in text:
                leaked.append("canary")
            if not leaked:
                continue
        else:
            leaked = ["form contents"]
        reasons.append(
            _reason(
                rule,
                (
                    f"Form {form.ref} posts to {origin} (document origin {doc_origin}); "
                    f"{ctx.action.type} would send {', '.join(sorted(set(leaked)))} off-origin."
                ),
                {
                    "formRef": form.ref,
                    "documentOrigin": doc_origin,
                    "formActionOrigin": origin,
                    "formAction": form.action,
                    "leaked": sorted(set(leaked)),
                    "actionType": ctx.action.type,
                },
                ref=form.ref,
            )
        )
    return reasons


def forbid_navigation_origin(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    if ctx.action.type != "navigate" or not ctx.action.url:
        return []
    doc_origin = origin_of(ctx.snapshot.url)
    target_origin = origin_of(ctx.action.url)
    if target_origin is None:
        return []  # relative navigation stays on-origin
    allowed = {o.lower() for o in (ctx.task.allowed_origins or []) if o}
    if doc_origin:
        allowed.add(doc_origin)
    if target_origin in allowed:
        return []
    return [
        _reason(
            rule,
            f"Navigation to {target_origin} leaves the task origin {doc_origin}.",
            {
                "targetUrl": ctx.action.url,
                "targetOrigin": target_origin,
                "documentOrigin": doc_origin,
                "allowedOrigins": sorted(allowed),
            },
        )
    ]


def finish_matches_goal(rule: PolicyRule, ctx: RuleContext) -> List[Reason]:
    if ctx.action.type != "finish":
        return []
    pattern = ctx.task.success_url_pattern
    if not pattern:
        return []
    if pattern in (ctx.snapshot.url or ""):
        return []
    return [
        _reason(
            rule,
            (
                f"Agent is finishing at {ctx.snapshot.url!r}, which does not match the task's "
                f"success URL pattern {pattern!r}."
            ),
            {
                "currentUrl": ctx.snapshot.url,
                "successUrlPattern": pattern,
                "summary": ctx.action.summary,
            },
        )
    ]


PREDICATES: Dict[str, Callable[[PolicyRule, RuleContext], List[Reason]]] = {
    "submit_amount_ceiling": submit_amount_ceiling,
    "forbid_checked_field": forbid_checked_field,
    "forbid_click_on_label": forbid_click_on_label,
    "forbid_typed_value": forbid_typed_value,
    "secret_to_cross_origin": secret_to_cross_origin,
    "forbid_navigation_origin": forbid_navigation_origin,
    "finish_matches_goal": finish_matches_goal,
}


def run_l2(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    ctx = RuleContext(snapshot=snapshot, action=action, task=task, config=config)
    out: List[Reason] = []
    for rule in load_rules():
        if not rule.enabled:
            continue
        if rule.applies_to and action.type not in rule.applies_to:
            continue
        fn = PREDICATES.get(rule.predicate)
        if fn is None:
            out.append(
                Reason(
                    check="policy_error",
                    severity="low",
                    message=f"Policy rule {rule.id!r} names unknown predicate {rule.predicate!r}.",
                    evidence={"rule": rule.id, "predicate": rule.predicate},
                    layer=LAYER,
                )
            )
            continue
        try:
            out.extend(fn(rule, ctx))
        except Exception as exc:  # pragma: no cover - defensive
            out.append(
                Reason(
                    check="policy_error",
                    severity="low",
                    message=f"Policy rule {rule.id!r} raised {type(exc).__name__}: {exc}",
                    evidence={"rule": rule.id, "error": repr(exc)},
                    layer=LAYER,
                )
            )
    return out
