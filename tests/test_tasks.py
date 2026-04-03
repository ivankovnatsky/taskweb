"""Tests for the tasks module."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from taskweb.tasks import (
    Task,
    _calculate_urgency,
    add_task,
    complete_task,
    delete_task,
    derive_from_tasks,
    edit_task,
    get_completed_tasks,
    get_pending_tasks,
    get_task_by_uuid,
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


def test_task_due_formatted_with_time():
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc)
    task = Task(uuid="test", due=str(int(dt.timestamp())))
    assert task.due_formatted == "2026-03-15 14:30"


def test_task_due_formatted_empty():
    task = Task(uuid="test", due="")
    assert task.due_formatted == ""


def test_task_due_date_property():
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc)
    task = Task(uuid="test", due=str(int(dt.timestamp())))
    assert task.due_date == "2026-03-15"


def test_task_due_date_empty():
    task = Task(uuid="test", due="")
    assert task.due_date == ""


def test_task_due_time_property():
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc)
    task = Task(uuid="test", due=str(int(dt.timestamp())))
    assert task.due_time == "14:30"


def test_task_due_time_midnight():
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc)
    task = Task(uuid="test", due=str(int(dt.timestamp())))
    assert task.due_time == ""


def test_task_due_time_empty():
    task = Task(uuid="test", due="")
    assert task.due_time == ""


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
    assert derived["projects"] == ["infra", "home"]  # sorted by count descending
    assert derived["tags"] == ["a", "b", "c"]  # a:2, b:2, c:1 — ties broken alphabetically
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


def test_add_task_with_due_time(tmp_path):
    from datetime import datetime, timezone

    db_path = _create_test_db(tmp_path)
    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = add_task("Timed task", due="2026-04-01", due_time="15:30")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT data FROM tasks")
    row = c.fetchone()
    conn.close()
    data = json.loads(row[0])
    due_ts = int(data["due"])
    dt = datetime.fromtimestamp(due_ts, tz=timezone.utc)
    assert dt.hour == 15
    assert dt.minute == 30
    assert dt.strftime("%Y-%m-%d") == "2026-04-01"


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


def test_edit_task_description(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-edit",
        {"description": "Original", "status": "pending", "entry": now},
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = edit_task("uuid-edit", description="Updated")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    data = json.loads(
        conn.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-edit",)).fetchone()[0]
    )
    conn.close()
    assert data["description"] == "Updated"


def test_edit_task_tags(tmp_path):
    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    _insert_task(
        db_path,
        "uuid-edit2",
        {"description": "Task", "status": "pending", "entry": now, "tags": "old"},
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = edit_task("uuid-edit2", description="Task", tags=["new", "next"])
    assert result is True

    conn = sqlite3.connect(str(db_path))
    data = json.loads(
        conn.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-edit2",)).fetchone()[0]
    )
    conn.close()
    assert data["tags"] == "new,next"
    assert "tag_old" not in data
    assert data["tag_new"] == "x"


def test_edit_task_preserves_due_time(tmp_path):
    """Editing with due_time should preserve the time component."""
    from datetime import datetime as dt, timezone as tz

    db_path = _create_test_db(tmp_path)
    now = str(int(time.time()))
    # Due at 2026-04-01 15:30:00 UTC (not midnight)
    due_dt = dt(2026, 4, 1, 15, 30, tzinfo=tz.utc)
    due_ts = str(int(due_dt.timestamp()))
    _insert_task(
        db_path,
        "uuid-due",
        {"description": "Timed", "status": "pending", "entry": now, "due": due_ts},
        ws_id=1,
    )

    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = edit_task("uuid-due", description="Timed", due="2026-04-01", due_time="15:30")
    assert result is True

    conn = sqlite3.connect(str(db_path))
    data = json.loads(
        conn.execute("SELECT data FROM tasks WHERE uuid = ?", ("uuid-due",)).fetchone()[0]
    )
    conn.close()
    assert data["due"] == due_ts  # preserved with time component


def test_edit_task_not_found(tmp_path):
    db_path = _create_test_db(tmp_path)
    with patch("taskweb.tasks._db_path", return_value=db_path):
        result = edit_task("nonexistent", description="X")
    assert result is False


# --- _calculate_urgency tests ---

_URG_DEFAULTS = {
    "due": "",
    "priority": "",
    "start": "",
    "tags": [],
    "project": "",
    "annotations": [],
    "entry": "",
    "wait": "",
    "scheduled": "",
}


def _urg(**overrides):
    return _calculate_urgency(**{**_URG_DEFAULTS, **overrides})


def test_urgency_baseline_no_fields():
    assert _urg() == 0.0


def test_urgency_project():
    assert _urg(project="work") > 0.0
    assert round(_urg(project="work"), 2) == 1.0


def test_urgency_active():
    now = str(int(time.time()))
    assert round(_urg(start=now), 2) == 4.0


def test_urgency_priority_h():
    assert round(_urg(priority="H"), 2) == 6.0


def test_urgency_priority_m():
    assert round(_urg(priority="M"), 2) == 3.9


def test_urgency_priority_l():
    assert round(_urg(priority="L"), 2) == 1.8


def test_urgency_next_tag():
    u = _urg(tags=["next"])
    # next tag (15.0) + 1 tag (0.8)
    assert round(u, 2) == 15.8


def test_urgency_tags_count():
    assert round(_urg(tags=["a"]), 2) == 0.8
    assert round(_urg(tags=["a", "b"]), 2) == 0.9
    assert round(_urg(tags=["a", "b", "c"]), 2) == 1.0


def test_urgency_annotations_count():
    ann1 = [{"entry": "1", "description": "x"}]
    ann2 = ann1 + [{"entry": "2", "description": "y"}]
    ann3 = ann2 + [{"entry": "3", "description": "z"}]
    assert round(_urg(annotations=ann1), 2) == 0.8
    assert round(_urg(annotations=ann2), 2) == 0.9
    assert round(_urg(annotations=ann3), 2) == 1.0


def test_urgency_due_overdue():
    # 10 days overdue -> capped at 1.0, * 12.0 = 12.0
    overdue = str(int(time.time()) - 86400 * 10)
    assert round(_urg(due=overdue), 2) == 12.0


def test_urgency_due_today():
    # Due right now: days_overdue ~ 0, value = (14/21 * 0.8) + 0.2 ≈ 0.733
    today = str(int(time.time()))
    u = _urg(due=today)
    assert 8.0 < u < 10.0  # 0.733 * 12 ≈ 8.8


def test_urgency_due_far_future():
    # Due in 30 days -> capped at 0.2, * 12.0 = 2.4
    future = str(int(time.time()) + 86400 * 30)
    assert round(_urg(due=future), 2) == 2.4


def test_urgency_due_boundary_14_days():
    # Due in exactly 14 days -> boundary: value = 0.2, * 12.0 = 2.4
    due_14d = str(int(time.time()) + 86400 * 14)
    u = _urg(due=due_14d)
    assert round(u, 1) == 2.4


def test_urgency_age_new_task():
    now = str(int(time.time()))
    u = _urg(entry=now)
    assert u < 0.1  # near zero age


def test_urgency_age_half_year():
    half_year_ago = str(int(time.time()) - 86400 * 182)
    u = _urg(entry=half_year_ago)
    assert 0.9 < u < 1.1  # ~182/365 * 2.0 ≈ 1.0


def test_urgency_age_capped():
    # Over 365 days -> capped at 2.0
    old = str(int(time.time()) - 86400 * 500)
    assert round(_urg(entry=old), 2) == 2.0


def test_urgency_no_entry():
    # Missing entry -> no age contribution (0.0)
    assert _urg(entry="") == 0.0


def test_urgency_waiting():
    # Waiting in the future -> -3.0
    future_wait = str(int(time.time()) + 86400 * 7)
    assert round(_urg(wait=future_wait), 2) == -3.0


def test_urgency_scheduled_past():
    # 10 days past scheduled -> capped at 1.0, * 5.0 = 5.0
    past = str(int(time.time()) - 86400 * 10)
    assert round(_urg(scheduled=past), 2) == 5.0


def test_urgency_scheduled_far_future():
    # 30 days out -> 0.2 * 5.0 = 1.0
    future = str(int(time.time()) + 86400 * 30)
    assert round(_urg(scheduled=future), 2) == 1.0


def test_urgency_combined():
    now = str(int(time.time()))
    overdue = str(int(time.time()) - 86400 * 10)
    u = _urg(
        due=overdue,
        priority="H",
        start=now,
        tags=["urgent"],
        project="work",
        entry=now,
    )
    # due 12.0 + priority 6.0 + active 4.0 + tag 0.8 + project 1.0 + age ~0
    assert u > 23.0
