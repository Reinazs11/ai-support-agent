from app.agents.routing import (
    _usage_from_openai_response,
    parse_agent_route_response,
)


class FakeOpenAIUsage:
    prompt_tokens = 100
    completion_tokens = 20
    total_tokens = 120


def test_parse_agent_route_response_preserves_usage() -> None:
    usage = _usage_from_openai_response(
        FakeOpenAIUsage(),
        prompt_cost_per_1m_tokens=0.20,
        completion_cost_per_1m_tokens=1.25,
    )

    decision = parse_agent_route_response(
        content='{"route": "classify_ticket", "rationale": "support follow-up"}',
        provider="openai",
        model="gpt-test",
        usage=usage,
    )

    assert decision.route == "classify_ticket"
    assert decision.provider == "openai"
    assert decision.model == "gpt-test"
    assert decision.usage is not None
    assert decision.usage.prompt_tokens == 100
    assert decision.usage.completion_tokens == 20
    assert decision.usage.total_tokens == 120
    assert decision.usage.estimated_cost_usd == 0.000045


def test_router_usage_has_no_cost_when_rates_are_unset() -> None:
    usage = _usage_from_openai_response(
        FakeOpenAIUsage(),
        prompt_cost_per_1m_tokens=0,
        completion_cost_per_1m_tokens=0,
    )

    assert usage is not None
    assert usage.estimated_cost_usd is None
