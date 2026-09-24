"""
Offline smoke test for the Playwright shim: python -m adapters.playwright.smoketest [url]
Uses sync Playwright directly, wraps the page, exercises guard_goto/read_page/guard_click,
and demonstrates GuardBlocked being raised on a clickjack trap when one is present.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    from playwright.sync_api import sync_playwright

    from adapters.playwright import GuardBlocked, wrap

    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8901/cart.html"
    os.environ.setdefault("GUARD_RUN_ID", "playwright-shim-smoketest")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = wrap(browser.new_page())
        result = page.guard_goto(url)
        print(f"[shim-smoketest] goto -> {result}")

        page_data = page.read_page()
        snap = page_data["snapshot"]
        print(f"[shim-smoketest] snapshot: {len(snap['elements'])} elements, "
              f"warnings={page_data['guard_warnings']}")

        decoy_ref = None
        for el in snap["elements"]:
            if "keep me updated" in (el["text"] or "").lower():
                decoy_ref = el["ref"]
        if decoy_ref:
            try:
                page.guard_click(decoy_ref)
                print("[shim-smoketest] UNEXPECTED: click was not blocked")
                return 1
            except GuardBlocked as exc:
                print(f"[shim-smoketest] guard_click correctly BLOCKED: {exc}")
        else:
            print("[shim-smoketest] no clickjack decoy found on this page (fine on non-01 sites)")

        browser.close()
    print("[shim-smoketest] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
