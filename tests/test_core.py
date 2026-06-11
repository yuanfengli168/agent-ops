from agent_ops import OpsAgent


def test_import() -> None:
    """Verify package imports correctly."""
    agent = OpsAgent()
    assert agent.board is None
    assert len(agent.workers) == 0