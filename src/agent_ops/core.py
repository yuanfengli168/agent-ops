"""OpsAgent — the orchestrator that ties everything together."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from agent_ops.board import Board
from agent_ops.providers import get_provider
from agent_ops.types import Task, TaskStatus, WorkerConfig, WorkerRole

console = Console()


class OpsAgent:
    """Multi-agent orchestrator: idea → tasks → build → review → ship."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.workers: dict[str, WorkerProvider] = {}  # type: ignore[name-defined]
        self.board: Board | None = None
        self._config: dict[str, Any] = {}

        if config_path:
            self.load_config(config_path)

    def load_config(self, path: str | Path) -> None:
        """Load configuration from YAML file."""
        path = Path(path)
        with open(path) as f:
            self._config = yaml.safe_load(f)

        project = self._config.get("project", {})
        board_path = project.get("board", "./board.md")
        self.board = Board(Path(board_path))

        for name, wcfg in self._config.get("workers", {}).items():
            cfg = WorkerConfig(
                role=WorkerRole(name),
                provider=wcfg["provider"],
                model=wcfg.get("model", ""),
                api_key_env=wcfg.get("api_key_env", ""),
                base_url=wcfg.get("base_url", ""),
                extra=wcfg.get("extra", {}),
            )
            self.workers[name] = get_provider(cfg)

    def register_worker(
        self,
        role: str,
        provider: str,
        model: str = "",
        api_key_env: str = "",
        base_url: str = "",
        **extra: Any,
    ) -> None:
        """Programmatically register a worker."""
        cfg = WorkerConfig(
            role=WorkerRole(role),
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            base_url=base_url,
            extra=extra,
        )
        self.workers[role] = get_provider(cfg)
        if self.board is None:
            self.board = Board(Path("./board.md"))

    async def dispatch(self, role: str, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Send a task to a specific worker."""
        if role not in self.workers:
            raise ValueError(f"Unknown worker: {role}. Available: {list(self.workers)}")
        console.print(f"[bold blue]→ Dispatching to {role}[/]")
        result = await self.workers[role].execute(prompt, context)
        console.print(f"[bold green]✓ {role} responded[/]")
        return result

    async def run(self, idea: str, max_iterations: int = 10) -> str:
        """Full pipeline: idea → brief → tasks → build → review → ship."""
        if not self.board:
            self.board = Board(Path("./board.md"))

        console.print(f"\n[bold]🚀 Starting project:[/] {idea}\n")

        # Step 1: Lead creates brief
        console.rule("[bold]Phase 1: Brief[/]")
        brief_prompt = (
            f"Project idea: {idea}\n\n"
            "Create a detailed project brief with:\n"
            "1. Problem statement\n"
            "2. Key features (max 5)\n"
            "3. Technical stack recommendation\n"
            "4. Task breakdown with IDs (T001, T002, etc.)\n"
            "5. Assign each task to: lead, ui, sde, or review\n\n"
            "Format tasks as: T{id}: {title} @{assignee}"
        )
        brief = await self.dispatch("lead", brief_prompt)

        # Step 2: Parse tasks from brief
        console.rule("[bold]Phase 2: Task Setup[/]")
        import re

        task_pattern = re.compile(r"(T\d+):\s*(.+?)\s*@(lead|ui|sde|review)", re.IGNORECASE)
        for match in task_pattern.finditer(brief):
            task_id, title, assignee = match.groups()
            self.board.add(title=title.strip(), assignee=WorkerRole(assignee.lower()))

        console.print(f"[bold]📋 Created {len(self.board.tasks)} tasks[/]\n")

        # Step 3: Execute tasks
        console.rule("[bold]Phase 3: Build[/]")
        for iteration in range(max_iterations):
            pending = self.board.get_by_status(TaskStatus.TODO)
            if not pending:
                console.print("[bold green]All tasks completed![/]")
                break

            console.print(f"\n[bold]Iteration {iteration + 1}[/] — {len(pending)} tasks remaining")
            task = pending[0]
            self.board.move(task.id, TaskStatus.IN_PROGRESS)

            console.print(f"  [yellow]→ {task.id}: {task.title} @{task.assignee.value}[/]")
            result = await self.dispatch(
                task.assignee.value,
                f"Task: {task.title}\n\nContext: {brief}\n\nPlease implement this.",
            )

            # Step 4: Review (except review tasks themselves)
            if task.assignee != WorkerRole.REVIEW:
                self.board.move(task.id, TaskStatus.IN_REVIEW)
                review_result = await self.dispatch(
                    "review",
                    f"Review this implementation:\n\n{result}\n\nTask: {task.title}",
                )
                # Simple heuristic: if review says approve/looks good, mark done
                if any(kw in review_result.lower() for kw in ["approve", "looks good", "lgtm", "✓"]):
                    self.board.move(task.id, TaskStatus.DONE)
                    console.print(f"  [green]✓ {task.id} approved[/]")
                else:
                    # Keep in review, will retry
                    console.print(f"  [yellow]⟳ {task.id} needs revision[/]")
            else:
                self.board.move(task.id, TaskStatus.DONE)

        # Final summary
        console.rule("[bold]Summary[/]")
        done = len(self.board.get_by_status(TaskStatus.DONE))
        remaining = len(self.board.get_by_status(TaskStatus.TODO)) + len(
            self.board.get_by_status(TaskStatus.IN_PROGRESS)
        )
        console.print(f"[green]✓ Done: {done}[/]  [yellow]⏳ Remaining: {remaining}[/]")

        return brief

    async def status(self) -> dict[str, int]:
        """Get board status summary."""
        if not self.board:
            return {}
        return {
            "todo": len(self.board.get_by_status(TaskStatus.TODO)),
            "in_progress": len(self.board.get_by_status(TaskStatus.IN_PROGRESS)),
            "in_review": len(self.board.get_by_status(TaskStatus.IN_REVIEW)),
            "done": len(self.board.get_by_status(TaskStatus.DONE)),
        }

    async def health_check(self) -> dict[str, bool]:
        """Check all workers are reachable."""
        results = {}
        for name, worker in self.workers.items():
            try:
                results[name] = await worker.health_check()
            except Exception:
                results[name] = False
        return results