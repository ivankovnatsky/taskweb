"""Tests for the tasks module."""

import json
from unittest.mock import MagicMock, patch

from taskweb.tasks import Task, _parse_tasks, get_pending_tasks, get_projects, get_tags


def test_task_age_hours():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    entry = now.strftime("%Y%m%dT%H%M%SZ")
    task = Task(uuid="test", entry=entry)
    assert task.age in ("<1h", "1h", "0h") or "h" in task.age or "<" in task.age


def test_task_age_days():
    task = Task(uuid="test", entry="20260301T000000Z")
    age = task.age
    assert age.endswith("d") or age.endswith("mo") or age.endswith("y")


def test_task_age_empty():
    task = Task(uuid="test", entry="")
    assert task.age == ""


def test_task_due_formatted():
    task = Task(uuid="test", due="20260315T000000Z")
    assert task.due_formatted == "2026-03-15"


def test_task_due_formatted_empty():
    task = Task(uuid="test", due="")
    assert task.due_formatted == ""


def test_task_is_overdue():
    task = Task(uuid="test", due="20200101T000000Z")
    assert task.is_overdue is True


def test_task_not_overdue():
    task = Task(uuid="test", due="20990101T000000Z")
    assert task.is_overdue is False


def test_task_is_active():
    task = Task(uuid="test", start="20260101T000000Z")
    assert task.is_active is True


def test_task_not_active():
    task = Task(uuid="test")
    assert task.is_active is False


def test_task_is_recurring():
    task = Task(uuid="test", recur="weekly")
    assert task.is_recurring is True


def test_task_is_completed():
    task = Task(uuid="test", status="completed")
    assert task.is_completed is True


def test_parse_tasks():
    data = json.dumps([
        {
            "uuid": "abc-123",
            "id": 1,
            "description": "Test task",
            "status": "pending",
            "project": "test",
            "tags": ["tag1"],
            "urgency": 5.0,
            "entry": "20260301T000000Z",
        }
    ])
    tasks = _parse_tasks(data)
    assert len(tasks) == 1
    assert tasks[0].description == "Test task"
    assert tasks[0].project == "test"
    assert tasks[0].tags == ["tag1"]


def test_parse_tasks_empty():
    assert _parse_tasks("[]") == []


def test_parse_tasks_invalid():
    assert _parse_tasks("invalid json") == []


@patch("taskweb.tasks._run_task")
def test_get_pending_tasks(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"uuid": "1", "id": 1, "description": "Task 1", "status": "pending", "urgency": 5.0},
            {"uuid": "2", "id": 2, "description": "Task 2", "status": "pending", "urgency": 10.0},
        ]),
    )
    tasks = get_pending_tasks()
    assert len(tasks) == 2
    assert tasks[0].urgency > tasks[1].urgency
    mock_run.assert_called_once_with("status:pending", "export")


@patch("taskweb.tasks._run_task")
def test_get_projects(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"uuid": "1", "id": 1, "description": "T1", "status": "pending", "project": "infra"},
            {"uuid": "2", "id": 2, "description": "T2", "status": "pending", "project": "home"},
            {"uuid": "3", "id": 3, "description": "T3", "status": "pending", "project": "infra"},
        ]),
    )
    projects = get_projects()
    assert projects == ["home", "infra"]


@patch("taskweb.tasks._run_task")
def test_get_tags(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"uuid": "1", "id": 1, "description": "T1", "status": "pending", "tags": ["a", "b"]},
            {"uuid": "2", "id": 2, "description": "T2", "status": "pending", "tags": ["b", "c"]},
        ]),
    )
    tags = get_tags()
    assert tags == ["a", "b", "c"]
