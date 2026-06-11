"""Default config template for AgentOps."""

default_config = """
# AgentOps Configuration
# Copy to agent-ops.yaml and customize

workers:
  lead:
    provider: claude
    model: claude-sonnet-4-20250514
    api_key_env: ANTHROPIC_API_KEY

  ui:
    provider: openclaw
    model: claude-sonnet-4-20250514
    base_url: http://localhost:3100

  sde:
    provider: openclaw
    model: claude-sonnet-4-20250514
    base_url: http://localhost:3100

  review:
    provider: minimax
    model: MiniMax-M1
    api_key_env: MINIMAX_API_KEY

project:
  board: ./board.md
  repo: ./project
  max_iterations: 10
"""