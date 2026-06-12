# AgentOps — Roadmap & Open Challenges

> Living doc. Updated as we discuss. Not a sprint plan — a backlog of ideas,
> known gaps, and the "final season" vision.

---

## 🎯 The Final-Season Vision

**Premise:** if tokens were infinite, the user goes to sleep with a folder, wakes
up with shipped code.

### The 8-hour dream flow

1. User drops into a folder:
   - Design doc (requirements, business logic)
   - UI design mockups (HTML/Tailwind draft or images)
   - HTML "fake page" example (one working reference impl)
2. Ops wakes up, reads the folder, chats with Lead to confirm understanding
3. Lead breaks the work into tasks and assigns to the right roles
4. SDE builds the second HTML page (UI worker matches the design spec exactly)
5. QA runs check templates:
   - `test_coverage >= 95%`
   - `no TODO left`
   - `a11y_audit passes`
   - `design_compliance == 100%` (visual diff against the HTML example)
6. If a check fails AND the issue is out of QA's capability, QA escalates to Lead
   (a higher-tier model). Lead rewrites the spec / gives a hint, loop continues.
7. Next iteration: login flow → backend deploy → integration tests
8. ... loop for ~8 hours, then ship

**Why this is achievable (eventually):** the combo of
**(a)** your gray-area subscriptions, **(b)** a strong template/check system,
**(c)** escalation between tiers, and **(d)** long-running orchestration is
exactly the recipe for bumping swe-bench-style success rates above 50%.

**Reality check:** current SOTA autonomous agents sit at ~30-50% success on
multi-hour tasks. The biggest blockers are:
- Browser automation (CAPTCHAs, anti-bot on deploy platforms)
- Hidden state across services (DB migrations, tickets, side-effect ordering)
- Implicit specs ("make it look nicer" — AI doesn't know what's in your head)

We work around these by **narrowing the scope with templates**, not by trying
to be AGI.

---

## P0 — Quick wins, low risk, do first

### 0.1 Avengers team preset (default + fallback chains)

**Goal:** every role has a primary + fallback model chain, configurable,
disable-able. `agent-ops init --team avengers` writes a working config.

**Spec for the "avengers" team (v1):**

| Role  | Primary (default)            | Fallback 1         | Fallback 2 (if any) |
|-------|------------------------------|--------------------|---------------------|
| Lead  | `claude-tui` (gray, best)    | `ollama:minimax-m3`| —                   |
| UI    | `claude-tui` (Fable 5, gray) | other UI-strong   | —                   |
| SDE   | `minimax-tui`                | `qwen3.6`          | —                   |
| QA    | `qwen3`                      | `glm5.1`           | —                   |
| Helper| configurable                 | configurable       | configurable        |

**Behavior:**
- Each role: ordered list of providers
- Try primary → on failure/error, try next
- A role can be `enabled: false` (fired) or `enabled: true` (hired)
- After init, the user can edit `agent-ops.yaml` to add/remove fallbacks
- The team preset itself is shipped **as Python code** (`agent_ops/teams/avengers.py`),
  with YAML as the override layer — see [§ 0.5 design decision](#05-preset-format-python-vs-yaml)

**Open questions:**
- Where does the fallback decision live? In the provider, in the dispatch loop, or in a new `FallbackChain` class? → **DecisionAI recommends a `FallbackChain` wrapper** at the OpsAgent level (see commit faf15da's "use feedback" notes).
- Should "disabled" workers still be health-checked? Probably not — skip them.

### 0.2 Add `QA` to the role enum

- Add `QA = "qa"` to `WorkerRole` in `types.py`
- Update the brief-task regex in `core.py` to allow `@qa`
- Add QA examples to the `avengers` preset

### 0.3 Fix the 8 known issues from the code review

These were all in commit history already, but listing here for reference:

- [x] Re-queue rejected tasks back to `TODO` (was: stuck in `IN_REVIEW`)
- [x] `ClaudeTUIProvider` now passes `context["system"]` (was: silently dropped)
- [x] `OpsAgent.status()` added (CLI `status` command crashed before)
- [x] `OpsAgent.health_check()` added (CLI `health` command crashed before)
- [x] `WorkerProvider` properly imported in `core.py` (was: `# type: ignore`)
- [x] Inline `import re` moved to top-level in `core.py`
- [x] Unused `import re` removed from `providers.py`
- [x] Dead `default_config` string still present in `config.py` — **TODO: delete or wire up**

---

## P1 — "Drop a folder, run" core capability

### 1.1 Inbox / Context Loader

**Goal:** at the start of a run, scan a folder, extract the relevant context,
build the brief automatically.

**Inputs the loader must understand:**
- Markdown / text: design docs, business specs
- HTML files: working reference pages, design drafts
- Images: UI mockups (PNG/JPG) — need to be base64'd or OCR'd depending on model
- Code files: existing source code (to extend, not rewrite)

**API surface (proposed):**

```python
from agent_ops.inbox import Inbox

inbox = Inbox("./project-folder")
context = inbox.load()          # returns a structured Context object
brief = inbox.to_brief()        # generates the initial Lead brief
```

**Key design questions:**
- File-type detection: use `magika` or simple extension matching?
- Size limits: skip files > N MB, log a warning?
- Privacy: if a file contains secrets, warn the user before sending to a model?
- HTML handling: extract text + structure, or send raw and let the model parse?

### 1.2 Conversation loop (Lead ↔ others)

**Goal:** Lead can ask clarifying questions back. Not just `prompt → answer`.

**Current:** `dispatch(role, prompt, context)` is one-shot.

**Proposed:** introduce a `Conversation` object that tracks a thread of
`[user_msg, assistant_msg, ...]` and supports `continue_until(condition)`.

**Use cases:**
- Lead reads the inbox, has 3 questions → asks the user before breaking tasks
- QA can't pass a check, escalates to Lead → Lead re-explains the spec to the implementer
- User wants to mid-run add a constraint ("use Postgres, not SQLite") → injected into all future context

**Open question:** **Do we use langchain / langgraph?**
- **Current answer: no.** The whole value prop is the gray-area subscription stack.
  Langchain adds a heavy abstraction layer that obscures what HTTP call actually
  happens — bad for a tool that depends on undocumented internal endpoints.
- We can borrow langchain's *patterns* (fallback chains, output parsers, retry)
  without depending on the library. If we ever want to swap in langgraph for the
  conversation loop, we can do that behind a feature flag.

### 1.3 Escalation between tiers

**Goal:** when a lower-tier model is stuck or fails, automatically try a higher-tier one.

**Triggers:**
- Provider exception (network, auth, 5xx)
- Output doesn't parse (malformed task list, bad review verdict)
- QA check fails 2+ times in a row
- Model self-reports low confidence (if it can)

**Flow:**

```
Try primary provider
  ↓ (fail)
Try fallback 1
  ↓ (fail)
Try fallback 2
  ↓ (fail)
Mark task as ESCALATED, ask Lead (highest-tier) for help
```

**Important:** escalation is **not** a retry. It's a qualitative change — the
higher model may rewrite the approach, not just retry the same call.

### 1.4 Task result persistence

**Goal:** `Task.result` is currently set in-memory only. Persist it so the user
can audit what each worker said.

**Proposal:** extend `Board._save` to include a `## results` section in the
markdown, or write a separate `results.md` per task.

---

## P2 — "Sleep 8 hours" engineering

### 2.1 Time-budget runner

**Goal:** instead of `max_iterations=10`, run for a time budget (e.g. 8h).

```python
ops.run(idea, time_budget=timedelta(hours=8))
```

**Behaviors:**
- Persist a checkpoint after every task completion
- On timeout: save state, print summary, exit cleanly
- On resume: pick up from the last checkpoint

### 2.2 Checkpoint + resume

**Goal:** killable, resumable runs. The 8-hour dream dies if one OOM kills 7h of work.

**Storage:** a `.agent-ops/state.json` per run, with task statuses + results.

**CLI:**
```bash
agent-ops run "..." --checkpoint .agent-ops/run-001
agent-ops resume .agent-ops/run-001
agent-ops status  .agent-ops/run-001
```

### 2.3 QA templates

**Goal:** user-defined check scripts the QA worker runs.

**Template format (proposed):**

```yaml
# qa-templates/coverage.yaml
name: test_coverage
check: pytest --cov=src --cov-fail-under=95
on_fail: escalate_to: lead
```

```yaml
# qa-templates/no-todo.yaml
name: no_todo
check: "! grep -rn 'TODO' src/"
on_fail: ask_sde_to_fix
```

```yaml
# qa-templates/design-compliance.yaml
name: design_compliance
check: visual_diff(reference_html, built_html)
on_fail: escalate_to: ui
```

**Built-in templates to ship:**
- `test_coverage` (pytest-based)
- `no_todo` / `no_fixme` (grep)
- `a11y_basic` (axe-core via headless browser)
- `design_compliance` (pixel diff against reference HTML)
- `lint_clean` (ruff/mypy clean)
- `type_strict` (mypy --strict)

### 2.4 Progress & observability

**Goal:** during an 8-hour run, the user wants a live view.

- Local web UI (`agent-ops ui`) showing board, current task, token usage
- TUI dashboard (`agent-ops watch`) with live updates
- Optional: push to a webhook (Slack, Discord) on milestones

---

## P3 — Long term

### 3.1 Deploy runner

- `agent-ops deploy --target vercel|fly|aws`
- Handles secrets via env, runs migrations, posts health check
- **Big risk:** deploy platforms have anti-bot measures. May need a human-in-the-loop step.

### 3.2 Integration test orchestrator

- Spawns a real backend, real DB, runs e2e tests against the built UI
- Tears down on completion
- Captures screenshots for visual regression

### 3.3 Voice → prompt optimizer (backlogged from original TODO.md)

- iOS Shortcut: dictate → STT → optimize → send to agent
- See [TODO.md](../TODO.md) in repo root for the original spec

### 3.4 Multi-user / shared runs

- Several users collaborate on the same `agent-ops` run
- Each user can steer a different role
- Conflicts resolved via board priority

---

## 📐 Design decisions log

### 0.5 Preset format: Python vs YAML

**Decision (tentative):** teams are **Python code** (`agent_ops/teams/avengers.py`),
YAML is the **override** layer.

- `ops.load_team("avengers")` — zero-config, ships with the package
- `agent-ops init --team avengers` — writes a local `agent-ops.yaml` the user can edit
- `ops.load_team(config="./my-team.yaml")` — load a fully custom team

**Rationale:**
- Preset is the source of truth, versioned with the package — no drift
- Python API is testable, type-checkable, composable
- YAML is for the user who wants to deviate

This came from DecisionAI suggestion — awaiting user confirmation.

---

## 🐛 Open code-quality issues (from review)

Things noticed but not yet addressed:

- **Sequential execution:** `run()` picks `pending[0]` one at a time. With
  fast providers like Copilot, independent tasks should run in parallel via
  `asyncio.gather()`.
- **`_org_id = ""` produces `/api/organizations//conversations`** in
  `ClaudeTUIProvider`. Will 404 unless `CLAUDE_ORG_ID` is set. Should warn
  at startup if it's empty.
- **No file persistence of `Task.result`.** Board is the only persistent
  state, and it doesn't capture worker output.
- **`Board._load` overwrites newer state** silently if in-memory and file
  disagree.
- **No CLI smoke test for `agent-ops run`.** A stub Lead would let users
  actually try the CLI end-to-end.
- **`config.py` `default_config` is dead code.** Should be deleted or wired
  into `agent-ops init` (which doesn't exist yet — see § 0.1).
- **Two paths can collide on `"design"` key:** `code_design_provider` is
  registered under both the phase-2 design spec generation and any future
  `@design`-tagged build task. Need to disambiguate.
- **No provider tests, no end-to-end test.** Only board CRUD + a trivial
  import check. Won't catch regressions in the orchestration loop.
