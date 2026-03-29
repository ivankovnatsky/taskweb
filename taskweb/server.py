"""Flask web application for TaskWeb."""

import os
from datetime import datetime, timezone

from flask import Flask, flash, redirect, render_template, request, url_for

from taskweb.tasks import (
    add_task,
    complete_task,
    delete_task,
    derive_from_tasks,
    get_completed_tasks,
    get_deleted_tasks,
    get_pending_tasks,
    get_task_by_uuid,
    start_task,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = os.environ.get("TASKWEB_SECRET_KEY") or os.urandom(32)

    @app.template_filter("format_timestamp")
    def format_timestamp(ts: str) -> str:
        """Convert a Unix epoch string to 'YYYY-MM-DD HH:MM' in UTC."""
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError, OSError):
            return ts

    PER_PAGE = 40

    @app.route("/")
    def index():
        project_filter = request.args.get("project", "")
        tag_filter = request.args.get("tag", "")
        page = max(1, request.args.get("page", 1, type=int))

        filter_str = ""
        if project_filter:
            filter_str += f"project:{project_filter} "
        if tag_filter:
            filter_str += f"+{tag_filter} "

        all_tasks = get_pending_tasks(filter_str.strip())
        derived = derive_from_tasks(all_tasks)
        total = len(all_tasks)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        tasks = all_tasks[(page - 1) * PER_PAGE : page * PER_PAGE]

        return render_template(
            "index.html",
            tasks=tasks,
            projects=derived["projects"],
            tags=derived["tags"],
            counts=derived["counts"],
            current_project=project_filter,
            current_tag=tag_filter,
            page=page,
            total_pages=total_pages,
        )

    @app.route("/completed")
    def completed():
        page = max(1, request.args.get("page", 1, type=int))
        all_tasks = get_completed_tasks()
        pending = get_pending_tasks()
        derived = derive_from_tasks(pending)
        total = len(all_tasks)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        tasks = all_tasks[(page - 1) * PER_PAGE : page * PER_PAGE]
        return render_template(
            "completed.html",
            tasks=tasks,
            counts={**derived["counts"], "completed": total},
            page=page,
            total_pages=total_pages,
        )

    @app.route("/deleted")
    def deleted():
        page = max(1, request.args.get("page", 1, type=int))
        all_tasks = get_deleted_tasks()
        total = len(all_tasks)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        tasks = all_tasks[(page - 1) * PER_PAGE : page * PER_PAGE]
        return render_template(
            "deleted.html",
            tasks=tasks,
            total=total,
            page=page,
            total_pages=total_pages,
        )

    @app.route("/task/<uuid>")
    def task_detail(uuid):
        task = get_task_by_uuid(uuid)
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for("index"))
        return render_template("task_detail.html", task=task)

    @app.route("/add", methods=["POST"])
    def add():
        description = request.form.get("description", "").strip()
        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("index"))

        project = request.form.get("project", "").strip()
        tags_str = request.form.get("tags", "").strip()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        priority = request.form.get("priority", "").strip()
        due = request.form.get("due", "").strip()

        if add_task(description, project=project, tags=tags, priority=priority, due=due):
            flash("Task added.", "success")
        else:
            flash("Failed to add task.", "error")
        return redirect(url_for("index"))

    @app.route("/task/<uuid>/done", methods=["POST"])
    def done(uuid):
        if complete_task(uuid):
            flash("Task completed.", "success")
        else:
            flash("Failed to complete task.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.route("/task/<uuid>/delete", methods=["POST"])
    def delete(uuid):
        if delete_task(uuid):
            flash("Task deleted.", "success")
        else:
            flash("Failed to delete task.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.route("/task/<uuid>/start", methods=["POST"])
    def start(uuid):
        if start_task(uuid):
            flash("Task started.", "success")
        else:
            flash("Failed to start task.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("error.html", error=str(e)), 500

    return app
