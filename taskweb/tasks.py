"""Interface to Taskwarrior 3 via direct SQLite access."""

import json
import logging
import os
import sqlite3
import subprocess
import time
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    """Raised when the Taskwarrior database cannot be found or opened."""


@dataclass
class Task:
    uuid: str
    id: int = 0
    description: str = ""
    status: str = "pending"
    project: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = ""
    due: str = ""
    entry: str = ""
    modified: str = ""
    urgency: float = 0.0
    start: str = ""
    end: str = ""
    recur: str = ""
    wait: str = ""
    annotations: list[dict] = field(default_factory=list)

    @property
    def short_uuid(self) -> str:
        return self.uuid[:8]

    @property
    def age(self) -> str:
        if not self.entry:
            return ""
        try:
            entry_ts = int(self.entry)
            delta = datetime.now(timezone.utc) - datetime.fromtimestamp(entry_ts, tz=timezone.utc)
            days = delta.days
            if days == 0:
                hours = delta.seconds // 3600
                return f"{hours}h" if hours > 0 else "<1h"
            if days < 30:
                return f"{days}d"
            if days < 365:
                return f"{days // 30}mo"
            return f"{days // 365}y"
        except (ValueError, TypeError):
            return ""

    @property
    def due_formatted(self) -> str:
        if not self.due:
            return ""
        try:
            due_ts = int(self.due)
            return datetime.fromtimestamp(due_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return self.due

    @property
    def is_overdue(self) -> bool:
        if not self.due:
            return False
        try:
            due_ts = int(self.due)
            return due_ts < time.time()
        except (ValueError, TypeError):
            return False

    @property
    def is_active(self) -> bool:
        return bool(self.start)

    @property
    def wait_formatted(self) -> str:
        if not self.wait:
            return ""
        try:
            wait_ts = int(self.wait)
            return datetime.fromtimestamp(wait_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return self.wait

    @property
    def is_recurring(self) -> bool:
        return bool(self.recur)

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"


def _db_path() -> Path:
    # 1. Explicit env var takes priority
    data_dir = os.environ.get("TASKDATA")
    if data_dir:
        return Path(os.path.expanduser(data_dir)) / "taskchampion.sqlite3"

    # 2. Read data.location from taskrc
    taskrc = Path(os.path.expanduser(os.environ.get("TASKRC", "~/.taskrc")))
    if taskrc.exists():
        try:
            for line in taskrc.read_text().splitlines():
                line = line.strip()
                if line.startswith("data.location"):
                    _, _, value = line.partition("=")
                    value = value.strip()
                    if value:
                        return Path(os.path.expanduser(value)) / "taskchampion.sqlite3"
        except OSError:
            pass

    # 3. Default
    return Path(os.path.expanduser("~/.task")) / "taskchampion.sqlite3"


def _connect() -> sqlite3.Connection:
    db = _db_path()
    if not db.exists():
        raise DatabaseUnavailableError(
            f"Database not found: {db}\nSet TASKDATA to your Taskwarrior 3 data directory."
        )
    conn = sqlite3.connect(str(db), timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _parse_task_data(
    uuid: str, data: dict, working_set: dict[str, int], urgency_map: dict[str, float]
) -> Task:
    """Parse a task's JSON data dict into a Task object."""
    tags_str = data.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    annotations = []
    for key, value in data.items():
        if key.startswith("annotation_"):
            ts = key[len("annotation_") :]
            annotations.append({"entry": ts, "description": value})
    annotations.sort(key=lambda a: a["entry"])

    entry = data.get("entry", "")
    due = data.get("due", "")
    start = data.get("start", "")
    priority = data.get("priority", "")
    status = data.get("status", "pending")

    urgency = urgency_map.get(uuid, 0.0)

    return Task(
        uuid=uuid,
        id=working_set.get(uuid, 0),
        description=data.get("description", ""),
        status=status,
        project=data.get("project", ""),
        tags=tags,
        priority=priority,
        due=due,
        entry=entry,
        modified=data.get("modified", ""),
        urgency=urgency,
        start=start,
        end=data.get("end", ""),
        recur=data.get("recur", ""),
        wait=data.get("wait", ""),
        annotations=annotations,
    )


def _get_urgency_map(task_uuid: str | None = None) -> dict[str, float]:
    """Get urgency values from Taskwarrior CLI via 'task export'.

    If task_uuid is provided, only export that single task.
    """
    try:
        cmd = ["task"]
        if task_uuid:
            cmd.append(task_uuid)
        cmd.append("export")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            tasks = json.loads(result.stdout)
            return {t["uuid"]: t.get("urgency", 0.0) for t in tasks}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        logger.warning("Failed to get urgency from task CLI, falling back to 0.0")
    return {}


def _get_working_set(conn: sqlite3.Connection) -> dict[str, int]:
    """Get the working set mapping uuid -> id."""
    c = conn.cursor()
    c.execute("SELECT id, uuid FROM working_set")
    return {uuid: id_ for id_, uuid in c.fetchall()}


def get_tasks(status_filter: str = "") -> list[Task]:
    conn = _connect()
    try:
        conn.execute("BEGIN DEFERRED")
        working_set = _get_working_set(conn)
        urgency_map = _get_urgency_map()
        c = conn.cursor()
        c.execute("SELECT uuid, data FROM tasks")
        tasks = []
        for uuid, data_str in c.fetchall():
            data = json.loads(data_str)
            if status_filter and data.get("status", "pending") != status_filter:
                continue
            tasks.append(_parse_task_data(uuid, data, working_set, urgency_map))
        tasks.sort(key=lambda t: t.urgency, reverse=True)
        return tasks
    finally:
        conn.rollback()
        conn.close()


def get_pending_tasks(filter_str: str = "") -> list[Task]:
    tasks = get_tasks("pending")
    if not filter_str:
        return tasks

    filtered = []
    for t in tasks:
        match = True
        for part in filter_str.split():
            if part.startswith("project:"):
                if t.project != part[len("project:") :]:
                    match = False
            elif part.startswith("+"):
                if part[1:] not in t.tags:
                    match = False
        if match:
            filtered.append(t)
    return filtered


def get_waiting_tasks() -> list[Task]:
    tasks = get_tasks("waiting")
    tasks.sort(key=lambda t: t.urgency, reverse=True)
    return tasks


def get_completed_tasks() -> list[Task]:
    tasks = get_tasks("completed")
    tasks.sort(key=lambda t: t.end, reverse=True)
    return tasks


def get_deleted_tasks() -> list[Task]:
    tasks = get_tasks("deleted")
    tasks.sort(key=lambda t: t.end, reverse=True)
    return tasks


def get_task_by_uuid(uuid: str) -> Task | None:
    conn = _connect()
    try:
        conn.execute("BEGIN DEFERRED")
        working_set = _get_working_set(conn)
        c = conn.cursor()
        c.execute("SELECT uuid, data FROM tasks WHERE uuid = ?", (uuid,))
        row = c.fetchone()
        if not row:
            return None
        urgency_map = _get_urgency_map(uuid)
        return _parse_task_data(row[0], json.loads(row[1]), working_set, urgency_map)
    finally:
        conn.rollback()
        conn.close()


def derive_from_tasks(tasks: list[Task]) -> dict:
    """Derive projects, tags, and counts from an already-fetched task list."""
    projects = sorted({t.project for t in tasks if t.project})
    tags = set()
    for t in tasks:
        tags.update(t.tags)
    overdue = [t for t in tasks if t.is_overdue]
    return {
        "projects": projects,
        "tags": sorted(tags),
        "counts": {
            "pending": len(tasks),
            "overdue": len(overdue),
        },
    }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_create(c: sqlite3.Cursor, task_uuid: str) -> None:
    op = json.dumps({"Create": {"uuid": task_uuid}})
    c.execute("INSERT INTO operations (data) VALUES (?)", (op,))


def _record_update(
    c: sqlite3.Cursor,
    task_uuid: str,
    prop: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    op = json.dumps(
        {
            "Update": {
                "uuid": task_uuid,
                "property": prop,
                "old_value": old_value,
                "value": new_value,
                "timestamp": _iso_now(),
            }
        }
    )
    c.execute("INSERT INTO operations (data) VALUES (?)", (op,))


def _record_undo_point(c: sqlite3.Cursor) -> None:
    c.execute("INSERT INTO operations (data) VALUES (?)", ('"UndoPoint"',))


def _update_task(uuid: str, updates: dict) -> bool:
    """Update task properties in the database."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("SELECT data FROM tasks WHERE uuid = ?", (uuid,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return False
        data = json.loads(row[0])
        _record_undo_point(c)
        for key, value in updates.items():
            old_value = data.get(key)
            _record_update(c, uuid, key, old_value, value)
        data.update(updates)
        now = str(int(time.time()))
        _record_update(c, uuid, "modified", data.get("modified"), now)
        data["modified"] = now
        c.execute("UPDATE tasks SET data = ? WHERE uuid = ?", (json.dumps(data), uuid))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to update task %s", uuid)
        return False
    finally:
        conn.close()


def add_task(
    description: str,
    project: str = "",
    tags: list[str] | None = None,
    priority: str = "",
    due: str = "",
) -> bool:
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        task_uuid = str(uuid_mod.uuid4())
        now = str(int(time.time()))
        data: dict = {
            "description": description,
            "status": "pending",
            "entry": now,
            "modified": now,
        }
        if project:
            data["project"] = project
        if tags:
            data["tags"] = ",".join(tags)
            for tag in tags:
                data[f"tag_{tag}"] = "x"
        if priority:
            data["priority"] = priority
        if due:
            try:
                due_dt = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                data["due"] = str(int(due_dt.timestamp()))
            except ValueError:
                data["due"] = due

        c = conn.cursor()

        # Record operations for sync (before data writes)
        _record_undo_point(c)
        _record_create(c, task_uuid)
        for key, value in data.items():
            _record_update(c, task_uuid, key, None, value)

        c.execute("INSERT INTO tasks (uuid, data) VALUES (?, ?)", (task_uuid, json.dumps(data)))

        # Add to working set (safe under BEGIN IMMEDIATE)
        c.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM working_set")
        next_id = c.fetchone()[0]
        c.execute("INSERT INTO working_set (id, uuid) VALUES (?, ?)", (next_id, task_uuid))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to add task")
        return False
    finally:
        conn.close()


def complete_task(uuid: str) -> bool:
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("SELECT data FROM tasks WHERE uuid = ?", (uuid,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return False
        data = json.loads(row[0])
        now = str(int(time.time()))
        _record_undo_point(c)
        _record_update(c, uuid, "status", data.get("status"), "completed")
        _record_update(c, uuid, "end", data.get("end"), now)
        _record_update(c, uuid, "modified", data.get("modified"), now)
        if "start" in data:
            _record_update(c, uuid, "start", data["start"], None)
        data["status"] = "completed"
        data["end"] = now
        data["modified"] = now
        data.pop("start", None)
        c.execute("UPDATE tasks SET data = ? WHERE uuid = ?", (json.dumps(data), uuid))
        c.execute("DELETE FROM working_set WHERE uuid = ?", (uuid,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to complete task %s", uuid)
        return False
    finally:
        conn.close()


def delete_task(uuid: str) -> bool:
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("SELECT data FROM tasks WHERE uuid = ?", (uuid,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return False
        data = json.loads(row[0])
        now = str(int(time.time()))
        _record_undo_point(c)
        _record_update(c, uuid, "status", data.get("status"), "deleted")
        _record_update(c, uuid, "end", data.get("end"), now)
        _record_update(c, uuid, "modified", data.get("modified"), now)
        data["status"] = "deleted"
        data["end"] = now
        data["modified"] = now
        c.execute("UPDATE tasks SET data = ? WHERE uuid = ?", (json.dumps(data), uuid))
        c.execute("DELETE FROM working_set WHERE uuid = ?", (uuid,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to delete task %s", uuid)
        return False
    finally:
        conn.close()


def edit_task(
    uuid: str,
    description: str = "",
    project: str = "",
    tags: list[str] | None = None,
    priority: str = "",
    due: str = "",
    recur: str = "",
    annotation: str = "",
) -> bool:
    """Edit a task's fields. Empty strings clear the field."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("SELECT data FROM tasks WHERE uuid = ?", (uuid,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return False
        data = json.loads(row[0])
        _record_undo_point(c)

        # Description (required, don't clear)
        if description and description != data.get("description", ""):
            _record_update(c, uuid, "description", data.get("description"), description)
            data["description"] = description

        # Project
        old_project = data.get("project", "")
        if project != old_project:
            _record_update(c, uuid, "project", old_project or None, project or None)
            if project:
                data["project"] = project
            else:
                data.pop("project", None)

        # Tags
        old_tags_str = data.get("tags", "")
        old_tags = [t.strip() for t in old_tags_str.split(",") if t.strip()] if old_tags_str else []
        new_tags = tags if tags is not None else []
        if sorted(new_tags) != sorted(old_tags):
            new_tags_str = ",".join(new_tags) if new_tags else None
            _record_update(c, uuid, "tags", old_tags_str or None, new_tags_str)
            # Remove old tag_ keys
            for t in old_tags:
                key = f"tag_{t}"
                if key in data:
                    _record_update(c, uuid, key, data[key], None)
                    del data[key]
            # Set new tags
            if new_tags:
                data["tags"] = ",".join(new_tags)
                for t in new_tags:
                    data[f"tag_{t}"] = "x"
                    _record_update(c, uuid, f"tag_{t}", None, "x")
            else:
                data.pop("tags", None)

        # Priority
        old_priority = data.get("priority", "")
        if priority != old_priority:
            _record_update(c, uuid, "priority", old_priority or None, priority or None)
            if priority:
                data["priority"] = priority
            else:
                data.pop("priority", None)

        # Due — preserve existing timestamp if only the date portion matches
        old_due = data.get("due", "")
        if due and old_due:
            try:
                old_date = datetime.fromtimestamp(int(old_due), tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                if due == old_date:
                    new_due = old_due  # preserve original timestamp with time component
                else:
                    due_dt = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    new_due = str(int(due_dt.timestamp()))
            except (ValueError, TypeError):
                new_due = due
        elif due:
            try:
                due_dt = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                new_due = str(int(due_dt.timestamp()))
            except ValueError:
                new_due = due
        else:
            new_due = ""
        if new_due != old_due:
            _record_update(c, uuid, "due", old_due or None, new_due or None)
            if new_due:
                data["due"] = new_due
            else:
                data.pop("due", None)

        # Recur
        old_recur = data.get("recur", "")
        if recur != old_recur:
            _record_update(c, uuid, "recur", old_recur or None, recur or None)
            if recur:
                data["recur"] = recur
            else:
                data.pop("recur", None)

        # Annotation (add new if provided)
        if annotation:
            ts = str(int(time.time()))
            ann_key = f"annotation_{ts}"
            data[ann_key] = annotation
            _record_update(c, uuid, ann_key, None, annotation)

        # Modified
        now = str(int(time.time()))
        _record_update(c, uuid, "modified", data.get("modified"), now)
        data["modified"] = now

        c.execute("UPDATE tasks SET data = ? WHERE uuid = ?", (json.dumps(data), uuid))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Failed to edit task %s", uuid)
        return False
    finally:
        conn.close()
