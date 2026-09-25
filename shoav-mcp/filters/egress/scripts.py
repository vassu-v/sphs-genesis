"""JS snippets the egress engine needs evaluated in-page.

Same split as ingress/scripts.py: these strings are for a future connector
to execute (via browser.eval_js today, or a direct session.page.evaluate()
once wired into Auto Browser internals). rules.py consumes only their
already-evaluated output shape, so it never needs a browser to test.
"""


def build_hit_test_script(cx: float, cy: float) -> str:
    """Target 2: what's actually topmost at the target's center point."""
    return f"""
    (() => {{
        const topEl = document.elementFromPoint({cx}, {cy});
        if (!topEl) return {{ found: false }};
        const style = window.getComputedStyle(topEl);
        return {{
            found: true,
            tag: topEl.tagName,
            ref: topEl.getAttribute('data-operator-id'),
            opacity: parseFloat(style.opacity),
            z_index: style.zIndex,
            pointer_events: style.pointerEvents,
        }};
    }})()
    """


FOCUS_CHECK_SCRIPT = """
(() => {
    const el = document.activeElement;
    if (!el) return { found: false };
    return {
        found: true,
        tag: el.tagName,
        ref: el.getAttribute('data-operator-id'),
        value: el.value !== undefined ? el.value : null,
    };
})()
"""
