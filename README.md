# AI Support & Knowledge Agent

Projeto de estudos production-style para AI Engineer. A aplicacao ingere documentos,
cria embeddings, indexa conteudo em Qdrant, responde perguntas com RAG e fontes,
classifica tickets, executa workflows controlados com agente e mede qualidade,
custo, latencia e traces.

## Stack inicial

- Python 3.12.10
- FastAPI + Pydantic v2
- PostgreSQL + SQLAlchemy + Alembic
- Qdrant para busca vetorial
- OpenAI SDK para LLMs e embeddings
- LangGraph para agente a partir da etapa de workflow
- Langfuse para observabilidade LLM
- Pytest, Ruff e mypy para qualidade

## Desenvolvimento local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
docker compose up -d postgres qdrant
uvicorn app.main:app --reload
```

Healthcheck:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Estado atual

Este scaffold implementa a fundacao do projeto:

- estrutura de pacotes;
- configuracao por ambiente;
- logging estruturado;
- contratos HTTP iniciais;
- endpoints stub para documentos, ingestao, chat, tickets e avaliacao;
- servicos deterministicos pequenos para chunking e classificacao;
- documentacao de arquitetura e plano.

As integracoes reais com OpenAI, PostgreSQL, Qdrant, LangGraph e Langfuse entram nas
proximas etapas descritas em `docs/implementation-plan.md`.
