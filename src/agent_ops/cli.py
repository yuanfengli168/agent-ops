"""CLI interface for AgentOps."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from agent_ops.core import OpsAgent

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-ops",
        description="AgentOps — Multi-agent orchestrator that turns ideas into shipped code",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_cmd = sub.add_parser("run", help="Run the full pipeline on an idea")
    run_cmd.add_argument("idea", help="Your project idea")
    run_cmd.add_argument("--config", "-c", default="agent-ops.yaml", help="Config file")
    run_cmd.add_argument("--max-iter", type=int, default=10, help="Max iterations")

    # dispatch
    disp_cmd = sub.add_parser("dispatch", help="Send a prompt to a specific worker")
    disp_cmd.add_argument("role", choices=["lead", "design", "ui", "sde", "qa", "review", "helper"])
    disp_cmd.add_argument("prompt", help="Prompt to send")
    disp_cmd.add_argument("--config", "-c", default="agent-ops.yaml")

    # status
    status_cmd = sub.add_parser("status", help="Show board status")
    status_cmd.add_argument("--config", "-c", default="agent-ops.yaml")

    # health
    health_cmd = sub.add_parser("health", help="Check worker health")
    health_cmd.add_argument("--config", "-c", default="agent-ops.yaml")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_run(args))
    elif args.command == "dispatch":
        asyncio.run(_dispatch(args))
    elif args.command == "status":
        asyncio.run(_status(args))
    elif args.command == "health":
        asyncio.run(_health(args))
    else:
        parser.print_help()


async def _run(args: argparse.Namespace) -> None:
    ops = OpsAgent(config_path=args.config)
    await ops.run(args.idea, max_iterations=args.max_iter)


async def _dispatch(args: argparse.Namespace) -> None:
    ops = OpsAgent(config_path=args.config)
    result = await ops.dispatch(args.role, args.prompt)
    console.print(result)


async def _status(args: argparse.Namespace) -> None:
    ops = OpsAgent(config_path=args.config)
    status = await ops.status()
    for k, v in status.items():
        console.print(f"  {k}: {v}")


async def _health(args: argparse.Namespace) -> None:
    ops = OpsAgent(config_path=args.config)
    health = await ops.health_check()
    for name, ok in health.items():
        icon = "✓" if ok else "✗"
        color = "green" if ok else "red"
        console.print(f"  [{color}]{icon} {name}[/{color}]")


if __name__ == "__main__":
    main()