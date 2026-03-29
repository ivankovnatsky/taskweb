"""Tests for the tasks module."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from taskweb.tasks import (
    Task,
    add_task,
    complete_task,
    delete_task,
    derive_from_tasks,
    get_completed_tasks,
    get_pending_tasks,
    get_task_by_uuid,
    start_task,
    stop_task,
)


def _create_test_db(tmp_path: Path) -> Path:
    """Create a test taskchampion.sqlite3 database."""
    db_path = tmp_path / "taskchampion.sqlite3"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE tasks (uuid STRING PRIMARY KEY, data STRING)")
    c.execute("CREATE TABLE working_set (id INTEGER PRIMARY KEY, uuid STRING)")
    c.execute(
        "CREATE TABLE operations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "data STRING, synced bool DEFAULT false)"
    )
    conn.commit()
    conn.close()
    return db_path


def _insert_task(db_path: Path, uuid: str, data: dict, ws_id: int | None = None):
    """Insert a task into the test database."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("INSERT INTO tasks (uuid, data) VALUES (?, ?)", (uuid, json.dumps(data)))
    if ws_id is not None:
        c.execute("INSERT INTO working_set (id, uuid) VALUES (?, ?)", (ws_id, uuid))
    conn.commit()
    conn.close()


def test_task_short_uuid():
    task = Task(uuid="abc12345-6789-0000-1111-222233334444")
    assert task.short_uuid == "abc12345"


def test_task_age_hours():
    now = str(int(time.time()))
    task = Task(uuid="test", entry=now)
    assert task.age == "<1h"


def test_task_age_days():
    old = str(int(time.time()) - 86400 * 5)
    task = Task(uuid="test", entry=old)
    assert task.age == "5d"


def test_task_age_empty():
    task = Task(uuid="test", entry="")
    assert task.age == ""


def test_task_due_formatted():
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 15, tzinfo=timezone.utc)
    task = Task(uuid="test", due=str(int(dt.timestamp())))
    assert task.due_formatted == "2026-03-15"


def test_task_due_formatted_empty():
    task = Task(uuid="test", due="")
    assert task.due_formatted == ""


def test_task_is_overdue():
    task = Task(uuid="test", due=str(int(time.time()) - 86400))
    assert task.is_overdue is True


def test_task_not_overdue():
    task = Task(uuid="test", due=str(int(time.time()) + 86400 * 365))
    assert task.is_overdue is False


def test_task_is_active():
    task = Task(uuid="test", start=str(int(time.time())))
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


def test_derive_from_tasks():
    tasks = [
        Task(uuid="1", project="infra", tags=["a", "b"], due=str(int(time.time()) - 86400)),
        Task(uuid="2", project="home", tags=["b", "c"]),
        Task(uuid="3", project="infra", tags=["a"]),
    ]
    derived = derive_from_tasks(tasks)
    assert derived["projects"] == ["home", "infra"]
    assert derived["tags"] == ["a", "b", "c"]
    assert derived["counts"]["pending"] == 3
    assert derived["counts"]["overdue"] == 1


def test_derive_from_tasks_empty():
    derived = derive_from_tasks([])
    assert derived["projects"] == []
    assert derived["tags"] == []
    assert derived["counts"]["pending"] == 0
    assert derived["counts"]["overdue"] == 0


def test_get_pending_tasks(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-1",
        {
            "description": "Task 1",
            "status": "pending",
            "entry": now,
            "priority": "H",
        },
        ws_id=1,
    )
    _insert_task(
        db_path,
        "uuid-2",
        {
            "description": "Task 2",
            "status": "pending",
            "entry": now,
        },
        ws_id=2,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        tasks = get_pending_tasks()
    assert len(tasks) == 2
    assert tasks[0].urgency > tasks[1].urgency


def test_get_pending_tasks_empty(tmp_path):
    db_path = _create_test_db(tmp_path)
    with patch("taskweb.tasks._db_path", return_value=db_path):
        tasks = get_pending_tasks()
    assert tasks == []


def test_get_completed_tasks(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-1",
        {
            "description": "Done task",
            "status": "completed",
            "entry": now,
            "end": now,
        },
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        tasks = get_completed_tasks()
    assert len(tasks) == 1
    assert tasks[0].description == "Done task"


def test_get_task_by_uuid(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-abc",
        {
            "description": "Specific task",
            "status": "pending",
            "entry": now,
        },
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        task = get_task_by_uuid("uuid-abc")
    assert task is not None
    assert task.description == "Specific task"
    assert task.id == 1


def test_get_task_by_uuid_not_found(tmp_path):
    db_path = _create_test_db(tmp_path)
    with patch("taskweb.tasks._db_path", return_value=db_path):
        task = get_task_by_uuid("nonexistent")
    assert task is None


def test_add_task(tmp_path):
    db_path = _create_test_db(tmp_path)
    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = add_task("New task", project="test", tags=["a", "b"], priority="H")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks")
    row = c.fetchone()
    conn.close()
    data = json.loads(row[0])
    assert data["description"] == "New task"
    assert data["project"] == "test"
    assert data["priority"] == "H"
    assert data["tags"] == "a,b"


def test_complete_task(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-done",
        {
            "description": "To complete",
            "status": "pending",
            "entry": now,
        },
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = complete_task("uuid-done")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-done",))
    data = json.loads(c.fetchone()[0])
    c.execute("SELECT * FROM working_set WHERE uuid = ?", ("uuid-done",))
    ws_row = c.fetchone()
    conn.close()
    assert data["status"] == "completed"
    assert "end" in data
    assert ws_row is None


def test_delete_task(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-del",
        {
            "description": "To delete",
            "status": "pending",
            "entry": now,
        },
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = delete_task("uuid-del")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-del",))
    data = json.loads(c.fetchone()[0])
    conn.close()
    assert data["status"] == "deleted"


def test_start_task(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-start",
        {
            "description": "To start",
            "status": "pending",
            "entry": now,
        },
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = start_task("uuid-start")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-start",))
    data = json.loads(c.fetchone()[0])
    conn.close()
    assert "start" in data


def test_stop_task(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-stop",
        {
            "description": "To stop",
            "status": "pending",
            "entry": now,
            "start": now,
        },
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = stop_task("uuid-stop")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-stop",))
    data = json.loads(c.fetchone()[0])
    conn.close()
    assert "start" not in data


def test_filter_by_project(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-1",
        {
            "description": "Task A",
            "status": "pending",
            "project": "infra",
            "entry": now,
        },
        ws_id=1,
    )
    _insert_task(
        db_path,
        "uuid-2",
        {
            "description": "Task B",
            "status": "pending",
            "project": "home",
            "entry": now,
        },
        ws_id=2,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        tasks = get_pending_tasks("project:infra")
    assert len(tasks) == 1
    assert tasks[0].project == "infra"


def test_filter_by_tag(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-1",
        {
            "description": "Tagged",
            "status": "pending",
            "tags": "next,urgent",
            "entry": now,
        },
        ws_id=1,
    )
    _insert_task(
        db_path,
        "uuid-2",
        {
            "description": "Untagged",
            "status": "pending",
            "entry": now,
        },
        ws_id=2,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        tasks = get_pending_tasks("+next")
    assert len(tasks) == 1
    assert tasks[0].description == "Tagged"
