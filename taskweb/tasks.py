"""Interface to Taskwarrior via subprocess."""

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


def _run_task(*args: str) -> subprocess.CompletedProcess:
    cmd = ["task", "rc.confirmation=off", "rc.bulk=0"]
    data_dir = os.environ.get("TASKDATA")
    taskrc = os.environ.get("TASKRC")
    if data_dir:
        cmd.append(f"rc.data.location={data_dir}")
    if taskrc:
        cmd.insert(1, f"rc:{taskrc}")
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


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
    result = _run_task(*args)
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
    result = _run_task(*args)
    return result.returncode == 0


def complete_task(task_id: int) -> bool:
    result = _run_task(str(task_id), "done")
    return result.returncode == 0


def delete_task(task_id: int) -> bool:
    result = _run_task(str(task_id), "delete")
    return result.returncode == 0


def start_task(task_id: int) -> bool:
    result = _run_task(str(task_id), "start")
    return result.returncode == 0


def stop_task(task_id: int) -> bool:
    result = _run_task(str(task_id), "stop")
    return result.returncode == 0


def modify_task(task_id: int, **kwargs: str) -> bool:
    args = [str(task_id), "modify"]
    for key, value in kwargs.items():
        if key == "description":
            args.append(value)
        elif key == "tags":
            for tag in value if isinstance(value, list) else [value]:
                args.append(tag if tag.startswith("+") or tag.startswith("-") else f"+{tag}")
        else:
            args.append(f"{key}:{value}")
    result = _run_task(*args)
    return result.returncode == 0


def get_projects() -> list[str]:
    tasks = get_pending_tasks()
    projects = sorted({t.project for t in tasks if t.project})
    return projects


def get_tags() -> list[str]:
    tasks = get_pending_tasks()
    tags = set()
    for t in tasks:
        tags.update(t.tags)
    return sorted(tags)


def get_task_count() -> dict[str, int]:
    pending = get_pending_tasks()
    completed = get_tasks("status:completed")
    overdue = [t for t in pending if t.is_overdue]
    return {
        "pending": len(pending),
        "completed": len(completed),
        "overdue": len(overdue),
    }
