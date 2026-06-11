"""Project board — markdown-based task tracker."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from agent_ops.types import Task, TaskStatus, WorkerRole


class Board:
    """Markdown-based kanban board for tracking tasks."""

    SECTIONS = list(TaskStatus)

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        if self.path.exists():
            self._load()

    def add(self, title: str, assignee: WorkerRole, description: str = "") -> Task:
        """Add a new task to the board."""
        task_id = f"T{len(self.tasks) + 1:03d}"
        now = datetime.now().isoformat(timespec="seconds")
        task = Task(
            id=task_id,
            title=title,
            assignee=assignee,
            status=TaskStatus.TODO,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self.tasks[task_id] = task
        self._save()
        return task

    def move(self, task_id: str, status: TaskStatus) -> Task:
        """Move a task to a new status."""
        task = self.tasks[task_id]
        task.status = status
        task.updated_at = datetime.now().isoformat(timespec="seconds")
        self._save()
        return task

    def get_by_status(self, status: TaskStatus) -> list[Task]:
        """Get all tasks with a given status."""
        return [t for t in self.tasks.values() if t.status == status]

    def get_by_assignee(self, assignee: WorkerRole) -> list[Task]:
        """Get all tasks assigned to a worker."""
        return [t for t in self.tasks.values() if t.assignee == assignee]

    def _save(self) -> None:
        """Persist board to markdown."""
        lines = ["# Project Board\n"]
        for status in self.SECTIONS:
            lines.append(f"## {status.value}\n")
            tasks = self.get_by_status(status)
            if not tasks:
                lines.append("_No tasks._\n")
            for t in tasks:
                check = "x" if status == TaskStatus.DONE else " "
                lines.append(f"- [{check}] {t.id}: {t.title} @{t.assignee.value}")
            lines.append("")
        self.path.write_text("\n".join(lines))

    def _load(self) -> None:
        """Load board from markdown."""
        content = self.path.read_text()
        current_status = TaskStatus.TODO
        for line in content.split("\n"):
            # Match section headers
            for status in TaskStatus:
                if line.strip() == f"## {status.value}":
                    current_status = status
                    break
            # Match task lines
            match = re.match(r"- \[.\] (T\d+): (.+?) @(\w+)", line)
            if match:
                task_id, title, assignee = match.groups()
                if task_id in self.tasks:
                    self.tasks[task_id].status = current_status
                else:
                    self.tasks[task_id] = Task(
                        id=task_id,
                        title=title,
                        assignee=WorkerRole(assignee),
                        status=current_status,
                    )