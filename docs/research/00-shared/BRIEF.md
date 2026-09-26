# Research brief — adversarial web content vs. autonomous browsing agents

> Every research agent reads this first. Follow the output contract exactly so the
> five workstreams merge cleanly.

---

## Why we are doing this

We are building defensive middleware for autonomous web-browsing agents. Our first
attempt failed a fairness test we set ourselves: we invented the attacks *and* the
detector, so the detector caught our own keywords. That proves nothing.

**This round we ground everything in published research instead.** We want the attack
taxonomy, the prevalence data, and the mitigation landscape to come from people who
measured them — not from our imagination.

Ground truth comes from the literature. If the literature disagrees with our intuition,
the literature wins and you say so.

## The subject, precisely

Attacks that work against **software agents browsing the web**, where the agent reads
a DOM, an accessibility tree, or a screenshot and then acts.

Two families, both in scope:

1. **Agent-targeted** — content authored to manipulate a model: indirect prompt
   injection in page content, instructions hidden from humans but legible to parsers,
   tool/function-call hijacking.
2. **Human-targeted that transfers to agents** — dark patterns, clickjacking/overlays,
   confirmshaming, drip pricing, pre-checked opt-ins, obstructed cancellation. These
   have a large HCI measurement literature and much of it applies to agents, sometimes
   *more* strongly because agents lack visual scepticism.

Out of scope: network attacks, malware distribution, phishing aimed purely at humans,
browser CVEs. Unless a paper ties them to agent workflows.

---

## Source rules — the part that matters most

**Never invent a citation.** A fabricated paper, author, arXiv ID or DOI is the single
worst outcome of this task; it is worse than returning nothing. We may put these in a
formal report, and a reader may look one up.

Therefore:

- **Fetch every source you cite.** Open the abstract page or PDF. If you could not
  fetch it, mark it `"verified": "unverified"` and say so. Do not quietly upgrade a
  search-result snippet into a citation.
- Prefer **peer-reviewed** venues (USENIX Security, IEEE S&P, CCS, NDSS, CHI, CSCW,
  WWW, NeurIPS/ICML/ICLR) — then **arXiv preprints**, which are fine and often the only
  place recent agent-security work exists.
- Prefer **2023-2026** for agent-specific work; older is fine for dark-pattern
  taxonomy, which is a mature field.
- Record real numbers wherever the paper gives them: attack success rates, sample
  sizes, prevalence percentages, benchmark scores. Numbers are what we need.
- When sources disagree, record the disagreement rather than picking a winner.
- Distinguish **measured** from **proposed**. "This defence was evaluated at 92% on
  benchmark X" and "the authors suggest this might help" are very different claims.

---

## Output contract

Each agent writes **only inside its own directory**. Three files:

### 1. `FINDINGS.md`
Your substantive output. Structure it however suits the material, but every
non-obvious claim carries a `[A-01]`-style tag matching an entry in `sources.json`.
Lead with a short summary of what you actually established.

### 2. `sources.json`
Machine-readable, so the citations agent can cross-check you.

```json
[
  {
    "claim_id": "A-01",
    "claim": "one sentence, specific and checkable",
    "source": {
      "title": "...",
      "authors": ["..."],
      "year": 2025,
      "venue": "arXiv | USENIX Security | CHI | ...",
      "arxiv_id": "2502.xxxxx",
      "doi": null,
      "url": "https://..."
    },
    "evidence_quote": "at most 25 words, verbatim, in quotes",
    "verified": "fetched",
    "confidence": "high"
  }
]
```

`verified` is `fetched` or `unverified`. `confidence` is `high`, `medium` or `low`.
Keep `evidence_quote` under 25 words — we are not reproducing anyone's paper.

### 3. `LOG.md`
Append-only running log, written **as you go**, not at the end. One line per
meaningful step: what you searched, what you opened, what you concluded, what you
discarded and why. Timestamp each entry. This is how the team follows your reasoning
and how we recover if you are interrupted.

---

## Hard rules

- Write **only** inside your own assigned directory.
- Do **not** read or modify `track3/`, `engine/`, `PROJECT_CHARTER.md`, or any other
  agent's research directory. `track3/` is a superseded prototype — ignore it entirely.
- Do not create, stage, or commit anything to git.
- Do not write code. This round is research only.
- Report what the literature says, including where it is thin or contradicts us.
  **Negative and inconvenient findings are valuable** — if the research says a defence
  we like does not work, that is exactly what we need to hear now.

## What we will do with this

The end goal is an MCP proxy that sits between an agent and a browser MCP server and
audits every action. Your research decides **what it should detect and why**, and gives
us the citations to defend those choices. Keep that use in mind: a finding we can
implement and measure beats a finding we can only admire.
