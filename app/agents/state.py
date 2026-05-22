from typing import Literal, TypedDict


class AgentState(TypedDict, total=False):
    user_message: str
    route: Literal["answer", "retrieve", "classify_ticket", "human_escalation"]
    answer: str
    ticket_id: str
