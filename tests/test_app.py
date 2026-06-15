"""Tests for the Flask application endpoints."""

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    ref = tmp_path / "reference"
    ref.mkdir()
    (ref / "faq.md").write_text(
        "## Hours\n\nThe lab is open Monday to Friday from 9 AM to 5 PM.",
        encoding="utf-8",
    )
    app = create_app(ref)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Lab Chat Bot" in response.data


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["documents"] >= 1


def test_chat_returns_answer(client):
    response = client.post("/api/chat", json={"message": "When is the lab open?"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["found"] is True
    assert "Monday to Friday" in data["reply"]
    assert data["source"] == "faq.md"


def test_chat_requires_message(client):
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_chat_missing_body(client):
    response = client.post("/api/chat", json={})
    assert response.status_code == 400


def test_chat_unknown_topic(client):
    response = client.post("/api/chat", json={"message": "tell me about quantum physics"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["found"] is False
