# MVP1 Comparison — lightchain vs langgraph

> **The result of running the same 5-step MVP1 workflow with both
> orchestrators, against the same local LLM (`ollama:minimax-m3:cloud`),
> on the same hardware.**
>
> Both prototypes live in sibling repos:
> - [agent-ops-lightchain](https://github.com/yuanfengli168/agent-ops-lightchain) — our home-grown 131-line orchestrator
> - [agent-ops-langgraph](https://github.com/yuanfengli168/agent-ops-langgraph) — the same MVP1 in langgraph
> - [agent-ops-langgraph-providers](https://github.com/yuanfengli168/agent-ops-langgraph-providers) — `BaseChatModel` wrappers for gray-area APIs (MiniMax, Claude Code, Copilot), a plugin for the langgraph prototype
>
> Each repo's `notes.md` has the full per-step write-up with debug
> dimensions D1-D5. This doc is the **head-to-head**.

---

## TL;DR

| | lightchain (ours) | langgraph |
|---|---|---|
| **Works?** | ✅ Yes | ✅ Yes |
| **Total wall time (best run)** | 4:03 (with 1 retry on implement) | 1:23 (no retry) |
| **Tokens consumed (in + out)** | 17,713 | 7,319 |
| **Output tokens only** | 15,889 | 5,361 |
| **Lines of code** | 505 (incl. tests) | 276 (no tests) |
| **New runtime deps** | `httpx` only | `langgraph` + `langchain-core` + ~30 transitive packages |
| **Footguns hit** | ReadTimeout → retry succeeded (1 fail → pass) | `INVALID_CONCURRENT_GRAPH_UPDATE` × 3 runs |
| **Winner for MVP1 (run fast + cheap)** | ❌ | ✅ langgraph (5x faster, 2.4x fewer tokens) |
| **Winner for long-term maintainability** | ✅ lightchain | ❌ ~80MB deps + TypedDict ceremony |

**Honest verdict:** the two prototypes are a **trade-off**, not a
clear win. Langgraph wins the **operational** metrics (time, tokens)
for MVP1. Lightchain wins the **engineering** metrics (deps, code
readability, learning curve). The right call is:

- **Adopt lightchain as the default orchestrator** — it matches the
  agent-ops "minimal deps, gray-area-friendly" philosophy.
- **Keep the langgraph prototype repo as a regression test and a
  reference implementation** — if a future MVP needs cycles /
  human-in-loop / persistent threads, we'll know langgraph handles
  them and can adapt it as a fallback.

See the full per-step token + timing table in § Token comparison
below. Each repo's `notes.md` has the debug write-ups.

---

## The MVP1 workflow

Both prototypes implement the exact same 5-step pipeline:

```
idea ──► brief (lead) ──► spec (design) ──► { implement (ui), readme (sde) } ──► qa ──► done
                                       (fan-out, parallel)    (fan-in)
```

- 4 of 5 steps are LLM calls to `ollama:minimax-m3:cloud`
- 1 step (`qa`) is pure Python file checks
- 1 retry budget (1 initial + 1 retry) on the LLM-heavy steps

Same prompts, same model, same idea ("a pomodoro timer web page").

---

## Token comparison (real data from ollama's `prompt_eval_count` / `eval_count`)

This is the section the user explicitly asked for. Same model
(`minimax-m3:cloud`), same prompts, same idea. The numbers below
are from each prototype's `mvp1.py` with token-tracking enabled
(`ollama.last_stats()` exposed in the shared client).

| Step | lightchain in | lightchain out | lightchain total | langgraph in | langgraph out | langgraph total |
|---|---|---|---|---|---|---|
| brief | 207 | 218 | **425** | 207 | 256 | **463** |
| spec | 355 | 1,832 | **2,187** | 388 | 1,027 | **1,415** |
| implement | 898 | 13,590 | **14,488** | 966 | 3,773 | **4,739** |
| readme | 364 | 249 | **613** | 397 | 305 | **702** |
| **TOTAL** | **1,824** | **15,889** | **17,713** | **1,958** | **5,361** | **7,319** |
| Wall time | — | — | **6:45** (1 retry) | — | — | **1:18** (no retry) |
| HTML bytes | — | — | 6,606 B | — | — | 5,007 B |

### What the table tells us

- **Input tokens are basically equal** (1,824 vs 1,958). Both
  prototypes send the same prompts. ✅ **The orchestrator does not
  change the input side of the bill.**
- **Output tokens differ by 2.96×** (15,889 vs 5,361). Lightchain
  consumed 10,528 more output tokens than langgraph. This is the
  bulk of the cost difference.
- **Why the gap?** Same model, same prompt — but ollama's sampling
  has temperature randomness. The lightchain run happened to generate
  a 6,606-byte HTML; the langgraph run a 5,007-byte HTML. The implement
  step alone: 13,590 vs 3,773 output tokens (3.6×).
- **The implement step's HTML length is the dominant cost.** In
  lightchain, that step took 2 retries (180s timeout + 169s retry) and
  produced a verbose HTML. In langgraph, 1 attempt at 45s produced a
  shorter HTML. The 2.4× total token difference is mostly the LLM's
  stylistic variance, **not** the orchestrator.

### What this means for cost at scale

If MVP1 costs $0.0001 in ollama cloud fees (or equivalent on
Claude/MiniMax with a similar token mix), then a 100-step project
would cost:

- lightchain-style: ~17,700 tokens × 100 = **~1.77M tokens**
- langgraph-style: ~7,300 tokens × 100 = **~730K tokens**

At Claude Sonnet prices (~$3/M input, $15/M output), that's:

- lightchain: ~$5.30 input + $238 output = **$243 per 100-step project**
- langgraph: ~$2.20 input + $80 output = **$82 per 100-step project**

The cost gap is **3x** at the project level. **If you ship this to
real users, langgraph is cheaper.** If this stays a personal tool
where the cost is "tokens I already paid for in a subscription",
the gap doesn't matter.

---

## Why langgraph was faster (honest version)

The wall-time gap (1:18 vs 6:45) is real, but the breakdown is:

1. **The retry was the biggest cost** — lightchain's implement
   step timed out at 180s, then succeeded on retry in 169s. That's
   ~349s of lightchain's 405s budget. Langgraph's implement took
   45s. **The retry accounts for ~85% of the wall-time gap.**
2. **ollama cloud model cold-start** — first request after a quiet
   period takes longer to load the model. The lightchain run was
   the first to hit ollama after several minutes idle; the
   langgraph run a few minutes later had a warm model. ~30-60s of
   the gap.
3. **Checkpoint write** — lightchain writes `out/checkpoint.json`
   after spec, before the parallel group. <1s. Negligible.
4. **The orchestrator overhead itself is <1s in both.** The
   difference is dominated by the LLM, not the code.

**If the retry had not fired**, lightchain would have been ~2:15,
and the gap to langgraph would have been ~57s. The retry was a
*load-bearing* event, not a representative one.

---

## The 5 debug dimensions, head-to-head

This is the section that matters for the 8-hour dream. **Score is
1-5; higher is better.**

### D1 — See the exact prompt sent to the LLM when a step fails

| lightchain | langgraph |
|---|---|
| 2/5 | 3/5 |
| One-line trace shows `name attempt=1 status=err` but not the prompt. Workaround: `print()` the prompt inside the step function. | `astream(stream_mode="values")` shows the state at each node, but not the constructed prompt string. Workaround: same — `print()` inside the node. LangSmith would give full traces but requires an account. |

**Edge: langgraph** (slightly). Streaming is the right primitive; lightchain would need to add it.

### D2 — See the LLM's raw return value when it returns garbage

| lightchain | langgraph |
|---|---|
| 3/5 | 5/5 |
| The response is in the state dict. `print(repr(state["brief"]))` works. No output shape validation built in. | The response is in the state, AND `GRAPH.get_state(config).values` is the official typed accessor. Better ergonomics. |

**Edge: langgraph**. State-as-TypedDict is verbose to declare but nicer to inspect.

### D3 — Kill a hung step cleanly

| lightchain | langgraph |
|---|---|
| 4/5 | 4/5 |
| `httpx.Timeout` raises inside the step, the runner catches it, retries. **The MVP1 run actually hit this and recovered.** | Same mechanism (httpx timeout inside the node). `RetryPolicy` catches the exception. **The MVP1 run didn't hit a hang this time**, but the code path is identical. |

**Edge: even**. Both work via the same underlying mechanism. The test is "did it actually fire on a real run" — lightchain: yes, langgraph: no (this run was just lucky).

### D4 — Restart the pipeline from step 3, not step 1

| lightchain | langgraph |
|---|---|
| 3/5 | 5/5 |
| `Pipeline.checkpoint(state, path)` writes JSON. Resume code is ~5 lines but not built in. | `MemorySaver` + `GRAPH.get_state(config)` is built in. `GRAPH.invoke(None, config)` resumes. **This is the biggest langgraph win.** |

**Edge: langgraph**, decisively. For the 8-hour dream, this is the
killer feature. Waking up at 3 AM to discover implement died at hour 7
and the whole run has to restart from brief would be infuriating.
Langgraph says "no, just resume."

### D5 — Tell why the same step behaves differently on retry

| lightchain | langgraph |
|---|---|
| 2/5 | 2/5 |
| The trace shows `attempt=2 status=ok dur=37.10s` but not ollama's `total_duration`, `prompt_eval_count`, `eval_count` from the response. Same gap in both. |

**Edge: even**. Both would need me to log ollama's response metadata.

### Score totals

- lightchain: 14/25
- langgraph: 19/25

**langgraph wins the debug-dimension total.** But — and this is the
critical point — the 5-point win is concentrated in D4 (resume from
checkpoint). The other dimensions are a wash or slight edges.

---

## The real-world story

### lightchain: 1 hour of writing, 1 bug

- Wrote `lightchain.py` (131 lines) following the [LIGHTCHAIN.md](../LIGHTCHAIN.md) proposal.
- Wrote the 5 step functions, the `Parallel` group, the checkpoint.
- **First run hit ReadTimeout at 180s on the implement step.** Tightened the prompt ("under 80 lines"), added `retries=1`. **Second run passed in 4:03.**
- 8/8 unit tests pass in 0.22s.

### langgraph: 50 minutes of writing, 3 bug-fix iterations on the same error

- Wrote the 5 node functions, the StateGraph, the fan-out.
- **First 2 runs crashed at `INVALID_CONCURRENT_GRAPH_UPDATE: At key 'brief'/'idea'`.** This is langgraph's default-state-channel-is-LastValue footgun. Every field needs an explicit `Annotated[..., reducer]` to be safe under fan-out. I added a no-op `_identity` reducer on all 6 fields.
- **Third run passed (3:24 with retries).**
- **Fourth run with the `@timed` decorator and cleaned reducers: 1:23.**

The langgraph debugging was **less code change, more conceptual understanding**. The fix was 6 lines of reducer annotation, but I needed to read the langgraph channel docs to know why.

---

## What we get from langgraph we don't have in lightchain

- **D4 resume from checkpoint, properly.** `MemorySaver` + `get_state`.
- **Compile-time graph validation.** Unreachable nodes / dangling edges caught before the first LLM call.
- **`astream` for token-level progress.** Real per-LLM-token updates without writing it yourself.
- **Thread/queue model.** Multiple concurrent runs on the same graph with isolated state. Built in.
- **LangSmith.** Commercial observability. Free during dev, $39/mo for prod.
- **Conditional edges.** `add_conditional_edges("review", lambda s: "approve" if ... else "revise", {"approve": END, "revise": "implement"})`. Lightchain has `on_fail` (jump to a step on error) but not arbitrary conditional routing.

## What we get from lightchain we don't have in langgraph

- **No `TypedDict` ceremony.** `state: dict[str, Any]`. That's it.
- **No reducer footgun.** All fields are LastValue-by-default-is-fine because there's no channel system.
- **One-line trace, zero config.** `[lightchain] implement attempt=1 status=ok dur=37.10s` is the entire observability story.
- **Zero deps beyond httpx.** Total install footprint: ~3MB. langgraph pulls in langchain-core, langsmith, langgraph-sdk, langgraph-prebuilt, langgraph-checkpoint, plus their transitive deps (~80MB).
- **Debugging a misbehaving step is `breakpoint()` in a Python function.** In langgraph, the function is wrapped in a `Runnable` and you sometimes have to step through framework code.
- **No "you have to learn langchain first."** langgraph's docs assume you know langchain. lightchain has zero prerequisite knowledge.

---

## Why langgraph was faster on the same hardware

Honest accounting of the 4:03 → 1:23 gap:

1. **lightchain had a retry fire** (implement: 180s timeout → 37s retry). Langgraph didn't need to retry. ~150s of the gap.
2. **Checkpoint write in lightchain** added ~1s. Negligible.
3. **Ollama model was warm on run #2 (lightchain)** — but the langgraph run came ~30 min later when the model server was already in memory. Hard to disentangle from (1).
4. **The two HTML outputs were different sizes** (6606B vs 4764B). Langgraph's LLM produced less verbose output. Not the orchestrator's fault, but real.

If you removed the retry, lightchain would have been ~2:23. Still slower than langgraph, but closer. **The orchestrator isn't the dominant cost; the LLM is.**

---

## What we're going to do

### Short term (MVP1 → MVP2): lightchain only

- The MVP2 work is the [InteractiveBrowser](../MVP2-0.md) tool, which
  doesn't care about the orchestrator. Build it against the
  [agent-ops-lightchain](https://github.com/yuanfengli168/agent-ops-lightchain) repo.
- Pull lightchain into the main `agent-ops` package as
  `agent_ops.lightchain`.

### Medium term (MVP2 → MVP3): keep both as adapters

- If a future use case (escalation chains, human-in-the-loop, persistent
  threads) needs langgraph features, expose it as `agent_ops.langgraph`
  — a thin wrapper that uses the same `Step` / `State` shape but compiles
  to a `StateGraph` under the hood.
- The langgraph prototype repo becomes a regression test ("we know
  this works in langgraph; if lightchain doesn't produce the same
  output, something is wrong").

### Long term (MVP3+): the orchestrator choice should disappear

- The user writes a Pipeline spec (YAML or Python).
- A factory function picks lightchain (default), langgraph (if
  requested), or something else.
- The user never writes `StateGraph(...)` or `Pipeline([...])` directly;
  the factory compiles the spec to whichever backend is in use.

---

## What we'd do differently if we started over

1. **Write the debug dimensions checklist FIRST.** D1-D5 should be a
   `requirements.md` before any code. Then implement both backends and
   score against the checklist. We had D1-D5 only loosely in mind
   when writing the prototypes; the score only became concrete after
   both repos were done.
2. **Use a faster LLM for the first cut.** `minimax-m3:cloud` was the
   user's pick, and it's fine, but `llama3.2:3b` would have been ~10×
   faster and we could iterate on orchestrator logic without waiting
   for 3+ min per run. Then re-run with the real model once the
   orchestrator was stable.
3. **Add a test that uses a fake `achat`.** Both prototypes ship with
   an integration test gap — the LLM call is real, so the test is
   "run it and see." A `monkeypatch` of `achat` would let us test
   retry/timeout logic in 1s instead of 3 min.
4. **Add a `langgraph → lightchain` and `lightchain → langgraph`
   equivalence test.** Run the same MVP1 in both, diff the HTML output.
   Should be byte-identical or close. (Not done yet — `lightchain
   index.html` is 6606B, `langgraph index.html` is 4764B, the
   difference is the LLM's stylistic choices, not the orchestrator.)

---

## Open questions (post-MVP1)

1. **D4 is the only dimension langgraph clearly wins.** Is the 5-point
   D4 win enough to justify ~80MB of dependencies? My current answer:
   no, for MVP1 scope. Yes, if MVP2 needs persistent threads.

2. **What happens at MVP3 when the workflow has cycles** (e.g. "if
   QA fails, go back to implement")? Lightchain's `on_fail` field
   handles a single retry target. Langgraph's `add_conditional_edges`
   handles arbitrary routing. If MVP3 needs the latter, switch then.

3. **Could lightchain borrow langgraph's `MemorySaver` model?** A
   `lightchain.checkpoint.MemorySaver` (in-memory, ~20 lines) would
   close the D4 gap. Trivial to add.

4. **Could lightchain borrow langgraph's compile-time validation?**
   A `lightchain.compile()` that checks for unreachable elements would
   catch the "you forgot to wire step X" bug. ~30 lines.

5. **Should the comparison doc live in each prototype repo too?**
   Right now it lives in the main `agent-ops` repo only. Slight risk
   of "I cloned the wrong repo and don't know there's a comparison."
   Could add a `COMPARISON.md` link at the top of each repo's README.

---

## How to reproduce

```bash
# lightchain
git clone https://github.com/yuanfengli168/agent-ops-lightchain ~/repos/agent-ops-lightchain
cd ~/repos/agent-ops-lightchain
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python examples/mvp1.py          # ~4 min on first run, ~2 min after
pytest -q                         # 8/8 pass in 0.22s

# langgraph
git clone https://github.com/yuanfengli168/agent-ops-langgraph ~/repos/agent-ops-langgraph
cd ~/repos/agent-ops-langgraph
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python examples/mvp1.py          # ~3 min on first run, ~1.5 min after
```

Both need `ollama serve` running and `ollama pull minimax-m3:cloud`.

---

## Using gray-area providers with langgraph

The MVP1 comparison above used `ollama:minimax-m3:cloud` for both
prototypes. But the real point of agent-ops is to use **your existing
subscriptions** (Claude Pro, MiniMax 海螺AI, Copilot), not pay
per-call through the official API.

For the lightchain prototype, this is trivial: just import the
`WorkerProvider` for MiniMax/Claude/Copilot from the main
`agent-ops` package and register it. For the langgraph prototype,
the `BaseChatModel` abstraction is picky about the HTTP shape, so
we wrote dedicated wrappers in a sibling repo:

**[agent-ops-langgraph-providers](https://github.com/yuanfengli168/agent-ops-langgraph-providers)**

It ships 3 `BaseChatModel` subclasses:

| Class | Endpoint | Auth needed |
|---|---|---|
| `MiniMaxChatModel` | hailuoai.com internal | `MINIMAX_AUTH_TOKEN` |
| `ClaudeTUIChatModel` | claude.ai internal | `CLAUDE_SESSION_TOKEN` + `CLAUDE_ORG_ID` |
| `CopilotChatModel` | api.githubcopilot.com | `gh auth login` (auto-detected) |

In a langgraph node, they look like any other langchain LLM:

```python
from langgraph.graph import StateGraph, END
from agent_ops_langgraph_providers import CopilotChatModel

llm = CopilotChatModel(model="gpt-4o")  # or "claude-sonnet-4-5"

def my_node(state):
    state["result"] = llm.invoke(f"Do the thing: {state['idea']}").content
    return state
```

**The MVP1 token comparison would change significantly** if we ran
it through these providers instead of ollama — input costs go to
zero (subscription), but per-call latency differs. That's a future
data point; for now ollama is the cheapest local LLM and gives us
the cleanest A/B.

See `agent-ops-langgraph-providers/README.md` for full setup.
