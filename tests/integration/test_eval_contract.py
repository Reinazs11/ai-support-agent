from fastapi.testclient import TestClient

from app.main import create_app


def test_eval_run_endpoint_is_explicitly_not_implemented() -> None:
    client = TestClient(create_app())

    response = client.post("/evals/run", json={"dataset_path": "evals/initial_rag.jsonl"})

    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]
    assert "scripts.run_eval" in response.json()["detail"]
