from fastapi.testclient import TestClient

from app.main import create_app


def test_health_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dependencies" in body
