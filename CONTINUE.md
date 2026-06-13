# CONTINUE — Where we are, where to go next

> **This doc is the "resume point" for the next session.** It's the
> first file to read when coming back to the project. It links to the
> 3 repos, summarizes the last decision, and lists the open questions
> that need your input.

---

## TL;DR

We are at the **end of MVP1, start of MVP2**. MVP1 proved both
lightchain (our home-grown orchestrator) and langgraph can run the
same 5-step pomodoro pipeline. We measured them across 3 ideas and
1.5 ideas, the wall-time and token numbers are within 30% of each
other — closer than the first headline suggested.

The next 2 MVPs are:

1. **MVP2-0 — InteractiveBrowser** (interactive Playwright wrapper
   for QA workers) — see `docs/MVP2-0.md`
2. **MVP2-1 — Gray area providers for langgraph** (`BaseChatModel`
   subclasses that hit MiniMax / Claude.ai / Codex internal APIs)
   — see new repo `agent-ops-langgraph-providers`

A complex E2E test (build frontend + SDE uses a `github` tool to
create a new repo and commit) is in the **backlog** — see TODO.md.

---

## 3 repos (private)

| Repo | URL | What it is |
|---|---|---|
| **agent-ops** (main) | https://github.com/yuanfengli168/agent-ops | The orchestrator + docs + roadmap |
| **agent-ops-lightchain** | https://github.com/yuanfengli168/agent-ops-lightchain | The 131-line `lightchain` orchestrator + MVP1 example |
| **agent-ops-langgraph** | https://github.com/yuanfengli168/agent-ops-langgraph | Same MVP1 in `langgraph` for comparison |
| **agent-ops-langgraph-providers** | https://github.com/yuanfengli168/agent-ops-langgraph-providers | (NEW) 3 `BaseChatModel` subclasses for gray-area APIs |

All 3 are **private** on github.com/yuanfengli168.

---

## Last decision (2026-06-13)

> **Adopt lightchain as the default orchestrator. Keep langgraph as
> a regression test + a fallback for when we need cycles / human-in-
> the-loop / persistent threads.**

The reasoning: lightchain matches the agent-ops "minimal deps,
gray-area-friendly" philosophy. Langgraph has a real D4 win
(resume from checkpoint) but it's 80MB+ of deps and requires
learning `LastValue` / `Annotated` / `RetryPolicy`. The MVP1 token
and time data showed both prototypes are within 30% of each other
on average — the operational advantage of langgraph is real but
smaller than the first single-idea run suggested.

Full data: [`docs/MVP1-TOKEN-COMPARISON.md`](MVP1-TOKEN-COMPARISON.md).
Full qualitative analysis: [`docs/MVP1-COMPARISON.md`](MVP1-COMPARISON.md).

---

## What we built (chronological)

| Date | What | Commit |
|---|---|---|
| 2026-06-12 | Agent-ops roadmap + vision doc | `docs/TODO.md` |
| 2026-06-12 | DESIGN.md + ARCHITECTURE.md | (main repo) |
| 2026-06-12 | LIGHTCHAIN.md (langchain/langgraph deep-dive) | (main repo) |
| 2026-06-12 | MVP1-PROTOTYPES.md (the spec) | (main repo) |
| 2026-06-12 | MVP2-0.md (InteractiveBrowser spec) | (main repo) |
| 2026-06-13 | MVP1 lightchain prototype + pomodoro end-to-end | `agent-ops-lightchain` |
| 2026-06-13 | MVP1 langgraph prototype + pomodoro end-to-end | `agent-ops-langgraph` |
| 2026-06-13 | Multi-idea × 2-orch comparison (3 ideas) | `docs/MVP1-TOKEN-COMPARISON.md` |
| 2026-06-13 | Honest verdict update (no more "5x faster" hype) | `docs/MVP1-COMPARISON.md` |

---

## What to do next (in priority order)

### P0 — Done

- [x] `agent_ops.lightchain` orchestrator (131 lines, 8/8 tests)
- [x] `agent_ops_langgraph.CompiledStateGraph` prototype for comparison
- [x] Token-comparison doc with 3 ideas × 2 orchestrators
- [x] MVP2-0 spec (InteractiveBrowser)
- [x] Continuous-comparison data plane (`MVP1_IDEA` / `MVP1_OUT_DIR` env vars)

### P1 — In flight (next session)

- [ ] **MVP2-0 — implement InteractiveBrowser** in both prototypes
- [ ] **MVP2-1 — `agent-ops-langgraph-providers`** repo: 3
      `BaseChatModel` subclasses (MiniMax, Claude Code, Codex)
- [ ] Update both `MVP1-COMPARISON.md` and `MVP1-TOKEN-COMPARISON.md`
      to point at the new providers repo

### P2 — Backlogged

- [ ] Complex E2E test: build a frontend, then SDE uses a `github`
      tool to create a new test repo and commit. This needs:
      - A `github` tool wrapper (`gh` CLI under the hood)
      - A `tool-calling` abstraction on top of our 2 orchestrators
      - Probably ~1 day of work
- [ ] `inbox` / context loader (drop a folder, get a brief)
- [ ] Voice → prompt optimizer (original TODO from repo root)
- [ ] Lightchain → langgraph equivalence test ("same MVP1 → byte-
      similar output")

### P3 — Distant

- [ ] MVP3 cycles / human-in-the-loop (when we have a real use case)
- [ ] Deploy runner (anti-bot is the blocker)
- [ ] Time-budget runner (8-hour dream infrastructure)
- [ ] Checkpoint + resume (D4 in our debug dimensions)

---

## Open questions waiting on you (Jacky)

1. **MVP2 build order**: InteractiveBrowser first, or gray-area
   providers first? (Both are P1.)
2. **MVP2 InteractiveBrowser scope**: L1 (read-only), L2 (read + simple
   interaction), or L3 (read + interact + write with confirm)?
3. **Gray-area providers**: 3 to implement (MiniMax, Claude Code,
   Codex). Which first?
4. **Lightchain → main repo**: merge `agent-ops-lightchain/src/lightchain.py`
   into `agent-ops/src/agent_ops/lightchain.py`? Or keep separate?
5. **MVP3 vision**: is "drop folder → ship in 8h" still the goal, or
   has the priority shifted to something else?

If you answer these, the next session has a clear runway.

---

## Quick-recovery instructions (for the next session)

```bash
# 1. Clone the 3 repos if you don't have them yet
mkdir -p ~/repos && cd ~/repos
git clone https://github.com/yuanfengli168/agent-ops.git
git clone https://github.com/yuanfengli168/agent-ops-lightchain.git
git clone https://github.com/yuanfengli168/agent-ops-langgraph.git

# 2. Read this doc first
cat agent-ops/CONTINUE.md

# 3. Then read the open questions section
# 4. Then pick a P1 item from "What to do next"
```

---

## Glossary (in case you come back cold)

- **MVP1**: the 5-step pomodoro pipeline (brief → spec →
  {implement, readme} → qa). Both prototypes have it. See
  `docs/MVP1-COMPARISON.md` and `docs/MVP1-TOKEN-COMPARISON.md`.
- **MVP2-0**: the InteractiveBrowser tool. See `docs/MVP2-0.md`.
- **Lightchain**: our 131-line home-grown DAG orchestrator
  (Step, Parallel, Pipeline). In `agent-ops-lightchain/src/lightchain.py`.
- **Langgraph**: the popular external library. Used in
  `agent-ops-langgraph/examples/mvp1.py` for comparison.
- **D1-D5**: the 5 debug dimensions (prompt visibility, response
  visibility, hang-kill, resume-from-step, retry-reproducibility).
  See `docs/MVP1-COMPARISON.md` § "5 debug dimensions, head-to-head".
- **Gray area**: using your existing AI subscriptions
  (Claude Pro, MiniMax 海螺AI, Copilot) via their internal APIs
  instead of paying per-call. The whole point of agent-ops.
- **8-hour dream**: the vision where you drop a folder before bed
  and the system ships code while you sleep. Tracked in
  `docs/TODO.md`.
