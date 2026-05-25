from fastapi import APIRouter

from app.api.routes import agents, chat, documents, evals, health, tickets

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(tickets.router, tags=["tickets"])
api_router.include_router(evals.router, tags=["evals"])
