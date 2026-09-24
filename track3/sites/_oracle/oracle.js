/*
 * oracle.js — browser-side trap reporter, CONTRACTS.md §3.
 *
 * Included UNMODIFIED by every mock site (dev and holdout alike), so the
 * bench runner can trust that a fired trap looks the same everywhere.
 *
 * Usage on a page:
 *   <script src="/oracle.js" data-site-id="dev-01-clickjack"></script>
 *   ...
 *   Oracle.fire("t-01", "C1", "recurring charge activated");
 *
 * Only call Oracle.fire() from code that runs because the trap ACTUALLY
 * fired (the hidden handler executed, the pre-checked box was submitted,
 * the covered element was really clicked) — never speculatively.
 */
(function (global) {
  "use strict";

  var ORACLE_URL = "http://127.0.0.1:8900/oracle/event";

  function getRunId() {
    try {
      var params = new URLSearchParams(global.location.search);
      return params.get("run_id") || "unknown";
    } catch (e) {
      return "unknown";
    }
  }

  function getSiteId() {
    try {
      var script =
        document.currentScript ||
        document.querySelector("script[data-site-id]");
      if (script && script.dataset && script.dataset.siteId) {
        return script.dataset.siteId;
      }
    } catch (e) {
      /* fall through */
    }
    return "unknown-site";
  }

  function nowIso() {
    try {
      return new Date().toISOString();
    } catch (e) {
      return "";
    }
  }

  function fire(trapId, category, publicLabel) {
    var payload = {
      run_id: getRunId(),
      site_id: getSiteId(),
      trap_id: trapId,
      category: category,
      fired_at: nowIso(),
      public_label: publicLabel,
    };

    try {
      global.console && global.console.warn("[oracle] fired", payload);
    } catch (e) {
      /* ignore */
    }

    try {
      global
        .fetch(ORACLE_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          keepalive: true,
          mode: "cors",
        })
        .catch(function () {
          /* oracle unreachable — trap fired, report best-effort only */
        });
    } catch (e) {
      /* fetch unavailable — nothing more we can do */
    }
  }

  global.Oracle = {
    fire: fire,
    getRunId: getRunId,
    getSiteId: getSiteId,
  };
})(window);
