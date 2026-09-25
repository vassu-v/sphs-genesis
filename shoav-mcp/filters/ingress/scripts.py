"""JS snippets the ingress engine needs evaluated in-page.

Nothing in this file runs here — these are string constants for a future
connector (browser.eval_js today, or a direct page.evaluate() once wired
into Auto Browser's internals per INTEGRATION.md) to execute and hand back
as plain dicts/lists. Keeping the JS out of the decision logic is what makes
rules.py testable without a browser: feed it the JS's *output* shape
directly as a fixture.

Design choice vs. the original rough sketch in PLAN_AND_ROUGH_SKETCH.md:
that sketch's script both inspects AND mutates the page (`el.remove()`)
in one pass, so the only thing Python ever sees is a stripped count. This
version reports facts only — the Python side decides what to strip — per
INTEGRATION.md's own recommendation for style_probe ("WITHOUT pre-filtering
... we want the invisible ones surfaced, not silently dropped"). This keeps
the mutation decision (which needs the benign-hidden-marker allowlist,
keyword heuristics, etc.) in testable Python instead of buried in a page.evaluate string.
"""

# Walks elements carrying Auto Browser's existing data-operator-id stamp
# (see INTEGRATION.md's note that INTERACTABLES_SCRIPT already stamps
# elements it iterates) and reports raw style/geometry facts, no filtering.
STYLE_PROBE_SCRIPT = """
(() => {
    const results = [];
    const viewport = { width: window.innerWidth, height: window.innerHeight };
    const stamped = document.querySelectorAll('[data-operator-id]');
    for (const el of stamped) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const text = (el.innerText || el.textContent || '').trim();
        if (!text) continue;
        results.push({
            ref: el.getAttribute('data-operator-id'),
            tag: el.tagName,
            class_name: el.className || '',
            text_snippet: text.slice(0, 200),
            display: style.display,
            visibility: style.visibility,
            opacity: parseFloat(style.opacity),
            font_size: parseFloat(style.fontSize),
            rect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
            viewport,
        });
    }
    return results;
})()
"""
