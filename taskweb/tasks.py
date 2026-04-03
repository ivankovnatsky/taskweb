"""Interface to Taskwarrior 3 via direct SQLite access."""

import json
import logging
import os
import sqlite3
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
            dt = datetime.fromtimestamp(due_ts, tz=timezone.utc)
            # Show time only when it's not midnight
            if dt.hour == 0 and dt.minute == 0:
                return dt.strftime("%Y-%m-%d")
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return self.due

    @property
    def due_date(self) -> str:
        """Return just the date portion of due (YYYY-MM-DD) for form fields."""
        if not self.due:
            return ""
        try:
            due_ts = int(self.due)
            return datetime.fromtimestamp(due_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return self.due

    @property
    def due_time(self) -> str:
        """Return just the time portion of due (HH:MM) for form fields.

        Returns empty string if time is midnight (00:00).
        """
        if not self.due:
            return ""
        try:
            due_ts = int(self.due)
            dt = datetime.fromtimestamp(due_ts, tz=timezone.utc)
            if dt.hour == 0 and dt.minute == 0:
                return ""
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return ""

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


def _parse_task_data(uuid: str, data: dict, working_set: dict[str, int]) -> Task:
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

    urgency = _calculate_urgency(
        due=due,
        priority=priority,
        start=start,
        tags=tags,
        project=data.get("project", ""),
        annotations=annotations,
        entry=entry,
        wait=data.get("wait", ""),
        scheduled=data.get("scheduled", ""),
    )

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


def _calculate_urgency(
    due: str,
    priority: str,
    start: str,
    tags: list[str],
    project: str,
    annotations: list[dict],
    entry: str,
    wait: str,
    scheduled: str,
) -> float:
    """Calculate urgency matching Taskwarrior's algorithm and default coefficients."""
    value = 0.0
    now = time.time()

    # Project: coefficient 1.0
    if project:
        value += 1.0

    # Active (started): coefficient 4.0
    if start:
        value += 4.0

    # Scheduled: coefficient 5.0, ramps like due over 21 days
    if scheduled:
        try:
            days_overdue = (now - int(scheduled)) / 86400.0
            if days_overdue >= 7.0:
                sched_value = 1.0
            elif days_overdue >= -14.0:
                sched_value = ((days_overdue + 14.0) * 0.8 / 21.0) + 0.2
            else:
                sched_value = 0.2
            value += sched_value * 5.0
        except (ValueError, TypeError):
            pass

    # Waiting: coefficient -3.0
    if wait:
        try:
            if int(wait) > now:
                value -= 3.0
        except (ValueError, TypeError):
            pass

    # Annotations: coefficient 1.0, value 0.8/0.9/1.0
    ann_count = len(annotations)
    if ann_count >= 3:
        value += 1.0
    elif ann_count == 2:
        value += 0.9
    elif ann_count == 1:
        value += 0.8

    # Tags: coefficient 1.0, value 0.8/0.9/1.0
    tag_count = len(tags)
    if tag_count >= 3:
        value += 1.0
    elif tag_count == 2:
        value += 0.9
    elif tag_count == 1:
        value += 0.8

    # Due: coefficient 12.0, linear 0.2-1.0 over 21 days
    if due:
        try:
            days_overdue = (now - int(due)) / 86400.0
            if days_overdue >= 7.0:
                due_value = 1.0
            elif days_overdue >= -14.0:
                due_value = ((days_overdue + 14.0) * 0.8 / 21.0) + 0.2
            else:
                due_value = 0.2
            value += due_value * 12.0
        except (ValueError, TypeError):
            pass

    # Age: coefficient 2.0, linear up to 365 days
    if entry:
        try:
            age_days = (now - int(entry)) / 86400.0
            if age_days > 365:
                value += 2.0
            else:
                value += (age_days / 365.0) * 2.0
        except (ValueError, TypeError):
            pass
    else:
        pass  # no entry = no age contribution

    # Priority (UDA coefficients): H=6.0, M=3.9, L=1.8
    if priority == "H":
        value += 6.0
    elif priority == "M":
        value += 3.9
    elif priority == "L":
        value += 1.8

    # Special tag 'next': coefficient 15.0
    if "next" in tags:
        value += 15.0

    return round(value, 2)


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
        c = conn.cursor()
        c.execute("SELECT uuid, data FROM tasks")
        tasks = []
        for uuid, data_str in c.fetchall():
            data = json.loads(data_str)
            if status_filter and data.get("status", "pending") != status_filter:
                continue
            tasks.append(_parse_task_data(uuid, data, working_set))
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
        return _parse_task_data(row[0], json.loads(row[1]), working_set)
    finally:
        conn.rollback()
        conn.close()


def matches_query(
    query_lower: str,
    description: str,
    project: str,
    tags: list[str],
    task_id: int = 0,
) -> bool:
    """Check if a task matches a search query against description, project, tags, or ID."""
    if query_lower in description.lower():
        return True
    if query_lower in project.lower():
        return True
    if any(query_lower in tag.lower() for tag in tags):
        return True
    # For numeric queries, also match task ID
    if task_id and query_lower.isdigit() and str(task_id) == query_lower:
        return True
    return False


def search_statuses_with_matches(query: str) -> set[str]:
    """Return set of status names that have tasks matching the query.

    Lightweight — no Task parsing.
    """
    query_lower = query.lower()
    conn = _connect()
    try:
        conn.execute("BEGIN DEFERRED")
        working_set = _get_working_set(conn)
        c = conn.cursor()
        c.execute("SELECT uuid, data FROM tasks")
        statuses: set[str] = set()
        for uuid, data_str in c.fetchall():
            data = json.loads(data_str)
            tags_str = data.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            task_id = working_set.get(uuid, 0)
            if matches_query(
                query_lower,
                data.get("description", ""),
                data.get("project", ""),
                tags,
                task_id,
            ):
                statuses.add(data.get("status", "pending"))
        return statuses
    finally:
        conn.rollback()
        conn.close()


def derive_from_tasks(tasks: list[Task]) -> dict:
    """Derive projects, tags, and counts from an already-fetched task list."""
    project_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for t in tasks:
        if t.project:
            project_counts[t.project] = project_counts.get(t.project, 0) + 1
        for tag in t.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    # Sort by task count descending, then alphabetically for ties
    projects = sorted(project_counts, key=lambda p: (-project_counts[p], p))
    tags = sorted(tag_counts, key=lambda t: (-tag_counts[t], t))
    overdue = [t for t in tasks if t.is_overdue]
    return {
        "projects": projects,
        "tags": tags,
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
    due_time: str = "",
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
                if due_time:
                    due_dt = datetime.strptime(
                        f"{due} {due_time}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone.utc)
                else:
                    due_dt = datetime.strptime(due, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
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
    due_time: str = "",
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

        # Due — combine date and time fields
        old_due = data.get("due", "")
        if due:
            try:
                if due_time:
                    due_dt = datetime.strptime(
                        f"{due} {due_time}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone.utc)
                else:
                    due_dt = datetime.strptime(due, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                new_due = str(int(due_dt.timestamp()))
            except (ValueError, TypeError):
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
