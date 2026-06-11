"""Tests for agent-ops."""

import pytest
from pathlib import Path
from agent_ops.board import Board
from agent_ops.types import TaskStatus, WorkerRole


@pytest.fixture
def tmp_board(tmp_path: Path) -> Board:
    return Board(tmp_path / "board.md")


def test_add_task(tmp_board: Board) -> None:
    task = tmp_board.add("Set up project", WorkerRole.LEAD)
    assert task.id == "T001"
    assert task.status == TaskStatus.TODO
    assert task.assignee == WorkerRole.LEAD


def test_move_task(tmp_board: Board) -> None:
    tmp_board.add("Build API", WorkerRole.SDE)
    task = tmp_board.move("T001", TaskStatus.IN_PROGRESS)
    assert task.status == TaskStatus.IN_PROGRESS


def test_get_by_status(tmp_board: Board) -> None:
    tmp_board.add("Task 1", WorkerRole.LEAD)
    tmp_board.add("Task 2", WorkerRole.UI)
    tmp_board.move("T001", TaskStatus.DONE)

    done = tmp_board.get_by_status(TaskStatus.DONE)
    todo = tmp_board.get_by_status(TaskStatus.TODO)
    assert len(done) == 1
    assert len(todo) == 1


def test_persistence(tmp_path: Path) -> None:
    board1 = Board(tmp_path / "board.md")
    board1.add("Persistent task", WorkerRole.REVIEW)

    board2 = Board(tmp_path / "board.md")
    assert "T001" in board2.tasks
    assert board2.tasks["T001"].title == "Persistent task"


def test_get_by_assignee(tmp_board: Board) -> None:
    tmp_board.add("Frontend task", WorkerRole.UI)
    tmp_board.add("Backend task", WorkerRole.SDE)

    ui_tasks = tmp_board.get_by_assignee(WorkerRole.UI)
    assert len(ui_tasks) == 1
    assert ui_tasks[0].title == "Frontend task"