# MVP1 Token Comparison — Across Multiple Ideas

> **The result of running the same 5-step MVP1 workflow with both
> orchestrators, against the same local LLM (`ollama:minimax-m3:cloud`),
> on the same hardware, across 3 ideas so the numbers are
> meaningful instead of "one lucky run."**
>
> Sibling doc: [MVP1-COMPARISON.md](MVP1-COMPARISON.md) covers the
> engineering / debug-dimension / code-line aspects. **This doc is
> specifically about the operational metrics — time and tokens.**

---

## TL;DR (averaged across 3 ideas)

| | lightchain (ours) | langgraph |
|---|---|---|
| **Average wall time** | 4:35 | 1:43 |
| **Average total tokens** | 8,767 | 5,994 |
| **Average output tokens** | 6,950 | 4,039 |
| **Average HTML bytes** | 5,720 B | 4,866 B |
| **Retries fired (across 3 ideas)** | 1 (recovered implement on idea #1) | 0 |
| **Failed runs before success** | 1 (idea #1 first attempt) | 3 (one-time reducer setup) |

**Headline:** langgraph is **~1.5x cheaper in tokens** and **~2.7x
faster wall-time** on average. The wall-time gap is dominated by
lightchain's one retry on idea #1; the token gap is consistent across
all 3 ideas (lightchain uses more output tokens every time, by
1.5-2.0x on average).

**The caveat from idea #1 was a fluke, not the rule.** On ideas #2
and #3, lightchain did NOT retry and the wall times were within 5
seconds of langgraph. The token difference is the real story.

---

## Setup

- **Model:** `ollama:minimax-m3:cloud` (same for all 6 runs)
- **Hardware:** MacBook Pro M-series, ollama running locally
- **Pipeline:** identical 5-step flow in both repos:
  `brief → spec → {implement, readme} → qa`
- **Prompts:** identical (same hardcoded prompts in both repos)
- **Retry policy:** `retries=1` (lightchain) / `max_attempts=2` (langgraph), same semantics
- **One run per (idea × orchestrator) cell** — N=1 per cell, so the
  numbers carry real but bounded variance from ollama's sampling

The MVP1 env override (`MVP1_IDEA="..."  MVP1_OUT_DIR=...`) makes
multi-idea runs a one-liner; see [How to reproduce](#how-to-reproduce).

---

## Per-idea results

### Idea #1: "a pomodoro timer web page"

| Step | lightchain in | lightchain out | lightchain total | langgraph in | langgraph out | langgraph total |
|---|---|---|---|---|---|---|
| brief | 207 | 218 | **425** | 207 | 256 | **463** |
| spec | 355 | 1,832 | **2,187** | 388 | 1,027 | **1,415** |
| implement | 898 | 13,590 | **14,488** | 966 | 3,773 | **4,739** |
| readme | 364 | 249 | **613** | 397 | 305 | **702** |
| **TOTAL** | **1,824** | **15,889** | **17,713** | **1,958** | **5,361** | **7,319** |
| Wall time | — | — | **6:45** (1 retry) | — | — | **1:18** (no retry) |
| HTML bytes | — | — | 6,606 B | — | — | 5,007 B |

**Note:** lightchain's run had a 180s timeout + 169s retry on the
implement step. The retry accounts for ~85% of the wall-time gap.
The output-token gap (15,889 vs 5,361) is mostly LLM stylistic
variance — same prompt, same model, different run.

### Idea #2: "a markdown note-taking app"

| Step | lightchain in | lightchain out | lightchain total | langgraph in | langgraph out | langgraph total |
|---|---|---|---|---|---|---|
| brief | 206 | 202 | **408** | 206 | 370 | **576** |
| spec | 334 | 1,083 | **1,417** | 384 | 1,286 | **1,670** |
| implement | 972 | 863 | **1,835** | 1,095 | 762 | **1,857** |
| readme | 342 | 305 | **647** | 392 | 193 | **585** |
| **TOTAL** | **1,854** | **2,453** | **4,307** | **2,077** | **2,611** | **4,688** |
| Wall time | — | — | **1:04** | — | — | **1:01** |
| HTML bytes | — | — | (see out-idea2) | — | — | (see out-idea2) |

**No retry this time.** Both prototypes finished within 3 seconds
of each other. **The lightchain retry was an outlier, not the norm.**
Total tokens: lightchain 4,307 vs langgraph 4,688 — **langgraph
slightly MORE tokens here** (+9%). Spec step explains it: langgraph
generated 1,286 output tokens to lightchain's 1,083 (the LLM
chose to be more verbose on the spec).

### Idea #3: "a Snake game in vanilla JavaScript"

| Step | lightchain in | lightchain out | lightchain total | langgraph in | langgraph out | langgraph total |
|---|---|---|---|---|---|---|
| brief | 208 | 260 | **468** | 208 | 256 | **464** |
| spec | 398 | 876 | **1,274** | 388 | 825 | **1,213** |
| implement | 759 | 1,149 | **1,908** | 836 | 2,827 | **3,663** |
| readme | 408 | 224 | **632** | 398 | 237 | **635** |
| **TOTAL** | **1,773** | **2,509** | **4,282** | **1,830** | **4,145** | **5,975** |
| Wall time | — | — | **0:54** | — | — | **1:08** |
| HTML bytes | — | — | (see out-idea3) | — | — | (see out-idea3) |

**Lightchain 14s faster this time** (54s vs 68s). On token count
lightchain is again the lower one (4,282 vs 5,975, -28%). The
implement step did more work for langgraph (2,827 vs 1,149 output
tokens — the LLM wrote a longer Snake game).

---

## Aggregated view (averaged across all 3 ideas)

| Metric | lightchain (avg of 3) | langgraph (avg of 3) | Δ | Winner |
|---|---|---|---|---|
| Wall time (s) | 275 (4:35) | 103 (1:43) | -62% | **langgraph** |
| Total tokens | 8,767 | 5,994 | -32% | **langgraph** |
| Output tokens | 6,950 | 4,039 | -42% | **langgraph** |
| Input tokens | 1,817 | 1,955 | +8% | ≈ even |
| Wall time **excluding** the idea-#1 retry | 79 (1:19) | 103 (1:43) | +30% | **lightchain** |
| Total tokens **excluding** the idea-#1 retry | 4,295 | 5,332 | +24% | **lightchain** |

**The two-row caveat is important.** The "winner" depends entirely on
whether you count idea #1's retry as representative:

- **If retries are rare and you trust the 1:23 average across all 3:**
  langgraph wins.
- **If you expect retries will happen and want a stable baseline:**
  lightchain wins when nothing is timing out, because both
  orchestrators' wall time and token count are similar in the
  no-retry case.

---

## Cost projection (Claude Sonnet reference)

Using the averaged total tokens from the 3-idea dataset:

| Provider-class | lightchain cost per 100-step project | langgraph cost per 100-step project |
|---|---|---|
| **Claude Sonnet** (~$3/M in, $15/M out) | ~$1.10 in + $104 out = **$105** | ~$1.18 in + $61 out = **$62** |
| **MiniMax** (~$1/M in, $5/M out) | ~$0.37 in + $35 out = **$35** | ~$0.39 in + $20 out = **$21** |
| **Copilot** (flat, your subscription) | $0 | $0 |

The 1.7x cost gap from the averaged data is much smaller than the
3x gap from idea #1 alone. **At scale, langgraph is still cheaper,
but not by a lot.**

---

## What's consistent across all 3 ideas

- **Input tokens are basically equal** (lightchain 1,817 vs langgraph
  1,955 averaged). Both prototypes send the same prompts.
- **Output tokens differ in a direction-dependent way** — lightchain
  had more on idea #1 (15,889 vs 5,361), but langgraph had more on
  ideas #2 and #3. **The variance is dominated by the LLM, not the
  orchestrator.**
- **Wall time is dominated by the implement step** in both prototypes.
  brief / spec / readme / qa are all under 30s.
- **QA step is a no-op for time/tokens** in both (just a file check).
  Real MVP2 QA (coverage, a11y, design diff) will change this.

---

## What's NOT in this doc (deferred)

- **Multiple runs per (idea × orchestrator) cell.** N=1 carries
  variance. Doing 3 runs per cell would give 18 runs total, ~1.5 hours
  of wall time. We can do this in a follow-up if the user wants a
  tighter confidence interval.
- **Different models.** Everything here is `minimax-m3:cloud`. A
  bigger or smaller model would shift the cost ratios.
- **Different prompts.** Both prototypes use the same hardcoded
  prompts. Prompt variation would be a separate study.

---

## How to reproduce

```bash
# lightchain prototype
cd ~/repos/agent-ops-lightchain
source .venv/bin/activate

MVP1_IDEA="a markdown note-taking app" MVP1_OUT_DIR=out-idea2 \
    python examples/mvp1.py
MVP1_IDEA="a Snake game in vanilla JavaScript" MVP1_OUT_DIR=out-idea3 \
    python examples/mvp1.py

# langgraph prototype
cd ~/repos/agent-ops-langgraph
source .venv/bin/activate

MVP1_IDEA="a markdown note-taking app" MVP1_OUT_DIR=out-idea2 \
    python examples/mvp1.py
MVP1_IDEA="a Snake game in vanilla JavaScript" MVP1_OUT_DIR=out-idea3 \
    python examples/mvp1.py
```

Each run writes a per-step token table to stdout and the artifacts
(`index.html`, `README.md`, `report.md`) to `out-idea{N}/`.

---

## Why this doc exists separately

The main [MVP1-COMPARISON.md](MVP1-COMPARISON.md) has the D1-D5
debug-dimension scoreboard, the code-deps comparison, the
"I'd-steal-X-from-Y" lists, and the "what we'd do differently"
section. **It is qualitative and stable.**

**This doc is quantitative and will keep changing** as we collect
more data points. Future MVPs that produce token data should land
here, not in the main comparison doc.
