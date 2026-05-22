from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    ChatMessage,
    ChatSession,
    Document,
    DocumentChunk,
    EvaluationRun,
    Ticket,
)
from app.db.session import create_session_factory


def build_test_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def test_document_and_chunk_metadata_can_be_persisted() -> None:
    session = build_test_session()
    document_id = str(uuid4())
    chunk_id = str(uuid4())

    document = Document(
        id=document_id,
        filename="handbook.md",
        content_type="text/markdown",
    )
    document.chunks.append(
        DocumentChunk(
            id=chunk_id,
            chunk_index=0,
            text="Refunds are available within 30 days.",
            qdrant_point_id="point-1",
        )
    )

    session.add(document)
    session.commit()

    persisted = session.scalars(select(Document).where(Document.id == document_id)).one()

    assert persisted.status == "registered"
    assert persisted.filename == "handbook.md"
    assert len(persisted.chunks) == 1
    assert persisted.chunks[0].qdrant_point_id == "point-1"


def test_ticket_chat_and_evaluation_metadata_can_be_persisted() -> None:
    session = build_test_session()
    chat_session = ChatSession(id=str(uuid4()), user_label="local-test")
    chat_session.messages.append(
        ChatMessage(
            id=str(uuid4()),
            role="user",
            content="How do I reset my password?",
            model=None,
        )
    )
    ticket = Ticket(
        id=str(uuid4()),
        subject="Login error",
        body="Customer cannot access the portal.",
        category="technical_support",
        priority="normal",
    )
    evaluation_run = EvaluationRun(
        id=str(uuid4()),
        dataset_path="evals/questions.yaml",
        status="pending",
    )

    session.add_all([chat_session, ticket, evaluation_run])
    session.commit()

    assert session.scalar(select(ChatSession).where(ChatSession.id == chat_session.id)) is not None
    assert session.scalar(select(Ticket).where(Ticket.id == ticket.id)).status == "open"
    persisted_eval = session.scalar(
        select(EvaluationRun).where(EvaluationRun.id == evaluation_run.id)
    )
    assert persisted_eval is not None
    assert persisted_eval.questions_evaluated == 0
