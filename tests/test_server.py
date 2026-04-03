"""Tests for the Flask server."""

from unittest.mock import patch


@patch(
    "taskweb.server.get_pending_tasks",
    return_value=[],
)
def test_index_empty(mock_tasks, client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"No pending tasks" in response.data


@patch("taskweb.server.get_pending_tasks")
def test_index_with_tasks(mock_tasks, client):
    from taskweb.tasks import Task

    mock_tasks.return_value = [
        Task(
            uuid="abc12345-1234-5678-9abc-def012345678",
            id=1,
            description="Test task",
            project="proj1",
            tags=["tag1"],
            urgency=5.0,
            entry="1740787200",
        ),
    ]
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test task" in response.data
    assert b"proj1" in response.data


@patch("taskweb.server.get_pending_tasks", return_value=[])
@patch("taskweb.server.get_completed_tasks", return_value=[])
def test_completed_empty(mock_completed, mock_pending, client):
    response = client.get("/completed")
    assert response.status_code == 200
    assert b"No completed tasks" in response.data


@patch("taskweb.server.add_task", return_value=True)
def test_add_task(mock_add, client):
    response = client.post(
        "/add",
        data={
            "description": "New task",
            "project": "test",
            "tags": "a,b",
            "priority": "H",
            "due": "2026-04-01",
        },
    )
    assert response.status_code == 302
    mock_add.assert_called_once_with(
        "New task", project="test", tags=["a", "b"], priority="H", due="2026-04-01", due_time=""
    )


def test_add_task_empty_description(client):
    response = client.post("/add", data={"description": ""})
    assert response.status_code == 302


@patch("taskweb.server.complete_task", return_value=True)
def test_done(mock_done, client):
    response = client.post("/task/abc12345-1234-5678-9abc-def012345678/done")
    assert response.status_code == 302
    mock_done.assert_called_once_with("abc12345-1234-5678-9abc-def012345678")


@patch("taskweb.server.delete_task", return_value=True)
def test_delete(mock_delete, client):
    response = client.post("/task/abc12345-1234-5678-9abc-def012345678/delete")
    assert response.status_code == 302
    mock_delete.assert_called_once_with("abc12345-1234-5678-9abc-def012345678")


@patch("taskweb.server.get_pending_tasks", return_value=[])
def test_filter_by_project(mock_tasks, client):
    response = client.get("/?project=infra")
    assert response.status_code == 200
    mock_tasks.assert_any_call("project:infra")
    mock_tasks.assert_any_call()


@patch("taskweb.server.get_pending_tasks", return_value=[])
def test_filter_by_tag(mock_tasks, client):
    response = client.get("/?tag=next")
    assert response.status_code == 200
    mock_tasks.assert_any_call("+next")
    mock_tasks.assert_any_call()


@patch("taskweb.server.get_task_by_uuid")
def test_task_detail(mock_get, client):
    from taskweb.tasks import Task

    mock_get.return_value = Task(
        uuid="abc12345-1234-5678-9abc-def012345678",
        id=1,
        description="Test task",
        project="proj1",
        annotations=[{"entry": "1709251200", "description": "A note"}],
    )
    response = client.get("/task/abc12345-1234-5678-9abc-def012345678")
    assert response.status_code == 200
    assert b"Test task" in response.data
    assert b"A note" in response.data


def test_task_detail_invalid_uuid(client):
    response = client.get("/task/nonexistent")
    assert response.status_code == 404


@patch("taskweb.server.get_task_by_uuid", return_value=None)
def test_task_detail_not_found(mock_get, client):
    response = client.get("/task/abc12345-1234-5678-9abc-000000000000")
    assert response.status_code == 302


def test_csrf_rejects_missing_token():
    """POST without CSRF token is rejected when TESTING is off."""
    from taskweb.server import create_app

    app = create_app()
    # Don't set TESTING = True
    with app.test_client() as c:
        response = c.post("/add", data={"description": "test"})
        assert response.status_code == 403


def test_csrf_rejects_wrong_token():
    """POST with wrong CSRF token is rejected."""
    from taskweb.server import create_app

    app = create_app()
    with app.test_client() as c:
        # Set a session token, then submit a wrong one
        with c.session_transaction() as sess:
            sess["_csrf_token"] = "correct-token"
        response = c.post("/add", data={"description": "test", "_csrf_token": "wrong"})
        assert response.status_code == 403
