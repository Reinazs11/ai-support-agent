import argparse
import sys

from openai import OpenAI, OpenAIError

from app.core.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check local OpenAI API configuration without printing secrets."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the OpenAI models API to verify the configured key and model access.",
    )
    args = parser.parse_args()

    settings = get_settings()
    shared_key_configured = bool(settings.openai_api_key)
    embedding_key_configured = bool(settings.embedding_api_key or settings.openai_api_key)
    chat_key_configured = bool(settings.chat_api_key or settings.openai_api_key)
    embedding_model = settings.embedding_model or settings.openai_embedding_model
    chat_model = settings.chat_model or settings.openai_chat_model

    print("OpenAI configuration")
    print(f"- shared OPENAI_API_KEY configured: {shared_key_configured}")
    print(f"- embedding provider: {settings.embedding_provider}")
    print(f"- embedding key configured: {embedding_key_configured}")
    print(f"- embedding model: {embedding_model}")
    print(f"- chat provider: {settings.chat_provider}")
    print(f"- chat key configured: {chat_key_configured}")
    print(f"- chat model: {chat_model}")

    missing = []
    if settings.embedding_provider == "openai" and not embedding_key_configured:
        missing.append("OPENAI_API_KEY or EMBEDDING_API_KEY")
    if settings.chat_provider == "openai" and not chat_key_configured:
        missing.append("OPENAI_API_KEY or CHAT_API_KEY")

    if missing:
        print(f"Missing required key setting(s): {', '.join(missing)}")
        return 1

    if args.live:
        api_key = settings.chat_api_key or settings.embedding_api_key or settings.openai_api_key
        client = OpenAI(api_key=api_key)
        for model in sorted({embedding_model, chat_model}):
            try:
                client.models.retrieve(model)
            except OpenAIError as exc:
                print(f"Live check failed for {model}: {type(exc).__name__}")
                return 1
        print("Live OpenAI model access check passed.")
    else:
        print("Local configuration check passed. Use --live to verify API access.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
