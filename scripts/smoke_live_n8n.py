import argparse
import sys

import httpx

DEFAULT_MESSAGE = "Live n8n smoke test: customer reports a billing invoice issue."


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a controlled live n8n webhook smoke test against the local API."
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--customer-tier", default="standard")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30)
    try:
        health = client.get("/health")
        health.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Could not reach API health endpoint: {type(exc).__name__}")
        return 1

    n8n_status = health.json().get("dependencies", {}).get("n8n")
    if n8n_status != "live":
        print(
            "Refusing to run live n8n smoke test because /health does not report "
            f"n8n as live. Current status: {n8n_status!r}."
        )
        return 1

    try:
        response = client.post(
            "/agent/respond",
            json={
                "message": args.message,
                "mode": "ticket",
                "customer_tier": args.customer_tier,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Agent request failed: {type(exc).__name__}")
        return 1

    body = response.json()
    actions = body.get("actions") or []
    action_statuses = {
        action.get("name"): action.get("status")
        for action in actions
        if isinstance(action, dict)
    }
    webhook_status = action_statuses.get("notify_n8n_webhook")
    if webhook_status != "completed":
        print(f"n8n webhook did not complete. Action statuses: {action_statuses}")
        return 1

    ticket = body.get("ticket") or {}
    print("Live n8n smoke test passed.")
    print(f"- route: {body.get('route')}")
    print(f"- ticket_id: {ticket.get('id')}")
    print(f"- ticket_category: {ticket.get('category')}")
    print(f"- ticket_priority: {ticket.get('priority')}")
    print(f"- notify_n8n_webhook: {webhook_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
