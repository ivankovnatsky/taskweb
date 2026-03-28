"""Flask web application for TaskWeb."""

import os

from flask import Flask, flash, redirect, render_template, request, url_for

from taskweb.tasks import (
    add_task,
    complete_task,
    delete_task,
    get_completed_tasks,
    get_pending_tasks,
    get_projects,
    get_tags,
    get_task_count,
    start_task,
    stop_task,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = os.environ.get("TASKWEB_SECRET_KEY", "taskweb-dev-key")

    @app.route("/")
    def index():
        project_filter = request.args.get("project", "")
        tag_filter = request.args.get("tag", "")

        filter_str = ""
        if project_filter:
            filter_str += f"project:{project_filter} "
        if tag_filter:
            filter_str += f"+{tag_filter} "

        tasks = get_pending_tasks(filter_str.strip())
        projects = get_projects()
        tags = get_tags()
        counts = get_task_count()

        return render_template(
            "index.html",
            tasks=tasks,
            projects=projects,
            tags=tags,
            counts=counts,
            current_project=project_filter,
            current_tag=tag_filter,
        )

    @app.route("/completed")
    def completed():
        tasks = get_completed_tasks()
        counts = get_task_count()
        return render_template("completed.html", tasks=tasks, counts=counts)

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

    @app.route("/task/<int:task_id>/done", methods=["POST"])
    def done(task_id):
        if complete_task(task_id):
            flash(f"Task {task_id} completed.", "success")
        else:
            flash(f"Failed to complete task {task_id}.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.route("/task/<int:task_id>/delete", methods=["POST"])
    def delete(task_id):
        if delete_task(task_id):
            flash(f"Task {task_id} deleted.", "success")
        else:
            flash(f"Failed to delete task {task_id}.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.route("/task/<int:task_id>/start", methods=["POST"])
    def start(task_id):
        if start_task(task_id):
            flash(f"Task {task_id} started.", "success")
        else:
            flash(f"Failed to start task {task_id}.", "error")
        return redirect(request.referrer or url_for("index"))

    @app.route("/task/<int:task_id>/stop", methods=["POST"])
    def stop(task_id):
        if stop_task(task_id):
            flash(f"Task {task_id} stopped.", "success")
        else:
            flash(f"Failed to stop task {task_id}.", "error")
        return redirect(request.referrer or url_for("index"))

    return app
