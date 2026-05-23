import argparse
import sys

import httpx

DEFAULT_DOCUMENT = (
    "Refund policy:\n"
    "Customers can request a refund within 30 days of purchase. "
    "Refund requests after 30 days should be escalated to support leadership.\n"
)
DEFAULT_QUESTION = "What is the refund window?"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a tiny live RAG smoke test against the local API."
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--max-cost-usd", type=float, default=0.005)
    parser.add_argument("--document-text", default=DEFAULT_DOCUMENT)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=60)

    health = client.get("/health")
    health.raise_for_status()
    openai_status = health.json().get("dependencies", {}).get("openai")
    if openai_status != "configured":
        print("OpenAI is not configured according to /health.")
        return 1

    upload = client.post(
        "/documents",
        files={
            "file": (
                "live-smoke-policy.txt",
                args.document_text.encode("utf-8"),
                "text/plain",
            )
        },
    )
    upload.raise_for_status()
    document_id = upload.json()["document_id"]

    ingest = client.post(f"/ingest/{document_id}")
    ingest.raise_for_status()
    ingest_body = ingest.json()
    if ingest_body.get("vectors_indexed", 0) < 1:
        print(f"Ingest did not index vectors: {ingest_body}")
        return 1

    chat = client.post(
        "/chat",
        json={
            "question": args.question,
            "top_k": 1,
            "document_ids": [document_id],
        },
    )
    chat.raise_for_status()
    chat_body = chat.json()

    usage = chat_body.get("usage") or {}
    estimated_cost = usage.get("estimated_cost_usd")
    if estimated_cost is not None and estimated_cost > args.max_cost_usd:
        print(
            f"Smoke test cost estimate ${estimated_cost} exceeded limit ${args.max_cost_usd}."
        )
        return 1

    if chat_body.get("retrieval_status") not in {"generated", "insufficient_context"}:
        print(f"Unexpected retrieval status: {chat_body.get('retrieval_status')}")
        return 1

    if not chat_body.get("sources"):
        print("Chat response did not include sources.")
        return 1

    print("Live RAG smoke test passed.")
    print(f"- document_id: {document_id}")
    print(f"- ingest status: {ingest_body.get('status')}")
    print(f"- retrieval status: {chat_body.get('retrieval_status')}")
    print(f"- source count: {len(chat_body.get('sources', []))}")
    print(f"- usage: {usage or None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
