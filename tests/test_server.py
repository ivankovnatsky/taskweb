"""Tests for the Flask server."""

from unittest.mock import patch


@patch("taskweb.server.get_task_count", return_value={"pending": 0, "completed": 0, "overdue": 0})
@patch("taskweb.server.get_tags", return_value=[])
@patch("taskweb.server.get_projects", return_value=[])
@patch("taskweb.server.get_pending_tasks", return_value=[])
def test_index_empty(mock_tasks, mock_projects, mock_tags, mock_counts, client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"No pending tasks" in response.data


@patch("taskweb.server.get_task_count", return_value={"pending": 1, "completed": 0, "overdue": 0})
@patch("taskweb.server.get_tags", return_value=["tag1"])
@patch("taskweb.server.get_projects", return_value=["proj1"])
@patch("taskweb.server.get_pending_tasks")
def test_index_with_tasks(mock_tasks, mock_projects, mock_tags, mock_counts, client):
    from taskweb.tasks import Task

    mock_tasks.return_value = [
        Task(
            uuid="1",
            id=1,
            description="Test task",
            project="proj1",
            tags=["tag1"],
            urgency=5.0,
            entry="20260301T000000Z",
        ),
    ]
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test task" in response.data
    assert b"proj1" in response.data


@patch("taskweb.server.get_task_count", return_value={"pending": 0, "completed": 0, "overdue": 0})
@patch("taskweb.server.get_completed_tasks", return_value=[])
def test_completed_empty(mock_tasks, mock_counts, client):
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
        "New task", project="test", tags=["a", "b"], priority="H", due="2026-04-01"
    )


def test_add_task_empty_description(client):
    response = client.post("/add", data={"description": ""})
    assert response.status_code == 302


@patch("taskweb.server.complete_task", return_value=True)
def test_done(mock_done, client):
    response = client.post("/task/1/done")
    assert response.status_code == 302
    mock_done.assert_called_once_with(1)


@patch("taskweb.server.delete_task", return_value=True)
def test_delete(mock_delete, client):
    response = client.post("/task/1/delete")
    assert response.status_code == 302
    mock_delete.assert_called_once_with(1)


@patch("taskweb.server.start_task", return_value=True)
def test_start(mock_start, client):
    response = client.post("/task/1/start")
    assert response.status_code == 302
    mock_start.assert_called_once_with(1)


@patch("taskweb.server.stop_task", return_value=True)
def test_stop(mock_stop, client):
    response = client.post("/task/1/stop")
    assert response.status_code == 302
    mock_stop.assert_called_once_with(1)


@patch("taskweb.server.get_task_count", return_value={"pending": 2, "completed": 0, "overdue": 0})
@patch("taskweb.server.get_tags", return_value=[])
@patch("taskweb.server.get_projects", return_value=["infra"])
@patch("taskweb.server.get_pending_tasks", return_value=[])
def test_filter_by_project(mock_tasks, mock_projects, mock_tags, mock_counts, client):
    response = client.get("/?project=infra")
    assert response.status_code == 200
    mock_tasks.assert_called_once_with("project:infra")


@patch("taskweb.server.get_task_count", return_value={"pending": 2, "completed": 0, "overdue": 0})
@patch("taskweb.server.get_tags", return_value=["next"])
@patch("taskweb.server.get_projects", return_value=[])
@patch("taskweb.server.get_pending_tasks", return_value=[])
def test_filter_by_tag(mock_tasks, mock_projects, mock_tags, mock_counts, client):
    response = client.get("/?tag=next")
    assert response.status_code == 200
    mock_tasks.assert_called_once_with("+next")
