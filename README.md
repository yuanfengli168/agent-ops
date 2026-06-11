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
| Design | UI specs, mockups, wireframes, 3D renders | GPT-4o / DALL-E |
| UI | Frontend, UX, React/CSS | OpenClaw |
| SDE | Backend, APIs, infra | OpenClaw |
| Review | Code review + **design compliance check** | MiniMax |

## Quick Start

```bash
pip install agent-ops
```

### Set up TUI tokens (one-time)

AgentOps uses your **existing subscriptions** — no extra API keys to buy.

**Claude (Lead):**
1. Open [claude.ai](https://claude.ai) → F12 → Application → Cookies
2. Copy `sessionKey` value → `export CLAUDE_SESSION_TOKEN=...`

**MiniMax / 海螺AI (Review):**
1. Open [hailuoai.com](https://hailuoai.com) → F12 → Network
2. Send a message → find `authorization` header → `export MINIMAX_AUTH_TOKEN=...`

**OpenClaw (UI / SDE):**
- Already running locally at `localhost:3100`, no extra setup needed

### Run

```python
from agent_ops import OpsAgent

ops = OpsAgent()
ops.register_worker("lead", provider="claude-tui", model="claude-sonnet-4-20250514")
ops.register_worker("ui", provider="openclaw", model="claude-sonnet-4-20250514")
ops.register_worker("sde", provider="openclaw", model="claude-sonnet-4-20250514")
ops.register_worker("review", provider="minimax-tui", model="MiniMax-M1")

# Ship an idea
ops.run("Build a CLI tool that converts currency using live exchange rates")
```

## Configuration

```yaml
# agent-ops.yaml
workers:
  lead:
    provider: claude-tui        # Uses your Claude subscription
    model: claude-sonnet-4-20250514
    api_key_env: CLAUDE_SESSION_TOKEN
  
  ui:
    provider: openclaw          # Local gateway, free
    model: claude-sonnet-4-20250514
    base_url: http://localhost:3100
  
  sde:
    provider: openclaw          # Local gateway, free
    model: claude-sonnet-4-20250514
    base_url: http://localhost:3100
  
  review:
    provider: minimax-tui       # Uses your MiniMax subscription
    model: MiniMax-M1
    api_key_env: MINIMAX_AUTH_TOKEN

project:
  board: ./board.md
  repo: ./project
  max_iterations: 10
```

> **💡 No API keys to buy.** All workers use your existing subscriptions:
> - Claude Lead → your Claude Pro/Team plan
> - OpenClaw UI/SDE → local gateway (uses whatever models you've configured)
> - MiniMax Review → your 海螺AI subscription

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
2. **Brief → Design**: Design worker generates UI specs, mockups, and 3D renders
3. **Brief → Tasks**: Lead breaks it into concrete tasks
4. **Task → Code**: UI/SDE workers pick up tasks and implement (following design spec)
5. **Code → Review**: Reviewer checks code quality **AND design compliance** (gap vs design)
6. **Fix → Re-review**: Loop until code matches design
7. **Approved → Ship**: Merge and close

## Development

```bash
git clone https://github.com/your-username/agent-ops.git
cd agent-ops
pip install -e ".[dev]"
pytest
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).