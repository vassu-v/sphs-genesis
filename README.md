# AI Bodyguard — Genesis Hackathon (Track 3)

Defensive middleware that sits between an autonomous web-browsing agent and the
browser, and stops the agent being manipulated by hostile page content — hidden
prompt injections, clickjacking overlays, dark patterns.

> **Status:** research phase. We are grounding the attack taxonomy in published work
> *before* building detectors, so the benchmark is not circular.

## The idea

A **proxy MCP server**. The guard re-exposes a browser MCP server's own tools,
audits each action before forwarding it, and sanitises page content on the way back.
The agent needs one config line and no code change.

- **Deterministic core** — geometry, computed style and origin checks that page text
  cannot argue with.
- **LLM on a leash** — advisory only; it may escalate suspicion, never clear it.

## Repository layout

| Path | What's there |
|------|--------------|
| [`research/`](research) | Literature-grounded research (workstreams 00–09): attacks, dark patterns, prevalence, mitigations, citations, synthesis. Start with [`08-synthesis/SYNTHESIS.md`](research/08-synthesis/SYNTHESIS.md). |
| [`track3/`](track3) | First prototype. **Superseded** — kept for reference only. |
| [`external/`](external) | Third-party clones (git-ignored). |
| [`assets/`](assets) | Screenshots, diagrams, demo images (tracked). |

## Research at a glance

| # | Workstream | Output |
|---|------------|--------|
| 00 | Shared brief | `BRIEF.md` |
| 01 | Agent attacks | `FINDINGS.md` |
| 02 | Dark patterns | `FINDINGS.md` |
| 03 | Prevalence | `FINDINGS.md` |
| 04 | Mitigations | `FINDINGS.md` |
| 05 | Citations | `BIBLIOGRAPHY.md`, `VERIFICATION.md` |
| 06 | Auto-browser evaluation | `FINDINGS.md`, `INTEGRATION.md` |
| 07 | TrickyArena | `FINDINGS.md` |
| 08 | Synthesis | `SYNTHESIS.md`, `DETECTION_TARGETS.md`, `OPEN_QUESTIONS.md` |
| 09 | Verification closeout | `CLOSEOUT.md` |

Read [`09-verification-closeout/CLOSEOUT.md`](research/09-verification-closeout/CLOSEOUT.md)
before citing any number — it lists claims that must not be repeated as originally worded.

## Setup

```bash
git clone https://github.com/LvcidPsyche/auto-browser.git external/auto-browser
```

Python 3.10 for anything under `track3/`; Node for browser tooling.

## Team

Two people: harness and guard layers, and dashboard and frontend.
