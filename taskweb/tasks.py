"""Interface to Taskwarrior 3 via subprocess."""

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone


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
    annotations: list[dict] = field(default_factory=list)

    @property
    def short_uuid(self) -> str:
        return self.uuid[:8]

    @property
    def age(self) -> str:
        if not self.entry:
            return ""
        try:
            entry_dt = datetime.strptime(self.entry, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - entry_dt
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
            due_dt = datetime.strptime(self.due, "%Y%m%dT%H%M%SZ")
            return due_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return self.due

    @property
    def is_overdue(self) -> bool:
        if not self.due:
            return False
        try:
            due_dt = datetime.strptime(self.due, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return due_dt < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False

    @property
    def is_active(self) -> bool:
        return bool(self.start)

    @property
    def is_recurring(self) -> bool:
        return bool(self.recur)

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"


class TaskError(Exception):
    pass


def _run_task(*args: str) -> subprocess.CompletedProcess:
    cmd = ["task", "rc.confirmation=off", "rc.bulk=0"]
    data_dir = os.environ.get("TASKDATA")
    taskrc = os.environ.get("TASKRC")
    if data_dir:
        cmd.append(f"rc.data.location={data_dir}")
    if taskrc:
        cmd.insert(1, f"rc:{taskrc}")
    cmd.extend(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        raise TaskError("Taskwarrior binary not found. Is 'task' installed?")
    except subprocess.TimeoutExpired:
        raise TaskError("Taskwarrior command timed out.")


def _parse_tasks(json_str: str) -> list[Task]:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return []
    tasks = []
    for item in data:
        tasks.append(
            Task(
                uuid=item.get("uuid", ""),
                id=item.get("id", 0),
                description=item.get("description", ""),
                status=item.get("status", "pending"),
                project=item.get("project", ""),
                tags=item.get("tags", []),
                priority=item.get("priority", ""),
                due=item.get("due", ""),
                entry=item.get("entry", ""),
                modified=item.get("modified", ""),
                urgency=item.get("urgency", 0.0),
                start=item.get("start", ""),
                end=item.get("end", ""),
                recur=item.get("recur", ""),
                annotations=item.get("annotations", []),
            )
        )
    return tasks


def get_tasks(filter_str: str = "") -> list[Task]:
    args = []
    if filter_str:
        args.extend(filter_str.split())
    args.append("export")
    try:
        result = _run_task(*args)
    except TaskError:
        return []
    if result.returncode != 0:
        return []
    tasks = _parse_tasks(result.stdout)
    tasks.sort(key=lambda t: t.urgency, reverse=True)
    return tasks


def get_pending_tasks(filter_str: str = "") -> list[Task]:
    filt = "status:pending"
    if filter_str:
        filt += f" {filter_str}"
    return get_tasks(filt)


def get_completed_tasks(limit: int = 20) -> list[Task]:
    tasks = get_tasks("status:completed")
    tasks.sort(key=lambda t: t.end, reverse=True)
    return tasks[:limit]


def get_task_by_uuid(uuid: str) -> Task | None:
    tasks = get_tasks(uuid)
    return tasks[0] if tasks else None


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


def add_task(
    description: str,
    project: str = "",
    tags: list[str] | None = None,
    priority: str = "",
    due: str = "",
) -> bool:
    args = ["add", description]
    if project:
        args.append(f"project:{project}")
    if tags:
        for tag in tags:
            t = tag if tag.startswith("+") else f"+{tag}"
            args.append(t)
    if priority:
        args.append(f"priority:{priority}")
    if due:
        args.append(f"due:{due}")
    try:
        result = _run_task(*args)
    except TaskError:
        return False
    return result.returncode == 0


def complete_task(uuid: str) -> bool:
    try:
        result = _run_task(uuid, "done")
    except TaskError:
        return False
    return result.returncode == 0


def delete_task(uuid: str) -> bool:
    try:
        result = _run_task(uuid, "delete")
    except TaskError:
        return False
    return result.returncode == 0


def start_task(uuid: str) -> bool:
    try:
        result = _run_task(uuid, "start")
    except TaskError:
        return False
    return result.returncode == 0


def stop_task(uuid: str) -> bool:
    try:
        result = _run_task(uuid, "stop")
    except TaskError:
        return False
    return result.returncode == 0
