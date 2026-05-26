import sys

from scripts import smoke_live_n8n


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise smoke_live_n8n.httpx.HTTPStatusError(
                "error",
                request=smoke_live_n8n.httpx.Request("GET", "http://test"),
                response=smoke_live_n8n.httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, *, health_payload: dict, agent_payload: dict) -> None:
        self.health_payload = health_payload
        self.agent_payload = agent_payload
        self.posts: list[dict] = []

    def get(self, path: str) -> FakeResponse:
        assert path == "/health"
        return FakeResponse(self.health_payload)

    def post(self, path: str, json: dict) -> FakeResponse:
        assert path == "/agent/respond"
        self.posts.append(json)
        return FakeResponse(self.agent_payload)


def test_live_n8n_smoke_refuses_when_health_is_not_live(monkeypatch, capsys) -> None:
    fake_client = FakeClient(
        health_payload={"dependencies": {"n8n": "simulated"}},
        agent_payload={},
    )
    monkeypatch.setattr(smoke_live_n8n.httpx, "Client", lambda **kwargs: fake_client)
    monkeypatch.setattr(sys, "argv", ["smoke_live_n8n"])

    exit_code = smoke_live_n8n.main()

    assert exit_code == 1
    assert fake_client.posts == []
    assert "does not report n8n as live" in capsys.readouterr().out


def test_live_n8n_smoke_passes_when_webhook_completes(monkeypatch, capsys) -> None:
    fake_client = FakeClient(
        health_payload={"dependencies": {"n8n": "live"}},
        agent_payload={
            "route": "classify_ticket",
            "ticket": {
                "id": "ticket-1",
                "category": "billing",
                "priority": "normal",
            },
            "actions": [
                {"name": "notify_n8n_webhook", "status": "completed"},
            ],
        },
    )
    monkeypatch.setattr(smoke_live_n8n.httpx, "Client", lambda **kwargs: fake_client)
    monkeypatch.setattr(sys, "argv", ["smoke_live_n8n"])

    exit_code = smoke_live_n8n.main()

    assert exit_code == 0
    assert fake_client.posts == [
        {
            "message": smoke_live_n8n.DEFAULT_MESSAGE,
            "mode": "ticket",
            "customer_tier": "standard",
        }
    ]
    assert "Live n8n smoke test passed." in capsys.readouterr().out


def test_live_n8n_smoke_fails_when_webhook_does_not_complete(monkeypatch) -> None:
    fake_client = FakeClient(
        health_payload={"dependencies": {"n8n": "live"}},
        agent_payload={
            "actions": [
                {"name": "notify_n8n_webhook", "status": "failed"},
            ],
        },
    )
    monkeypatch.setattr(smoke_live_n8n.httpx, "Client", lambda **kwargs: fake_client)
    monkeypatch.setattr(sys, "argv", ["smoke_live_n8n"])

    exit_code = smoke_live_n8n.main()

    assert exit_code == 1
