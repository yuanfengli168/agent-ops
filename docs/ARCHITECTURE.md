# AgentOps Architecture (User-Facing)

> **Audience:** anyone reading the repo who wants to understand *how* AgentOps
> works and *why* it's shaped the way it is. No code-level detail here — see
> [DESIGN.md](DESIGN.md) for the developer view.

---

## 1. What AgentOps is

AgentOps is a **multi-agent orchestrator for shipping code from an idea**. You
give it an idea (or drop a folder of design docs and HTML mockups), and a
small team of AI workers — each playing a specific role — collaboratively
turns it into a working project.

The key differentiator: **AgentOps hooks into AI subscriptions you already
pay for** (Claude Pro, MiniMax 海螺AI, GitHub Copilot, OpenClaw). No
per-call API fees, no separate billing.

---

## 2. The team

AgentOps ships with role abstractions, not bundled workers. You compose a
team by registering workers under roles:

| Role     | What it does                                                 |
|----------|--------------------------------------------------------------|
| `lead`   | Reads the idea / folder, writes a project brief, breaks it into tasks |
| `design` | Produces UI/UX specs and HTML/Tailwind design drafts          |
| `ui`     | Implements the frontend, matching the design spec             |
| `sde`    | Implements the backend, APIs, infrastructure                  |
| `qa`     | Reviews work, runs checks, reports pass/fail (placeholder)    |
| `review` | Final code + design-compliance check                         |
| `helper` | Custom role — anything you wire up                            |

Each role can be filled by any of the [supported providers](#4-providers).
A role can also be **disabled** (the "fire" action) or **swapped** (the
"hire" action) without changing the orchestrator.

---

## 3. The flow

A full `agent-ops run` proceeds in 5 phases:

```
   ┌─────────────┐
   │  You (idea) │
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 1. Brief     │  ← Lead reads the idea (or a folder) and writes a brief
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 2. Design    │  ← Design produces HTML/Tailwind mockups (optional)
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 3. Tasks     │  ← Lead's brief is parsed into a markdown board
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 4. Build     │  ← Loop: pick TODO → assign to role → implement
   │    ↺         │
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 5. Review    │  ← Reviewer checks code + design compliance
   │              │     PASS → DONE; FAIL → back to TODO with feedback
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ 6. Shipped   │
   └──────────────┘
```

The board is the **single source of truth** for task state. It's a plain
markdown file you can read, edit by hand, or version-control.

---

## 4. Providers

A provider is the **plumbing** that turns "ask the model X" into an actual
HTTP call. AgentOps currently ships:

| Provider          | Uses                                            | Setup                                    |
|-------------------|-------------------------------------------------|------------------------------------------|
| `copilot`         | Your GitHub Copilot subscription                | `gh auth login` (or `GH_TOKEN` env var)  |
| `claude-tui`      | Your claude.ai subscription                     | Extract `sessionKey` cookie              |
| `minimax-tui`     | Your 海螺AI subscription                        | Extract `authorization` header           |
| `openclaw`        | Your local OpenClaw gateway (port 3100)         | Just run OpenClaw                        |
| `qa`              | Any LLM, prompted to act as a QA reviewer       | Configure the underlying LLM             |
| `design`          | MiniMax, prompted to output HTML/Tailwind       | MiniMax token                            |
| `browser`         | Any TUI app, via Playwright                     | `pip install playwright && playwright install` |

New providers can be added by subclassing `WorkerProvider` in
[src/agent_ops/providers.py](../src/agent_ops/providers.py).

---

## 5. Configuration

A `agent-ops.yaml` file wires roles to providers:

```yaml
workers:
  lead:
    provider: copilot
    model: gpt-4o

  sde:
    provider: copilot
    model: gpt-4o-mini

  review:
    provider: copilot
    model: gpt-4o-mini

project:
  board: ./board.md
  repo: ./project
  max_iterations: 10
```

Three things are tunable per worker:

- `provider` — which plumbing to use
- `model` — which model that provider should call
- `enabled: false` — fire this role (orchestrator skips it)

See [agent-ops.yaml](../agent-ops.yaml) for the full annotated example.

---

## 6. Why this shape

**Why teams, not single agents?** A single mega-prompt asking one model to
"design, code, test" produces mediocre work on all three. Splitting roles
keeps each prompt focused and lets you mix model strengths (Claude for
reasoning, MiniMax for visuals, Copilot for cheap iteration).

**Why markdown as the board?** It's version-controllable, diffable,
human-readable, and editable. You can `git diff board.md` after a run and
see exactly what changed.

**Why orchestrator code, not langchain?** Langchain is great for
single-team setups. AgentOps depends on **gray-area subscription
endpoints** that change without notice, so the orchestrator needs to stay
small enough to debug line-by-line. We borrow langchain's *patterns*
(fallback chains, output parsers) but not its library — see
[LIGHTCHAIN.md](LIGHTCHAIN.md) for the proposed internal DSL that captures
these patterns.

**Why no deploy step yet?** Deploy platforms have anti-bot measures. The
8-hour "drop a folder, wake to shipped code" dream needs a human-in-the-loop
step for the deploy handoff. Tracked in [TODO.md § 3.1](TODO.md#31-deploy-runner).

---

## 7. Where to go next

- [DESIGN.md](DESIGN.md) — the developer's view: module layout, data flow, extension points
- [TODO.md](TODO.md) — what's done, what's planned, the "8-hour dream" vision
- [LIGHTCHAIN.md](LIGHTCHAIN.md) — proposed DSL for declarative pipelines, with a learning walkthrough of langchain/langgraph
