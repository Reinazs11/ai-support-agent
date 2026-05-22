# AGENTS.md

## Objetivo do projeto

Construir um AI Support & Knowledge Agent production-style para estudos de AI
Engineering. O projeto deve evoluir em fatias verticais, sempre preservando
testabilidade, contratos explicitos e documentacao curta.

## Regras de trabalho

- Use Python 3.12.10.
- Prefira FastAPI, Pydantic v2, SQLAlchemy 2.x, Qdrant, OpenAI SDK e LangGraph.
- Nao acople logica de dominio diretamente as rotas HTTP.
- Mantenha integracoes externas atras de servicos ou interfaces pequenas.
- Para cada etapa, atualize documentacao e testes relevantes.
- Nunca registre chaves, prompts sensiveis ou conteudo completo de documentos nos logs.
- Retorne fontes apenas quando elas vierem do retrieval.

## Comandos esperados

```powershell
python -m compileall app scripts tests
pytest
ruff check .
mypy app
```
