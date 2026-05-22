from fastapi import APIRouter

from app.tickets.schemas import TicketClassificationRequest, TicketClassificationResponse
from app.tickets.service import TicketService

router = APIRouter()


@router.post("/tickets/classify", response_model=TicketClassificationResponse)
async def classify_ticket(
    request: TicketClassificationRequest,
) -> TicketClassificationResponse:
    return TicketService().classify(request)
