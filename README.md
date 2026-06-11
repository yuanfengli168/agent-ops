# AgentOps 🏗️

> Turn ideas into shipped code — automatically.

AgentOps is a multi-agent orchestrator that connects AI workers into a production pipeline. Define your idea, and the system breaks it down, assigns tasks, and ships it through an iterative loop of building and reviewing.

## Architecture

```
         ┌─────────────┐
         │  You (idea)  │
         └──────┬───────┘
                │
         ┌──────▼───────┐
         │   Ops Agent   │  ← Orchestrator / PM
         └──────┬───────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│ Lead  │  │  UI   │  │  SDE  │
│(Claude)│  │(OpenClaw)│  │(OpenClaw)│
└───┬───┘  └───┬───┘  └───┬───┘
    │          │          │
    └──────────┼──────────┘
               │
         ┌─────▼──────┐
         │   Review    │  ← MiniMax
         └─────┬──────┘
               │
         ┌─────▼──────┐
         │   Shipped   │
         └────────────┘
```

## Workers

| Worker | Role | Provider |
|--------|------|----------|
| Lead | Requirements, architecture, task breakdown | Claude / Anthropic |
| UI | Frontend, UX, React/CSS | OpenClaw |
| SDE | Backend, APIs, infra | OpenClaw |
| Review | Code review, quality, security | MiniMax |

## Quick Start

```bash
pip install agent-ops
```

```python
from agent_ops import OpsAgent

ops = OpsAgent()

# Register workers
ops.register_worker("lead", provider="claude", model="claude-sonnet-4-20250514")
ops.register_worker("ui", provider="openclaw", model="claude-sonnet-4-20250514")
ops.register_worker("sde", provider="openclaw", model="claude-sonnet-4-20250514")
ops.register_worker("review", provider="minimax", model="MiniMax-M1")

# Ship an idea
ops.run("Build a CLI tool that converts currency using live exchange rates")
```

## Configuration

```yaml
# agent-ops.yaml
workers:
  lead:
    provider: claude
    model: claude-sonnet-4-20250514
    api_key_env: ANTHROPIC_API_KEY
  
  ui:
    provider: openclaw
    model: claude-sonnet-4-20250514
  
  sde:
    provider: openclaw
    model: claude-sonnet-4-20250514
  
  review:
    provider: minimax
    model: MiniMax-M1
    api_key_env: MINIMAX_API_KEY

project:
  board: ./board.md
  repo: ./project
  max_iterations: 10
```

## Project Board

Tasks are tracked in a markdown board:

```markdown
## TODO
- [ ] T001: Set up FastAPI project skeleton @sde
- [ ] T002: Design data models @lead

## IN-PROGRESS
- [ ] T003: Create React frontend shell @ui

## IN-REVIEW
- [ ] T004: Implement /convert endpoint @sde

## DONE
- [x] T005: Write project brief @lead
```

## How It Works

1. **Idea → Brief**: Lead worker creates a project brief with requirements
2. **Brief → Tasks**: Lead breaks it into concrete tasks
3. **Task → Code**: UI/SDE workers pick up tasks and implement
4. **Code → Review**: Reviewer checks quality, suggests fixes
5. **Fix → Re-review**: Loop until approved
6. **Approved → Ship**: Merge and close

## Development

```bash
git clone https://github.com/your-username/agent-ops.git
cd agent-ops
pip install -e ".[dev]"
pytest
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).