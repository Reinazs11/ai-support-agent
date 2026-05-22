from fastapi import APIRouter

from app.rag.schemas import ChatRequest, ChatResponse
from app.rag.service import RagService

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await RagService().answer(request)
