"""
The ONE snapshot extractor, shared by the MCP server (adapters/mcp/server.py) and the
Playwright in-process shim (adapters/playwright/shim.py). Do not duplicate this logic —
both adapters call `page.evaluate(SNAPSHOT_EXTRACTOR_JS)` (sync or async) and shape the
returned dict into a PageSnapshot via adapters/_shared/snapshot.py.

Per CONTRACTS.md §5, this is the single most important piece of code in the guard
system: the guard can only be as good as the signal it receives here. In particular it
must compute `hitTestRef` (document.elementFromPoint at the element's centre) for every
interactive element -- that is the flagship clickjacking check's only input.

Refs are stable across calls within one DOM state: elements are tagged in-place with a
`data-guard-ref="ref_N"` attribute the first time they're seen, so `click(ref)` etc. can
resolve back to the live element with a plain `[data-guard-ref="ref_N"]` selector.
"""

SNAPSHOT_EXTRACTOR_JS = r"""
() => {
  if (!window.__guardRefCounter) window.__guardRefCounter = 0;

  function refFor(el) {
    if (!el || el.nodeType !== 1) return null;
    let r = el.getAttribute('data-guard-ref');
    if (!r) {
      r = 'ref_' + (window.__guardRefCounter++);
      el.setAttribute('data-guard-ref', r);
    }
    return r;
  }

  function parseColor(c) {
    // returns [r,g,b,a] or null
    if (!c) return null;
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    return [parts[0] || 0, parts[1] || 0, parts[2] || 0, parts.length > 3 ? parts[3] : 1];
  }

  function colorsClose(c1, c2, tol) {
    const a = parseColor(c1), b = parseColor(c2);
    if (!a || !b) return false;
    const dr = Math.abs(a[0] - b[0]), dg = Math.abs(a[1] - b[1]), db = Math.abs(a[2] - b[2]);
    return (dr + dg + db) < tol;
  }

  function isInteractive(el) {
    const tag = el.tagName.toLowerCase();
    if (['button', 'a', 'input', 'select', 'textarea', 'label'].includes(tag)) return true;
    const role = el.getAttribute('role');
    if (role && ['button', 'link', 'checkbox', 'radio', 'menuitem', 'tab', 'switch'].includes(role)) return true;
    if (el.hasAttribute('onclick')) return true;
    if (el.tabIndex !== undefined && el.tabIndex >= 0 && el !== document.body) return true;
    const style = getComputedStyle(el);
    if (style.cursor === 'pointer') return true;
    return false;
  }

  function computedBlock(style) {
    return {
      opacity: parseFloat(style.opacity),
      fontSize: parseFloat(style.fontSize) || 0,
      color: style.color,
      backgroundColor: style.backgroundColor,
      visibility: style.visibility,
      display: style.display,
      zIndex: style.zIndex === 'auto' ? 0 : (parseInt(style.zIndex, 10) || 0),
      pointerEvents: style.pointerEvents,
      clipPath: style.clipPath,
      transform: style.transform,
    };
  }

  function hiddenReasons(el, style, box) {
    const reasons = [];
    if (parseFloat(style.opacity) === 0) reasons.push('opacity-zero');
    if ((parseFloat(style.fontSize) || 0) === 0) reasons.push('font-size-zero');
    if (colorsClose(style.color, style.backgroundColor, 12)) reasons.push('color-matches-background');
    if (box.x + box.w < 0 || box.y + box.h < 0 || box.x > window.innerWidth * 3) reasons.push('offscreen');
    if (style.clipPath && style.clipPath !== 'none') reasons.push('clipped');
    if ((box.w === 0 || box.h === 0) && style.display !== 'none') reasons.push('zero-size');
    if (style.visibility === 'hidden' || style.visibility === 'collapse') reasons.push('visibility-hidden');
    return reasons;
  }

  function labelText(el) {
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab && lab.innerText.trim()) return lab.innerText.trim();
    }
    const wrapping = el.closest('label');
    if (wrapping && wrapping.innerText.trim()) return wrapping.innerText.trim();
    return '';
  }

  function accessibleName(el) {
    return (
      el.getAttribute('aria-label') ||
      labelText(el) ||
      el.innerText ||
      el.getAttribute('alt') ||
      el.getAttribute('title') ||
      el.value ||
      ''
    ).trim().slice(0, 200);
  }

  function inAccessibilityTree(el, style) {
    if (el.getAttribute('aria-hidden') === 'true') return false;
    if (style.display === 'none') return false;
    if (el.hasAttribute('hidden')) return false;
    if (el.closest('[aria-hidden="true"]')) return false;
    return true;
  }

  function ancestorRefs(node) {
    // Chain of refs from `node`'s PARENT up to (and including) <body>. Used to
    // populate `hitTestAncestors` on the element the agent intended to hit, so
    // guard/l1_structural.py's hit-test check can tell "this covering element
    // is actually a benign descendant of my target" from "something unrelated
    // is genuinely on top" without needing a full DOM tree walk of its own.
    const chain = [];
    let cur = node ? node.parentElement : null;
    let hops = 0;
    while (cur && hops < 64) {
      chain.push(refFor(cur));
      if (cur === document.body) break;
      cur = cur.parentElement;
      hops++;
    }
    return chain;
  }

  const elements = [];
  const seen = new Set();
  // Deliberately broad: querySelectorAll('*') + isInteractive() filter, not a fixed
  // tag/attr allowlist. A clickjack decoy is very often a bare <span> or <div> with
  // only an inline cursor:pointer style and a JS click handler -- exactly the kind of
  // element a tag-based selector (button, a, [role], [onclick]...) would silently miss,
  // which would blind the hit-test check on precisely the elements it exists to catch.
  const candidates = document.querySelectorAll('*');

  candidates.forEach((el) => {
    if (seen.has(el)) return;
    if (!isInteractive(el)) return;
    seen.add(el);

    const rect = el.getBoundingClientRect();
    const box = { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) };
    const style = getComputedStyle(el);
    const ref = refFor(el);

    // hit-test at the element's own centre point
    const cx = rect.x + rect.width / 2;
    const cy = rect.y + rect.height / 2;
    let hitTestRef = null;
    let hitTestAncestors = [];
    if (rect.width > 0 && rect.height > 0 && cx >= 0 && cy >= 0 && cx <= window.innerWidth && cy <= window.innerHeight) {
      const hitEl = document.elementFromPoint(cx, cy);
      hitTestRef = hitEl ? refFor(hitEl) : null;
      if (hitEl && hitTestRef !== ref) hitTestAncestors = ancestorRefs(hitEl);
    } else {
      hitTestRef = ref; // off-viewport elements can't be hit-tested; treat as self
    }

    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    // Live DOM property, not the static HTML attribute -- a checkbox pre-checked in
    // markup but later toggled by page JS (or vice versa) must report its CURRENT
    // state, since that's what actually submits. attrs['checked'] would only ever
    // reflect how the page was originally authored.
    const isCheckable = (el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio'));

    // Cheap, attribute-based guess at what activating this element actually DOES --
    // fake_close_button needs to distinguish "this dismisses something" from "this
    // navigates/submits/mutates cart or subscription state" and we cannot see JS
    // closures from here, only DOM shape. Populate what's inferable for free; do not
    // over-invest (a wrong guess just means the check falls back to its own
    // attrs-based heuristics, which it already has per guard/'s own fallback).
    const handlers = [];
    if (el.tagName === 'A' && el.getAttribute('href')) handlers.push('navigate');
    if (el.tagName === 'BUTTON' && (el.getAttribute('type') || '').toLowerCase() === 'submit') handlers.push('submit');
    if (el.hasAttribute('formaction')) handlers.push('submit');
    if (el.closest('form') && (el.tagName === 'BUTTON' || (el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'submit'))) {
      if (!handlers.includes('submit')) handlers.push('submit');
    }
    for (const a of el.attributes) {
      if (/^data-(cart|extra)/i.test(a.name)) handlers.push('cart-mutate');
      if (/^data-(subscription|recurring|plan)/i.test(a.name)) handlers.push('subscription-mutate');
    }

    elements.push({
      ref,
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      name: accessibleName(el),
      text: (el.innerText || el.value || '').trim().slice(0, 500),
      box,
      computed: computedBlock(style),
      attrs,
      inAccessibilityTree: inAccessibilityTree(el, style),
      hitTestRef,
      hitTestAncestors,
      checked: isCheckable ? !!el.checked : null,
      handlers: Array.from(new Set(handlers)),
    });
  });

  // forms
  const forms = [];
  document.querySelectorAll('form').forEach((form) => {
    const ref = refFor(form);
    let action = form.action || document.location.href;
    try { action = new URL(action, document.location.href).href; } catch (e) {}
    const fields = [];
    form.querySelectorAll('input, select, textarea').forEach((field) => {
      const fref = refFor(field);
      let label = '';
      if (field.id) {
        const lab = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
        if (lab) label = lab.innerText.trim();
      }
      if (!label && field.closest('label')) label = field.closest('label').innerText.trim();
      fields.push({
        ref: fref,
        name: field.name || field.id || '',
        type: field.type || field.tagName.toLowerCase(),
        checked: !!field.checked,
        label: label.slice(0, 200),
      });
    });
    forms.push({ ref, action, method: (form.method || 'get').toLowerCase(), fields });
  });

  // text nodes: walk visible text-bearing leaf elements
  const textNodes = [];
  const NON_CONTENT_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TITLE']);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      // Script/style/template contents are text nodes in the DOM tree but are never
      // page CONTENT a human or the agent reads -- without this filter every <script>
      // body gets reported as a giant "hidden text the user cannot read" finding,
      // which is noise at best and a false-positive injection_phrasing surface at
      // worst (application JS source routinely contains words like "ignore" or
      // "system" with no adversarial meaning at all).
      const p = n.parentElement;
      if (p && NON_CONTENT_TAGS.has(p.tagName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let node;
  let guard = 0;
  while ((node = walker.nextNode()) && guard < 2000) {
    const text = node.textContent.trim();
    if (!text) continue;
    guard++;
    const parent = node.parentElement;
    if (!parent) continue;
    const style = getComputedStyle(parent);
    const rect = parent.getBoundingClientRect();
    const box = { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) };
    const reasons = hiddenReasons(parent, style, box);
    // covered-by-overlay check for short imperative snippets (injection bait tends to be short blocks)
    let covered = false;
    if (rect.width > 0 && rect.height > 0) {
      const cx = rect.x + rect.width / 2, cy = rect.y + rect.height / 2;
      if (cx >= 0 && cy >= 0 && cx <= window.innerWidth && cy <= window.innerHeight) {
        const hitEl = document.elementFromPoint(cx, cy);
        if (hitEl && hitEl !== parent && !parent.contains(hitEl)) covered = true;
      }
    }
    if (covered) reasons.push('covered');
    if (parent.getAttribute('aria-hidden') !== 'true' && reasons.length === 0 && style.visibility === 'hidden') {
      reasons.push('aria-only');
    }
    const visible = reasons.length === 0 && style.display !== 'none';
    textNodes.push({ ref: refFor(parent), text: text.slice(0, 500), visible, hiddenBy: reasons });
  }

  // amounts: scan visible text for currency-like numbers, plus data-amount attrs
  const amounts = [];
  const currencyRe = /(₹|INR|Rs\.?|\$|USD)\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)/gi;
  document.querySelectorAll('body *').forEach((el) => {
    if (el.children.length > 0) return; // leaf-ish only, avoid double counting containers
    const text = (el.innerText || '').trim();
    if (!text || text.length > 100) return;
    let m;
    currencyRe.lastIndex = 0;
    while ((m = currencyRe.exec(text)) !== null) {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const box = { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) };
      const reasons = hiddenReasons(el, style, box);
      const currency = /₹|INR|Rs/i.test(m[1]) ? 'INR' : 'USD';
      amounts.push({
        ref: refFor(el),
        value: parseFloat(m[2].replace(/,/g, '')),
        currency,
        visiblyRendered: reasons.length === 0 && style.display !== 'none' && rect.width > 0 && rect.height > 0,
      });
    }
  });
  // also pick up amounts smuggled only in data-* attributes (never rendered)
  document.querySelectorAll('[data-amount], [data-price], [data-fee]').forEach((el) => {
    ['data-amount', 'data-price', 'data-fee'].forEach((attr) => {
      const v = el.getAttribute(attr);
      if (v && !isNaN(parseFloat(v))) {
        amounts.push({
          ref: refFor(el),
          value: parseFloat(v),
          currency: el.getAttribute('data-currency') || 'INR',
          visiblyRendered: false,
        });
      }
    });
  });

  return {
    url: document.location.href,
    title: document.title,
    viewport: { w: window.innerWidth, h: window.innerHeight },
    elements,
    forms,
    textNodes,
    amounts,
  };
}
"""
