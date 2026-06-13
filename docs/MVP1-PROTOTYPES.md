# MVP1 — Two Prototypes: lightchain vs langgraph

> **Status:** spec only, not implemented. This doc lays out a small but
> realistic workflow and shows what it looks like in both our home-grown
> `lightchain` and in `langgraph`. After reading this, the user picks
> which one (or both) we implement for real.

---

## 1. Why two prototypes

We have two candidate orchestration layers:

- **`lightchain`** — proposed in [LIGHTCHAIN.md](LIGHTCHAIN.md). ~150 lines,
  zero deps, declared-in-Python DAG, easy to debug.
- **`langgraph`** — the popular external library. Real, mature, with cycles
  / conditional branches / checkpointing built in.

We don't yet know which is the better fit. The fastest way to find out
is to write **the same workflow** in both, side by side, and see which
one we like more. That's what this doc does.

Both prototypes run on **Ollama** locally. The user can
`ollama pull minimax-m3:cloud` and run both prototypes without any
cloud subscriptions, no Copilot, no claude-tui. This makes the comparison
honest — same LLM, same hardware, the difference is purely the
orchestration layer.

---

## 2. MVP1 scope

**Input:** a string (an idea, e.g. `"a pomodoro timer web page"`).

**Output:**
- `out/index.html` — a single-page HTML using Tailwind via CDN
- `out/README.md` — a one-paragraph description of what was built
- `out/report.md` — pass/fail for each step, with console output

**Workflow (5 steps):**

```
              ┌─► [ui: implement index.html] ─┐
              │                                │
[idea] ─► [lead: brief] ─► [design: spec] ─► [qa: verify] ─► done
              │                                ▲
              └─► [sde: write README.md] ──────┘
```

| Step | Role | Inputs | Outputs | Failure → |
|---|---|---|---|---|
| 1. brief | lead | `idea` | `brief` text | abort |
| 2. spec | design | `brief` | `design_spec` text | abort |
| 3. implement_html | ui | `brief`, `design_spec` | `index.html` | retry once, then abort |
| 4. write_readme | sde | `brief` | `README.md` | retry once, then abort |
| 5. qa_verify | qa | `index.html` (path) | pass/fail report | retry once, then abort |

**Key property:** steps 3 and 4 are **independent** — they can run in
parallel. The MVP1 prototypes must show how each orchestrator handles
that.

---

## 3. Prototype A — lightchain

This is the shape we sketched in [LIGHTCHAIN.md Part 4](LIGHTCHAIN.md#part-4--the-lightchain-proposal).
Here's it applied to MVP1.

### 3.1 Step functions

```python
# prototypes/lightchain/mvp1.py  (sketch)

import asyncio
from pathlib import Path
from agent_ops.lightchain import Step, Run, parallel
from agent_ops.ollama import OllamaProvider      # new tiny wrapper, see § 3.4


async def step_brief(state: dict) -> dict:
    state["brief"] = await llm("lead",
        f"Write a one-paragraph brief for: {state['idea']}")
    return state


async def step_spec(state: dict) -> dict:
    state["design_spec"] = await llm("design",
        f"Given this brief, write a 5-bullet design spec:\n{state['brief']}")
    return state


async def step_implement_html(state: dict) -> dict:
    html = await llm("ui",
        f"Write a complete single-file index.html using Tailwind CDN. "
        f"Match this spec:\n{state['design_spec']}")
    Path("out").mkdir(exist_ok=True)
    Path("out/index.html").write_text(html)
    state["html_path"] = "out/index.html"
    return state


async def step_write_readme(state: dict) -> dict:
    readme = await llm("sde",
        f"Write a one-paragraph README for: {state['brief']}")
    Path("out/README.md").write_text(readme)
    return state


async def step_qa_verify(state: dict) -> dict:
    # For MVP1, QA = "file exists and is non-empty"
    p = Path(state["html_path"])
    state["qa_pass"] = p.exists() and p.stat().st_size > 100
    return state
```

### 3.2 Wiring with parallel

```python
pipeline = Run(steps=[
    Step("brief",       role="lead",   fn=step_brief,
         needs=["idea"],            produces=["brief"]),

    Step("spec",        role="design", fn=step_spec,
         needs=["brief"],           produces=["design_spec"]),

    # The interesting bit: parallel() is a tiny helper that runs the
    # enclosed steps concurrently and waits for all of them.
    parallel("build", steps=[
        Step("implement_html", role="ui",  fn=step_implement_html,
             needs=["brief", "design_spec"], produces=["html_path"]),
        Step("write_readme",   role="sde", fn=step_write_readme,
             needs=["brief"],               produces=["readme_path"]),
    ]),

    Step("qa_verify",   role="qa",    fn=step_qa_verify,
         needs=["html_path"],        produces=["qa_pass"]),
])
```

### 3.3 Run

```python
async def main():
    state = await pipeline.run({"idea": "a pomodoro timer web page"})
    print("done:", state.get("qa_pass"))
```

### 3.4 What we'd need to build

- `lightchain.py` itself (~150 lines, as proposed)
- `OllamaProvider` — a tiny new provider that POSTs to
  `http://localhost:11434/api/generate` (or `/api/chat` for chat-style).
  ~30 lines. Same `WorkerProvider` interface.
- The `parallel()` helper — ~20 lines, just `asyncio.gather` over the
  inner steps with shared state.

**Total new code:** ~200 lines.

---

## 4. Prototype B — langgraph

The same MVP1, written in langgraph. This is the **real learning material**:
by writing it, we feel what langgraph is good at and where it gets in
the way.

### 4.1 State

```python
# prototypes/langgraph/mvp1.py  (sketch)

from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict, total=False):
    idea: str
    brief: str
    design_spec: str
    html_path: str
    readme_path: str
    qa_pass: bool
```

### 4.2 Nodes (the same logic as § 3.1)

```python
async def node_brief(state: State) -> State:
    state["brief"] = await llm("lead", f"Write a brief for: {state['idea']}")
    return state

async def node_spec(state: State) -> State:
    state["design_spec"] = await llm("design", f"Spec for: {state['brief']}")
    return state

async def node_implement_html(state: State) -> State:
    html = await llm("ui", f"Write index.html for: {state['design_spec']}")
    Path("out/index.html").write_text(html)
    state["html_path"] = "out/index.html"
    return state

async def node_write_readme(state: State) -> State:
    readme = await llm("sde", f"Write a README for: {state['brief']}")
    Path("out/README.md").write_text(readme)
    return state

async def node_qa_verify(state: State) -> State:
    p = Path(state["html_path"])
    state["qa_pass"] = p.exists() and p.stat().st_size > 100
    return state
```

### 4.3 Graph

```python
graph = StateGraph(State)

graph.add_node("brief",         node_brief)
graph.add_node("spec",          node_spec)
graph.add_node("implement_html", node_implement_html)
graph.add_node("write_readme",   node_write_readme)
graph.add_node("qa_verify",      node_qa_verify)

graph.set_entry_point("brief")
graph.add_edge("brief", "spec")

# Fan-out: spec goes to BOTH implement_html and write_readme
graph.add_edge("spec", "implement_html")
graph.add_edge("spec", "write_readme")

# Fan-in: both converge on qa_verify
graph.add_edge("implement_html", "qa_verify")
graph.add_edge("write_readme",   "qa_verify")

graph.add_edge("qa_verify", END)

app = graph.compile()
```

### 4.4 Run

```python
async def main():
    result = await app.ainvoke({"idea": "a pomodoro timer web page"})
    print("done:", result.get("qa_pass"))
```

### 4.5 What we'd need to build / install

- `pip install langgraph langchain-ollama` (or just `langchain`).
- The same 5 node functions as § 3.1.
- The graph wiring in § 4.3.

**Total new code:** ~120 lines + ~50MB of dependencies.

---

## 5. Comparison matrix

| Dimension | lightchain (ours) | langgraph |
|---|---|---|
| Lines of new orchestration code | ~50 | ~25 (graph wiring) |
| New dependencies | 0 | langgraph + langchain-ollama (~50MB) |
| Parallel steps | `parallel("build", steps=[...])` | `add_edge(a, c)` × 2 (fan-out) |
| Conditional branching | `on_fail` field on `Step` | `add_conditional_edges()` |
| Checkpointing | `Run.checkpoint(path)` (~20 lines) | Built-in, configurable backend |
| Visualization | Walk `steps` list, emit Mermaid | `app.get_graph().draw_mermaid()` |
| Debug feel | "this is just Python" | "what's a RunnableConfig?" |
| Time to write prototype | ~3 hours | ~3 hours (incl. learning) |
| Time to debug a misbehaving step | Fast — single function | Slower — must trace through `Runnable` wrappers |
| Fits our gray-area vision | Perfect — direct calls | Awkward — `ChatOllama` wraps our LLM call |
| Vendor lock-in | None | Moderate |
| Production hardening | We write it | LangSmith, Studio, etc. |

---

## 6. The verdict (preliminary)

We **expect** to prefer lightchain, for the reasons in
[LIGHTCHAIN.md Part 3](LIGHTCHAIN.md#part-3--should-agentops-depend-on-langchainlanggraph)
and because Ollama is a plain HTTP call we'd be wrapping in
`ChatOllama` for no real benefit.

But we won't know for sure until both prototypes are written and run on
the same MVP1 input. The actual experience of writing langgraph
"Hello World" can be either smoother or rougher than the docs suggest.

**Recommendation:** write **both** prototypes. ~1 day total. Then keep
whichever we like.

---

## 7. Implementation plan

| Sub-task | Owner | Estimated time |
|---|---|---|
| Write `lightchain.py` (per [LIGHTCHAIN.md Part 4](LIGHTCHAIN.md#part-4--the-lightchain-proposal)) | TBD | 3-4 hours |
| Write `OllamaProvider` | TBD | 30 min |
| Write `prototypes/lightchain/mvp1.py` | TBD | 2 hours |
| Write `prototypes/langgraph/mvp1.py` | TBD | 2 hours |
| Side-by-side run on the same `idea` | TBD | 1 hour |
| Decision write-up: keep one, keep both, or pivot | TBD | 1 hour |

**Total: ~1 working day.**

---

## 8. Open questions

1. **Where do the prototypes live?** Options:
   - `prototypes/lightchain/` and `prototypes/langgraph/` as siblings to `src/`
   - `docs/prototypes/` so they live with the docs
   - Each as a standalone script in `examples/`
   I recommend `prototypes/` at the repo root.

2. **Should the prototypes share code?** E.g. the 5 step functions in
   § 3.1 and § 4.2 are nearly identical. Sharing them via
   `prototypes/_common.py` is honest but slightly biases the comparison
   (langgraph version gets a freebie from the lightchain version). I
   recommend **don't share** — copy-paste is fine for a 1-day prototype.

3. **What LLM to use exactly?** `ollama pull minimax-m3:cloud` is the
   user's stated preference. The MVP1 prototypes just need to call
   `POST http://localhost:11434/api/chat` with the role name as the
   model. We may need to add `minimax-m3:cloud` to the user's
   `~/.ollama/models`.

4. **How do we measure "better"?** Since both prototypes produce the
   same output, the comparison is qualitative:
   - Which is easier to extend (add a step)?
   - Which is easier to debug when a step hangs?
   - Which would we trust to run for 8 hours (the dream)?
   The write-up in step 7 should answer all three.
