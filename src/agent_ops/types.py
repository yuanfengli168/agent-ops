"""Worker provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkerRole(str, Enum):
    LEAD = "lead"
    UI = "ui"
    SDE = "sde"
    REVIEW = "review"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    KILLED = "KILLED"


@dataclass
class Task:
    id: str
    title: str
    assignee: WorkerRole
    status: TaskStatus = TaskStatus.TODO
    description: str = ""
    result: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerConfig:
    role: WorkerRole
    provider: str  # "claude", "openclaw", "minimax", "custom"
    model: str = ""
    api_key_env: str = ""  # env var name for API key
    base_url: str = ""  # custom endpoint
    extra: dict[str, Any] = field(default_factory=dict)


class WorkerProvider(ABC):
    """Base class for worker providers."""

    def __init__(self, config: WorkerConfig) -> None:
        self.config = config

    @abstractmethod
    async def execute(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Execute a task and return the result."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable."""
        ...