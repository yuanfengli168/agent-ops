# AgentOps Internal Design (Developer View)

> **Audience:** contributors and maintainers. This is the "how it actually
> works" doc. For the user-facing "what is this and how do I use it", see
> [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Module layout

```
src/agent_ops/
├── __init__.py        # Re-exports OpsAgent
├── types.py           # WorkerRole, TaskStatus, Task, WorkerConfig, WorkerProvider ABC
├── providers.py       # All worker providers (Claude, MiniMax, OpenClaw, Copilot, Browser)
│                      #   + PROVIDERS registry + get_provider()
├── design.py          # CodeDesignProvider, MidjourneyProvider
├── qa.py              # QAProvider (placeholder)
├── board.py           # Board (markdown-backed task store)
├── core.py            # OpsAgent (the orchestrator)
├── cli.py             # argparse CLI: run | dispatch | status | health
└── config.py          # (currently dead — see § 7)
```

The dependency graph is strictly one-way:

```
            cli.py
               │
               ▼
            core.py  ────▶  providers.py  ────▶  design.py
               │            │                      │
               │            └─────────────  ▶  qa.py
               │
               ▼
            board.py
               │
               ▼
            types.py  ◀──── all modules use this
```

`types.py` is the leaf — everyone imports it, it imports nothing internal.
`cli.py` is the only consumer of `core.py` (besides user code via `__init__.py`).

---

## 2. Data model

### 2.1 `Task` ([types.py](../src/agent_ops/types.py))

```python
@dataclass
class Task:
    id: str               # "T001", "T002", ...
    title: str
    assignee: WorkerRole
    status: TaskStatus    # TODO | IN_PROGRESS | IN_REVIEW | IN_QA | DONE | KILLED
    description: str = ""
    result: str = ""      # worker's output (in-memory only — see § 6)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any]
```

### 2.2 `WorkerConfig` and `WorkerProvider`

```python
@dataclass
class WorkerConfig:
    role: WorkerRole
    provider: str         # key in PROVIDERS registry
    model: str = ""
    api_key_env: str = "" # env var name to read the token from
    base_url: str = ""    # optional endpoint override
    enabled: bool = True
    extra: dict[str, Any] # free-form, read by some providers (e.g. browser selectors)


class WorkerProvider(ABC):
    @abstractmethod
    async def execute(self, prompt: str, context: dict | None = None) -> str: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
```

The `context` dict is currently used to pass a `system` message; the
orchestrator assembles it (brief + design spec for UI/SDE tasks).

### 2.3 `WorkerRole` and `TaskStatus`

Both are `str, Enum` so they round-trip through YAML and markdown cleanly.

| `WorkerRole` | Purpose |
|---|---|
| LEAD, DESIGN, UI, SDE, QA, REVIEW, HELPER | Built-in roles |

| `TaskStatus` | Meaning |
|---|---|
| TODO, IN_PROGRESS, IN_REVIEW, IN_QA | Active states |
| DONE, KILLED | Terminal states |

`IN_QA` was added recently (commit `aa39c5e`) to distinguish "implementer
finished, QA checking" from "implementer finished, reviewer checking".
The pipeline currently moves `IN_PROGRESS → IN_REVIEW → DONE|TODO`. The
`IN_QA` state is reserved for when the § P2 QA loop in
[TODO.md § 2.3](TODO.md#23-qa-templates) lands.

---

## 3. The orchestrator loop

`OpsAgent.run(idea, max_iterations=10)` ([core.py:104-179](../src/agent_ops/core.py#L104-L179)):

```
Phase 1: Brief
  └─ dispatch("lead", brief_prompt) → brief text

Phase 2: Design (optional, only if "design" worker registered)
  └─ dispatch("design", design_prompt) → design spec text

Phase 3: Task Setup
  └─ regex parse brief for "T###: title @role" lines
  └─ Board.add() each

Phase 4: Build loop (up to max_iterations)
  └─ take first TODO task
  └─ Board.move(task, IN_PROGRESS)
  └─ dispatch(task.assignee, ..., context={system: brief + design_spec?})
  └─ if assignee != REVIEW:
       Board.move(task, IN_REVIEW)
       dispatch("review", ..., context=brief + design_spec)
       if review verdict contains "approve|looks good|lgtm|✓":
         Board.move(task, DONE)
       else:
         Board.move(task, TODO)   # re-queue
     else:
       Board.move(task, DONE)     # reviewer's own tasks skip review

Phase 5: Summary
```

**Key behaviors:**
- Tasks are taken in **insertion order** (`pending[0]`), not priority-sorted.
- Review is **skipped for reviewer's own tasks** (avoids infinite review-of-review loop).
- Rejected tasks are **re-queued**, not killed.
- `max_iterations` is a *loop iteration* cap, not a per-task cap. One iteration
  processes one task. So 10 tasks + no rejections ≈ 10 iterations.

---

## 4. The provider abstraction

Every provider implements two methods:

```python
async def execute(self, prompt, context=None) -> str
async def health_check(self) -> bool
```

The orchestrator only knows about these two. Everything else (HTTP, auth,
JSON parsing) is the provider's concern.

The `PROVIDERS` registry ([providers.py:478-501](../src/agent_ops/providers.py#L478-L501))
maps string names to classes. Adding a new provider:

1. Subclass `WorkerProvider`.
2. Implement `execute` and `health_check`.
3. Add the class to `PROVIDERS` under one or more keys.
4. (Optional) Add a config block to `agent-ops.yaml`.

That's it. No orchestrator changes needed.

---

## 5. The board

`Board` ([board.py](../src/agent_ops/board.py)) is a thin wrapper over a
markdown file. Five sections (one per `TaskStatus`), tasks as `- [ ] T###: title @role`
lines.

```python
board = Board(Path("board.md"))
board.add(title="Build API", assignee=WorkerRole.SDE)  # → T001
board.move("T001", TaskStatus.IN_PROGRESS)
board.get_by_status(TaskStatus.TODO)
board.get_by_assignee(WorkerRole.SDE)
```

Persistence: every mutation rewrites the markdown file. `_load` is called
on init if the file exists.

**Limitations** (see [TODO.md § 🐛](TODO.md#-open-code-quality-issues-from-review)):
- `Task.result` is not persisted.
- `_load` silently overwrites in-memory state if file is newer.
- No locking → concurrent runs on the same board will corrupt the file.

---

## 6. Extension points

If you want to change AgentOps behavior, these are the leverage points:

| Goal | Where to look |
|---|---|
| Add a new model provider | New class in `providers.py`, register in `PROVIDERS` |
| Add a new role | New value in `WorkerRole` enum, update regex in `core.py:115-117` |
| Change the build loop | `OpsAgent.run()` in `core.py` |
| Change what gets sent to a worker | The prompt-building blocks in `run()` |
| Change board format | `Board._save()` and `Board._load()` |
| Add CLI subcommand | `cli.py:23-30` (argparse subparsers) |
| Add a check template (P2) | New `qa_templates/` directory, new code in `qa.py` |

**Avoid touching:**
- `types.py` without updating all consumers (it's a leaf module, so
  adding to it is safe; changing signatures is not).
- The `PROVIDERS` dict's existing keys (renames break user configs).

---

## 7. Dead code and known cleanup

`src/agent_ops/config.py` defines a `default_config` string that is
**never imported anywhere**. It was probably intended to be loaded by
`agent-ops init`, which doesn't exist yet (see
[TODO.md § 0.1](TODO.md#01-avengers-team-preset-default--fallback-chains)).

**Either:**
- Delete `config.py` outright, or
- Wire it into the future `agent-ops init` command.

For now: left as-is, but flagged here.

---

## 8. Testing

Current test coverage ([tests/](../tests/)):

- `test_board.py` — 5 cases: add, move, get_by_status, persistence, get_by_assignee
- `test_core.py` — 1 case: import smoke test

**What's missing:**
- No provider tests (would need network mocks for Copilot, etc.)
- No end-to-end `run()` test
- No CLI test

**How to add provider tests:** subclass the provider, monkeypatch
`httpx.AsyncClient` to return canned responses, assert the prompt and
the parsing. `pytest-asyncio` is already a dev dep.

---

## 9. Looking ahead

The `OpsAgent.run()` loop is small and easy to read — that's intentional.
But as we add the features in [TODO.md](../docs/TODO.md) (inbox loader,
escalation, time-budget runner, QA templates), the loop will grow.

When that happens, the right move is **not** to keep stacking logic into
`run()`. The right move is to introduce a declarative pipeline layer.
That's exactly what [LIGHTCHAIN.md](LIGHTCHAIN.md) proposes.
