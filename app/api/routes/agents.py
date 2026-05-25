from fastapi import APIRouter

from app.agents.schemas import AgentRequest, AgentResponse
from app.agents.service import AgentWorkflowService

router = APIRouter()


@router.post("/agent/respond", response_model=AgentResponse)
async def respond(request: AgentRequest) -> AgentResponse:
    return await AgentWorkflowService().run(request)
