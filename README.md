<div align="center">

<table align="center">
  <tr>
    <td align="left" valign="middle">
      <h1>S.H.O.A.V.</h1>
      <b>S</b>hield for <b>H</b>ostile <b>O</b>perations &amp; <b>A</b>gent <b>V</b>ulnerability
    </td>
    <td align="center" valign="middle">
      <h2>AI<br>BODYGUARD</h2>
    </td>
  </tr>
</table>

<br>

Built for the **Genesis Hackathon 2026**, Track 03.

<br>

![Phase](https://img.shields.io/badge/phase-research-f59e0b?style=flat-square)
![Base](https://img.shields.io/badge/built_on-Auto_Browser-2563eb?style=flat-square)
![Core](https://img.shields.io/badge/core-deterministic-16a34a?style=flat-square)
![Track](https://img.shields.io/badge/genesis_hackathon-track_03-7c3aed?style=flat-square)

<br>

</div>

## The problem

Human users rely on spatial awareness and intuition to avoid sketchy pop-ups, fake
download buttons, bait-and-switch checkboxes, and hidden subscription traps.

Autonomous web-browsing agents (for example Playwright/Puppeteer-driven LLMs) read the
web mechanically, relying on raw DOM trees, accessibility trees, or screen coordinates.
Malicious sites exploit this blind spot using agent-targeted dark patterns and UI traps
to hijack automated workflows.

## The mission

Build a real-time defensive middleware, an "AI Bodyguard", that intercepts, evaluates,
and protects autonomous web agents from deceptive interfaces and adversarial web
design.

## Technical scope

**Interception layer.** Sits between the web-browsing agent and the browser session to
audit incoming DOM elements, visual layouts, and interaction targets before execution.

**Trap detection.** Spot deceptive UI patterns in real time, including phony
close/cancel targets that trigger downloads or navigation, invisible or overlapping
click-jacking layers, deceptive consent flows and pre-checked recurring billing traps,
and hidden prompt-injection vectors designed to hijack the agent goal.

**Actionable neutralization.** Either strip the malicious payload from the page,
reroute the agent action, or alert the agent planner with structured safety telemetry.

<br>

## What we are making

A guard layered on top of an existing browser MCP server, so that any agent able to
run a command in a terminal can drive a real browser through it, with the guard
watching every step.

We are not writing a browser controller from scratch. We extend
[Auto Browser](https://github.com/LvcidPsyche/auto-browser) and add the defensive layer
inside it.

Reach is the point. Agents that already ship with their own built-in browser will not
pick this up automatically. But anything that can call a CLI can trigger it by hand,
which covers most of the agents people actually use.

## Rough design

The core is deterministic. Detection relies on structure that page text cannot argue
with: what is really under a click target, what is actually visible, what a form is
about to submit.

A language model may sit alongside as an advisor. It can raise suspicion, and it can
never lower it. Fooling the advisor costs us a false alarm, not a breach.

<br>

## Where we are

Not much built yet. We are in the research phase of a fresh start, and so far we have
the research notes and a local clone of the base project. Nothing here is a working
product yet.

## Setup

Get the base MCP (Auto Browser), which is the project we build on:
[github.com/LvcidPsyche/auto-browser](https://github.com/LvcidPsyche/auto-browser)

```bash
git clone https://github.com/LvcidPsyche/auto-browser.git external/auto-browser
cd external/auto-browser
docker compose up --build
```

It then serves on `127.0.0.1`:

| Endpoint | URL |
|----------|-----|
| MCP (HTTP) | `http://127.0.0.1:8000/mcp` |
| Tool list | `http://127.0.0.1:8000/mcp/tools` |
| Tool call | `http://127.0.0.1:8000/mcp/tools/call` |
| Dashboard | `http://127.0.0.1:8000/dashboard` |

### Using it

From an MCP client, point it at the HTTP endpoint above, or run the stdio bridge:

```bash
uvx auto-browser-mcp
```

From a plain terminal, no MCP support needed. This is the route any CLI agent uses:

```bash
curl -s http://127.0.0.1:8000/mcp/tools/call \
  -X POST -H 'content-type: application/json' \
  -d '{"name":"browser.create_session",
       "arguments":{"name":"demo","start_url":"https://example.com"}}'
```

Requires Docker. Python 3.10 for our own code.

<br>

## Repository

```
context.md     working context and decisions
research/      literature-grounded research, workstreams 00 to 09
track3/        first attempt, superseded, kept for reference
external/      third-party clones (git-ignored)
assets/        images
```

<br>

<div align="center">

**[Vassu-V](https://github.com/Vassu-V)**
&nbsp;&nbsp;·&nbsp;&nbsp;
**[str-VaibhavThakkar](https://github.com/str-VaibhavThakkar)**

<br>

<sub>No agents were tricked into a free trial during the making of this project.<br>
Several were tempted.</sub>

<br>

</div>
