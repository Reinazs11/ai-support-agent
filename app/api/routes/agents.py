from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.schemas import AgentRequest, AgentResponse
from app.agents.service import AgentWorkflowService
from app.db.session import get_db_session

router = APIRouter()


@router.post("/agent/respond", response_model=AgentResponse)
async def respond(
    request: AgentRequest,
    session: Session = Depends(get_db_session),
) -> AgentResponse:
    return await AgentWorkflowService(session=session).run(request)
