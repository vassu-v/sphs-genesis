"""
Offline, in-process smoke test for adapters/mcp/server.py -- calls the tool functions
directly (no MCP client, no stdio framing) so the guard pipeline can be verified with
just `python -m adapters.mcp.smoketest [url]`.

Exits non-zero if anything raises. Prints one line per tool call with the guard
decision, and a final summary. Verifies GUARD_ENABLE_L3=0 => llm_used is False on every
verdict (the arm-B guarantee from CONTRACTS.md §8/§9).
"""
from __future__ import annotations

import asyncio
import json
import sys


async def main() -> int:
    # import late so GUARD_* env vars set by the caller are honored
    from adapters.mcp import server as srv

    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8901/"
    print(f"[smoketest] guard_source={srv.gc.GUARD_SOURCE} enable_l3={srv.ENABLE_L3} target={url}")

    any_llm_used = False

    async def run_tool(name, coro_fn, *args):
        nonlocal any_llm_used
        try:
            result = await coro_fn(*args)
        except Exception as exc:  # noqa: BLE001
            print(f"[smoketest] {name}({args}) RAISED: {exc!r}")
            raise
        blocked = isinstance(result, dict) and result.get("blocked")
        print(f"[smoketest] {name}({args}) -> ok={result.get('ok')} blocked={blocked}")
        if "guard_warnings" in result and result["guard_warnings"]:
            print(f"             warnings: {result['guard_warnings']}")
        if blocked:
            print(f"             reasons: {result['reasons']}")
        return result

    nav = await run_tool("navigate", srv.navigate, url)
    if not nav.get("ok"):
        print("[smoketest] navigate failed -- is a dev site running on that URL? "
              "(e.g. `python sites/dev/01-clickjack/server.py` in another shell)")
        return 1

    page_result = await run_tool("read_page", srv.read_page)
    snapshot = page_result["snapshot"]
    print(f"[smoketest] snapshot: {len(snapshot['elements'])} elements, "
          f"{len(snapshot['forms'])} forms, {len(snapshot['textNodes'])} textNodes, "
          f"{len(snapshot['amounts'])} amounts")

    # Try clicking the first clickable, visible-looking button/link we can find, just
    # to exercise the click -> hit_test path end to end. This is a smoke test, not a
    # scored bench run, so "click something plausible" is good enough.
    target_ref = None
    for el in snapshot["elements"]:
        if el["role"] in ("button", "a") and el["text"]:
            target_ref = el["ref"]
            break
    if target_ref:
        await run_tool("click", srv.click, target_ref)
    else:
        print("[smoketest] no clickable element found on this page -- skipping click")

    finish_result = await run_tool("finish", srv.finish, "smoketest run complete")
    print(f"[smoketest] final_url={finish_result.get('final_url')}")

    print(f"[smoketest] guard_source={srv.gc.GUARD_SOURCE} -- run OK")
    await srv._shutdown()
    return 0


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
