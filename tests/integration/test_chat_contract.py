from fastapi.testclient import TestClient

from app.main import create_app


def test_chat_contract_reports_not_configured_without_embeddings() -> None:
    client = TestClient(create_app())

    response = client.post("/chat", json={"question": "What is the refund policy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_status"] == "not_configured"
    assert body["confidence"] == "low"
    assert body["sources"] == []
    assert body["answer"]
