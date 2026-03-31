"""Flask web application for TaskWeb."""

import hmac
import logging
import os
import re
from datetime import datetime, timezone
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from taskweb import __commit__, __version__
from taskweb.tasks import (
    DatabaseUnavailableError,
    add_task,
    complete_task,
    delete_task,
    derive_from_tasks,
    edit_task,
    get_completed_tasks,
    get_deleted_tasks,
    get_pending_tasks,
    get_task_by_uuid,
)

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    env_key = os.environ.get("TASKWEB_SECRET_KEY")
    if env_key:
        app.secret_key = env_key.encode()
    else:
        app.secret_key = os.urandom(32)

    @app.template_filter("format_timestamp")
    def format_timestamp(ts: str) -> str:
        """Convert a Unix epoch string to 'YYYY-MM-DD HH:MM' in UTC."""
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            return ts

    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    def _validate_uuid(uuid: str) -> bool:
        return bool(uuid_re.match(uuid))

    def _generate_csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = os.urandom(16).hex()
        return session["_csrf_token"]

    app.jinja_env.globals["csrf_token"] = _generate_csrf_token
    app.jinja_env.globals["version"] = __version__
    app.jinja_env.globals["commit"] = __commit__

    @app.before_request
    def _check_csrf():
        if request.method == "POST" and not app.config.get("TESTING"):
            token = request.form.get("_csrf_token", "")
            expected = session.get("_csrf_token", "")
            if not token or not expected or not hmac.compare_digest(token, expected):
                abort(403)

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
        all_pending = all_tasks if not filter_str.strip() else get_pending_tasks()
        derived = derive_from_tasks(all_pending)
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
        total = len(all_tasks)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        tasks = all_tasks[(page - 1) * PER_PAGE : page * PER_PAGE]
        return render_template(
            "completed.html",
            tasks=tasks,
            counts={"completed": total},
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
        if not _validate_uuid(uuid):
            abort(404)
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
        if priority and priority not in ("H", "M", "L"):
            priority = ""
        due = request.form.get("due", "").strip()

        if add_task(description, project=project, tags=tags, priority=priority, due=due):
            flash("Task added.", "success")
        else:
            flash("Failed to add task.", "error")
        return redirect(url_for("index"))

    @app.route("/task/<uuid>/edit", methods=["GET", "POST"])
    def edit(uuid):
        if not _validate_uuid(uuid):
            abort(404)
        task = get_task_by_uuid(uuid)
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for("index"))

        if request.method == "GET":
            return render_template("task_edit.html", task=task)

        description = request.form.get("description", "").strip()
        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("edit", uuid=uuid))

        project = request.form.get("project", "").strip()
        tags_str = request.form.get("tags", "").strip()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        priority = request.form.get("priority", "").strip()
        if priority and priority not in ("H", "M", "L"):
            priority = ""
        due = request.form.get("due", "").strip()
        recur = request.form.get("recur", "").strip()
        annotation = request.form.get("annotation", "").strip()

        if edit_task(
            uuid,
            description=description,
            project=project,
            tags=tags,
            priority=priority,
            due=due,
            recur=recur,
            annotation=annotation,
        ):
            flash("Task updated.", "success")
        else:
            flash("Failed to update task.", "error")
        return redirect(url_for("task_detail", uuid=uuid))

    @app.route("/task/<uuid>/done", methods=["POST"])
    def done(uuid):
        if not _validate_uuid(uuid):
            abort(404)
        if complete_task(uuid):
            flash("Task completed.", "success")
        else:
            flash("Failed to complete task.", "error")
        return redirect(url_for("index"))

    @app.route("/task/<uuid>/delete", methods=["POST"])
    def delete(uuid):
        if not _validate_uuid(uuid):
            abort(404)
        if delete_task(uuid):
            flash("Task deleted.", "success")
        else:
            flash("Failed to delete task.", "error")
        return redirect(url_for("index"))

    @app.errorhandler(DatabaseUnavailableError)
    def db_unavailable(e):
        return render_template("db_missing.html", message=str(e)), 503

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error: %s", e)
        return render_template("error.html"), 500

    return app
