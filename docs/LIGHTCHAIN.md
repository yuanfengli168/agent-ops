# Lightchain — A Tiny DAG Layer for AgentOps

> **Status:** proposal + learning doc. Not implemented yet.
>
> **Audience:** Jacky (and anyone else learning about langchain/langgraph
> while thinking about how to evolve AgentOps). Reading this top-to-bottom
> should give you:
> 1. A solid mental model of langchain and langgraph (what they are, when
>    to use them, when not to)
> 2. A clear "why we should/shouldn't depend on them" decision for AgentOps
> 3. A concrete proposal for a tiny home-grown alternative ("lightchain")
>    that we can ship inside AgentOps in ~200 lines

---

## Part 1 — The big picture

### What langchain *is*

LangChain started in late 2022 as a way to glue LLMs to other things
(docs, APIs, tools). Over two years it grew into a large ecosystem with
several distinct sub-projects:

| Sub-project | What it does | When you reach for it |
|---|---|---|
| `langchain-core` | Base abstractions: `Runnable`, `PromptTemplate`, `OutputParser` | Always (it's the core) |
| `langchain` (the meta-package) | Pre-built integrations: `ChatOpenAI`, `ChatAnthropic`, retrievers, agents | You want a quick start with the major vendors |
| `langchain-community` | Third-party integrations (hundreds of them) | You use a niche vector DB or model |
| `langgraph` | Stateful, graph-based orchestration with cycles and human-in-the-loop | You need branching, retries, persistent state across steps |
| `langserve` | Deploy a chain as a REST API | You want to expose a chain to other services |
| `LangSmith` (commercial) | Tracing, evaluation, monitoring | You need observability for production chains |

For AgentOps, the relevant pieces are `langchain-core` (the abstractions)
and `langgraph` (the orchestration model). The rest we don't need.

### What langgraph is (and why it matters)

Langgraph is the *interesting* part. Where classical langchain "chains"
are linear (`prompt → llm → parser → next prompt → ...`), langgraph
lets you model the workflow as a **directed graph with cycles and
branches**:

```
        ┌─► [qa_check] ──fail──► [escalate_to_lead] ──┐
        │                                              │
[brief] ─┼─► [implement] ──────────────────────────────┤
        │                                              │
        └─► [design] ──────────────────────────────────┘
                              ▲                        │
                              └──────── retry ─────────┘
```

Nodes are functions. Edges are conditional. State is a typed dict that
flows through the graph. The graph *itself* is a Python object you can
inspect, visualize, and checkpoint.

Langgraph is what you reach for when your workflow has:
- **Cycles** (retry, escalate, iterate)
- **Conditional branching** (different paths based on intermediate results)
- **Human-in-the-loop** (pause for user input)
- **Persistent state across long-running workflows**

This sounds *exactly* like the 8-hour AgentOps dream in
[TODO.md](../docs/TODO.md). That's why we're studying it.

---

## Part 2 — Langchain mental model, slowly

If you've never used langchain, the fastest way to build intuition is to
see the same workflow written three ways: **plain Python**, **langchain
chain**, **langgraph graph**.

### Example: "summarize a doc, then translate to French"

#### Way 1 — plain Python (what we'd write today)

```python
import httpx

def summarize(text: str) -> str:
    resp = httpx.post("https://api.minimax.chat/v1/text/chatcompletion_v2",
                      headers={"authorization": f"Bearer {token}"},
                      json={"model": "MiniMax-M1",
                            "messages": [{"role": "user",
                                          "content": f"Summarize: {text}"}]})
    return resp.json()["choices"][0]["message"]["content"]

def to_french(text: str) -> str:
    resp = httpx.post(..., json={"messages": [{"role": "user",
                                               "content": f"Translate to French: {text}"}]})
    return resp.json()["choices"][0]["message"]["content"]

result = to_french(summarize(doc))
```

**Pros:** total control, easy to debug, no magic.
**Cons:** every step repeats boilerplate, no retry, no tracing, hard to
swap providers, hard to compose into bigger workflows.

#### Way 2 — langchain chain (the "LCEL" way)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

summarize_prompt = ChatPromptTemplate.from_messages([
    ("user", "Summarize: {text}")
])
translate_prompt = ChatPromptTemplate.from_messages([
    ("user", "Translate to French: {summary}")
])

# Each "step" is `prompt | llm`
summarize_step = summarize_prompt | llm
translate_step = translate_prompt | llm

# Compose: pass the output of summarize as {summary} to translate
chain = (
    {"summary": summarize_step}
    | translate_step
)

result = chain.invoke({"text": doc})
```

**Pros:** composable (`|` is the chain operator), swappable (change
`ChatOpenAI` to `ChatAnthropic` in one line), auto-parses LLM output.
**Cons:** still linear. No cycles. No state. The "magic" hides what HTTP
call actually happens.

#### Way 3 — langgraph (the "real workflow" way)

```python
from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    text: str
    summary: str
    french: str

def summarize_node(state: State) -> State:
    state["summary"] = llm.invoke(f"Summarize: {state['text']}").content
    return state

def translate_node(state: State) -> State:
    state["french"] = llm.invoke(f"Translate to French: {state['summary']}").content
    return state

graph = StateGraph(State)
graph.add_node("summarize", summarize_node)
graph.add_node("translate", translate_node)
graph.add_edge("summarize", "translate")
graph.add_edge("translate", END)
graph.set_entry_point("summarize")

app = graph.compile()
result = app.invoke({"text": doc})
```

**Pros:** stateful, inspectable, can checkpoint, can add cycles, can
branch on intermediate values.
**Cons:** heavier than way 2. Worth it for non-trivial workflows.

### When to use which

| If your workflow is... | Use |
|---|---|
| 1-2 LLM calls, no branching | Plain Python |
| Linear pipeline, 3+ steps, may want to swap models | langchain `prompt \| llm` |
| Has cycles / retries / conditional branches / human-in-loop | langgraph |
| Long-running, needs checkpointing + resume | langgraph (with a checkpointer) |
| Needs strict observability / eval | LangSmith (commercial) on top |

---

## Part 3 — Should AgentOps depend on langchain/langgraph?

### The case FOR using langgraph

1. **It already solves problems we have.** The AgentOps build loop
   (implement → review → re-queue → re-implement) is a *graph with a
   cycle*. The QA escalation (in P2) is a *conditional branch*. The
   8-hour dream needs *checkpointing*. Langgraph does all of this.
2. **Community & docs.** If a user knows langgraph, they can extend
   AgentOps without learning our home-grown DSL.
3. **Mature.** Langgraph is used in production at many companies.

### The case AGAINST

1. **Heavy dependency.** Langgraph pulls in langchain-core, pydantic,
   a few other things. Hundreds of MB installed. Slow import time.
2. **The gray-area problem.** Langgraph's "ChatModel" abstraction tries
   to be provider-agnostic. That's great for OpenAI vs Anthropic, but
   our providers talk to *undocumented internal endpoints*. Wrapping
   those in `ChatModel` means fighting the abstraction. You'd end up
   writing custom `ChatModel` subclasses for every provider, which
   defeats the point.
3. **Control loss.** When Claude.ai changes its internal API shape, we
   need to be able to debug the HTTP call line-by-line. With langgraph
   in the middle, the call is buried under three layers of callbacks.
4. **Prompt reformatting.** Langchain's `ChatPromptTemplate` will try to
   reformat your prompt into a "standard" structure. Our prompts are
   hand-tuned for specific endpoints (e.g. claude.ai's internal format
   is different from Anthropic's public API). Reformatting them
   silently can break things.

### Decision

**We will NOT take a hard dependency on langchain/langgraph.**

But we will borrow three ideas from them, and ship them as a small
internal module called `lightchain` (see [Part 4](#part-4--the-lightchain-proposal)).

The escape hatch stays open: if a future use case really needs langgraph
(for example, someone wants to embed AgentOps inside a larger
langgraph workflow), we can add it as an *optional* dep with a thin
adapter.

---

## Part 4 — The Lightchain Proposal

### Goals

1. Capture the **three langgraph ideas we want**: typed state, conditional
   branching, cycles/retries.
2. Stay under **~200 lines of code** with **zero new dependencies**.
3. Make the AgentOps `OpsAgent.run()` loop **declarative** instead of
   imperative.
4. Keep the gray-area advantage: every step is just a Python function
   that calls our existing `WorkerProvider` directly.

### Non-goals

- Not a general-purpose LLM framework.
- Not a competitor to langchain. We don't care about users who don't
  already use AgentOps.
- Not a replacement for production-grade observability. Use LangSmith
  for that.

### Shape of the API

```python
# src/agent_ops/lightchain.py  (proposed, ~150 lines)

from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class Step:
    name: str
    role: str                       # "lead" | "sde" | "ui" | "qa" | ...
    fn: Callable[[dict], "Step"]    # the actual work
    needs: list[str] = field(default_factory=list)   # input keys this step requires
    produces: list[str] = field(default_factory=list)  # output keys this step adds to state
    retries: int = 1
    on_fail: str | None = None      # step name to escalate to

@dataclass
class Run:
    steps: list[Step]

    def run(self, initial: dict) -> dict:
        state = dict(initial)
        for step in self.steps:
            try:
                state = step.fn(state)
            except Exception as e:
                if step.on_fail and state.get("__attempt", 0) < step.retries:
                    state["__attempt"] = state.get("__attempt", 0) + 1
                    continue  # try on_fail step
                raise
        return state
```

### Example: rewriting the AgentOps build loop in lightchain

Today, the build loop in `core.py` is imperative:

```python
for iteration in range(max_iterations):
    pending = self.board.get_by_status(TaskStatus.TODO)
    if not pending:
        break
    task = pending[0]
    self.board.move(task.id, TaskStatus.IN_PROGRESS)
    result = await self.dispatch(task.assignee.value, ...)
    if task.assignee != WorkerRole.REVIEW:
        review = await self.dispatch("review", ...)
        if "approve" in review.lower():
            self.board.move(task.id, TaskStatus.DONE)
        else:
            self.board.move(task.id, TaskStatus.TODO)  # re-queue
```

With lightchain, the same flow becomes **data**:

```python
from agent_ops.lightchain import Step, Run

build_pipeline = Run(steps=[
    Step(
        name="pick_next_task",
        role="ops",
        fn=pick_next_task_step,    # pulls first TODO, puts it in state["task"]
        produces=["task"],
    ),
    Step(
        name="implement",
        role=None,                  # role is read from state["task"].assignee
        fn=implement_step,          # dispatches to task.assignee
        needs=["task", "brief", "design_spec"],
        produces=["result"],
    ),
    Step(
        name="review",
        role="review",
        fn=review_step,
        needs=["task", "result", "brief", "design_spec"],
        produces=["verdict"],
    ),
    Step(
        name="accept_or_requeue",
        role="ops",
        fn=accept_or_requeue_step,  # moves task to DONE or TODO based on verdict
        needs=["task", "verdict"],
    ),
])

state = {"board": board, "brief": brief, "design_spec": design_spec}
for _ in range(max_iterations):
    if not state["board"].get_by_status(TaskStatus.TODO):
        break
    state = await build_pipeline.run(state)
```

### What we gain

1. **The loop is data, not code.** To change the workflow, edit the
   `Run(steps=[...])` list, not the `for` loop in `core.py`.
2. **Visualization.** We can render the pipeline as a graph (text or
   Mermaid) just by walking the `steps` list. Future `agent-ops graph`
   CLI command becomes trivial.
3. **Composability.** A `Run` is just a list. You can put one `Run`
   inside another, or share a `Step` between two pipelines.
4. **Testability.** Each step is a pure function `state → state`. Easy
   to unit test by feeding in synthetic state and asserting the output.

### What we don't gain (deliberately)

- Langgraph's full stateful-checkpointing story. We can add a simple
  `Run.checkpoint()` method that dumps `state` to JSON, but it's not
  the same as langgraph's thread/queue model.
- LangSmith observability. If you need that, install langsmith
  alongside and instrument the step functions yourself.

---

## Part 5 — Implementation plan

### Milestone 1: prototype (~150 lines, ~1 day)

- Create `src/agent_ops/lightchain.py` with the shapes above.
- Rewrite `OpsAgent.run()` to use it for the build loop.
- All existing tests pass; no behavior change.

### Milestone 2: visualization

- Add `agent-ops graph` CLI command that prints the pipeline as
  Mermaid syntax (renderable in GitHub, VS Code, anywhere).
- Useful for users to see what their team does.

### Milestone 3: P2 features plug in naturally

- **Time-budget runner:** wrap `Run.run()` in a deadline check.
- **Checkpoint + resume:** dump `state` to a file, load it on resume.
- **Escalation chains:** the `on_fail` field in `Step` already does
  this; just give it more structure (priority list of fallbacks).

### Milestone 4 (optional): langgraph adapter

- If a real user needs to embed AgentOps inside a langgraph workflow,
  add an `agent_ops.lightchain.langgraph_adapter` module that exposes
  each `Step` as a langgraph `Node`. Opt-in via
  `pip install agent-ops[langgraph]`.

---

## Part 6 — Reading list (deep dives)

If you want to actually learn langchain and langgraph, here's the path
I recommend:

1. **LangChain quickstart** (30 min)
   https://python.langchain.com/docs/introduction/
   - Skim the "Architecture" page. Don't try to read everything.

2. **LCEL (LangChain Expression Language)** (1 hour)
   https://python.langchain.com/docs/concepts/lcel/
   - This is the `prompt | llm | parser` syntax. Worth understanding well.

3. **LangGraph quickstart** (2-3 hours)
   https://langchain-ai.github.io/langgraph/
   - Build the "chatbot with tools" tutorial end to end. That's the
     canonical example.

4. **LangGraph concepts: state, nodes, edges, conditional edges**
   (1 hour)
   https://langchain-ai.github.io/langgraph/concepts/
   - The "low-level" concepts. This is what we're mimicking.

5. **Anthropic's "Building effective agents" essay** (30 min)
   https://www.anthropic.com/research/building-effective-agents
   - Not langchain-specific, but the best mental model of "what is an
     agent, anyway" that exists.

Total time: ~6 hours of focused reading. After that you'll understand
both the design space and exactly why we're not depending on it.

---

## Part 7 — FAQ

**Q: If we don't use langchain, are we "behind"?**
A: No. Langchain is one design choice among many. Many production
agents (Devin, Factory, Codegen, MetaGPT) use custom orchestration.
Langchain is a *tool*, not a *standard*.

**Q: Is lightchain just a worse langgraph?**
A: For the 90% case (linear pipeline with a few cycles), it's a *better*
langgraph because there's no magic to fight. For the 10% case (complex
stateful workflows with parallel branches), it's a worse langgraph and
that's when you'd reach for the optional adapter.

**Q: Will lightchain work with my gray-area providers?**
A: Yes — that's the whole point. Lightchain doesn't care which
provider you use. The step functions just call
`await ops.dispatch("lead", prompt)`, same as today.

**Q: Can I prototype lightchain in a Jupyter notebook?**
A: Yes. It's plain Python. The prototype in [Part 4](#part-4--the-lightchain-proposal)
is the full thing.

---

## Part 8 — Open questions for the user (Jacky)

1. **Naming.** "lightchain" is fine but a bit cute. Alternatives:
   `pipedag`, `agentflow`, `rolegraph`, or just `pipeline`. What do you
   prefer?

2. **Scope for milestone 1.** Should the prototype replace the
   *current* `OpsAgent.run()` loop, or live alongside it as an opt-in
   `OpsAgent.run_v2()`? The former is more disruptive but proves the
   approach.

3. **Visualization format.** Mermaid is the obvious choice (works
   everywhere). But should we also output Graphviz `.dot` for prettier
   diagrams?

4. **Test approach.** Each `Step` as a pure function is easy to test.
   Do we want a `lightchain.testing` helper module with utilities like
   `assert_step_produces(step, input_state, key, expected)`?

Once these are answered, milestone 1 is ~1 day of work.
