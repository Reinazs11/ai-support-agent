# Plano De Estudo Do Projeto

Este plano foi feito para transformar o projeto em material de dominio tecnico,
nao apenas em uma peca de portfolio. O foco e sair de "eu entendo por que isso
existe" para "eu consigo explicar, debugar, alterar e defender esse codigo em
uma entrevista".

Use este documento como trilha pratica. O objetivo nao e decorar todos os
arquivos, mas entender os contratos, os fluxos, as decisoes e os pontos fracos
do sistema.

## Como Usar

Trate cada modulo como um ciclo:

1. Leia os arquivos indicados.
2. Desenhe o fluxo com suas proprias palavras.
3. Rode o comportamento localmente quando fizer sentido.
4. Quebre algo de proposito em ambiente local.
5. Explique o erro, a causa e a correcao.
6. Escreva uma nota curta do que aprendeu.

Ritmo sugerido:

- Plano curto: 3 a 4 semanas, 1 a 2 horas por dia.
- Plano completo: 6 a 8 semanas, 1 a 2 horas por dia.
- Plano profundo: 10 a 12 semanas, incluindo pequenos refactors, testes extras
  e simulacoes de entrevista.

Regra principal: nao avance apenas porque leu. Avance quando conseguir explicar
e reproduzir.

## Resultado Esperado

Ao final, voce deve conseguir:

- explicar a arquitetura ponta a ponta;
- justificar as escolhas de FastAPI, PostgreSQL, Qdrant, LangGraph e Langfuse;
- ler e alterar codigo Python/FastAPI com seguranca;
- entender onde entram Pydantic, SQLAlchemy, Alembic, pytest, Ruff e Docker;
- explicar os fluxos de ingestao, RAG, agentes, avaliacao e observabilidade;
- demonstrar o projeto em uma entrevista sem depender de respostas prontas;
- falar honestamente sobre limitacoes e proximos passos de producao.

## Modulo 0: Baseline Do Projeto

Objetivo: entender o que o projeto e, o que ele nao e e qual problema resolve.

Leia:

- `README.md`
- `docs/implementation-plan.md`
- `docs/architecture.md`
- `docs/known-limitations.md`
- `docs/final-checklist.md`

Perguntas que voce precisa responder:

- Qual problema o sistema resolve?
- O que significa "production-style" neste projeto?
- O que ja esta implementado para demo local?
- O que ainda falta para producao real?
- Quais riscos existem se alguem vender isso como SaaS pronto?

Exercicios:

- Faca um resumo de 2 minutos do projeto.
- Faca um resumo de 30 segundos do projeto.
- Faca uma lista com 5 decisoes tecnicas que voce defenderia em entrevista.
- Faca uma lista com 5 limitacoes que voce admitiria sem tentar maquiar.

Criterio de dominio:

- Voce consegue explicar o projeto sem citar nomes de bibliotecas como se isso
  fosse a explicacao. Exemplo ruim: "usa Qdrant e LangGraph". Exemplo bom:
  "usa Qdrant para busca semantica dos chunks e LangGraph para deixar o fluxo
  de ticket explicito, rastreavel e testavel".

## Modulo 1: Arquitetura E Separacao De Responsabilidades

Objetivo: entender por que o projeto e dividido em pacotes e quais fronteiras
existem entre API, servicos, banco, RAG, agentes e observabilidade.

Leia:

- `app/main.py`
- `app/api/router.py`
- `app/api/routes/*.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/db/models.py`
- `docs/api-contracts.md`

Mapa mental esperado:

- `api`: recebe HTTP, valida contrato e chama servicos.
- `core`: configuracoes, logging e objetos compartilhados.
- `db`: modelos, sessao e migracoes.
- `documents`: upload, parsing, chunking e ingestao.
- `rag`: embeddings, busca vetorial, prompt, resposta e fontes.
- `agents`: roteamento, workflow, acoes controladas e n8n.
- `evals`: datasets e validacao de comportamento.
- `observability`: logs, tracing e custo/latencia.

Exercicios:

- Desenhe o fluxo de `POST /documents`.
- Desenhe o fluxo de `POST /ingest/{document_id}`.
- Desenhe o fluxo de `POST /chat`.
- Desenhe o fluxo de `POST /agent/respond`.
- Explique por que rotas HTTP nao deveriam conter toda a logica de negocio.

Criterio de dominio:

- Voce consegue abrir qualquer rota e dizer rapidamente qual servico ela chama,
  qual schema valida a entrada e qual resposta e esperada.

## Modulo 2: Python Moderno No Projeto

Objetivo: consolidar Python aplicado, nao Python abstrato.

Leia:

- `pyproject.toml`
- `app/core/config.py`
- `app/documents/service.py`
- `app/rag/service.py`
- `app/agents/routing.py`
- `tests/conftest.py`

Conceitos para estudar:

- type hints;
- `dataclass`;
- `Protocol`;
- `Literal`;
- exceptions customizadas;
- async/await;
- context managers;
- dependency injection simples;
- imports e organizacao de pacotes;
- diferenca entre funcao pura, servico e rota.

Exercicios:

- Explique por que `Settings` usa `BaseSettings`.
- Explique por que `get_settings()` usa `lru_cache`.
- Explique por que alguns servicos recebem dependencias opcionais no
  construtor.
- Pegue uma exception customizada e siga onde ela e lancada e tratada.
- Escolha um teste unitario e explique quais dependencias sao falsas/mocadas.

Criterio de dominio:

- Voce consegue ler um arquivo Python do projeto e identificar fluxo principal,
  dependencias, efeitos colaterais e pontos testaveis.

## Modulo 3: FastAPI, Pydantic E Contratos HTTP

Objetivo: entender como a API mantem contratos explicitos e previsiveis.

Leia:

- `app/api/routes/health.py`
- `app/api/routes/documents.py`
- `app/api/routes/chat.py`
- `app/api/routes/agents.py`
- `app/documents/schemas.py`
- `app/rag/schemas.py`
- `app/agents/schemas.py`
- `tests/integration/test_*_contract.py`

Conceitos para estudar:

- request/response models;
- validacao com Pydantic v2;
- status codes;
- erros controlados;
- diferenca entre contrato de API e implementacao interna;
- por que `/evals/run` retorna `501 Not Implemented`.

Exercicios:

- Rode a API e chame `/health`.
- Chame `/chat` com provedores desabilitados e explique o status retornado.
- Chame `/evals/run` e explique por que 501 e melhor que fingir uma feature.
- Adicione mentalmente um campo novo em `ChatResponse` e liste quais testes
  poderiam quebrar.

Criterio de dominio:

- Voce consegue explicar cada campo importante de `/chat` e `/agent/respond`,
  incluindo `retrieval_status`, `sources`, `usage`, `actions` e `router`.

## Modulo 4: Banco, SQLAlchemy E Alembic

Objetivo: entender persistencia como fonte de verdade operacional.

Leia:

- `app/db/models.py`
- `app/db/session.py`
- `migrations/env.py`
- `migrations/versions/0001_initial_schema.py`
- `migrations/versions/0002_add_document_storage_metadata.py`
- `tests/integration/test_persistence_models.py`
- `tests/integration/test_document_service.py`

Conceitos para estudar:

- modelos SQLAlchemy;
- relacionamentos;
- sessao e commit;
- migrations;
- diferenca entre dados relacionais e vetores;
- por que PostgreSQL e Qdrant cumprem papeis diferentes.

Exercicios:

- Explique quais dados ficam em PostgreSQL.
- Explique quais dados ficam em Qdrant.
- Explique por que `qdrant_point_id` so deve ser salvo apos indexacao bem
  sucedida.
- Simule mentalmente uma falha de Qdrant durante ingestao e diga qual estado o
  documento deveria assumir.
- Leia uma migration e explique o que mudaria no banco.

Criterio de dominio:

- Voce consegue explicar por que PostgreSQL e fonte de verdade de metadados e
  Qdrant e indice semantico, nao banco principal da aplicacao.

## Modulo 5: Ingestao, Parsing E Chunking

Objetivo: entender como documentos viram unidades recuperaveis.

Leia:

- `app/documents/service.py`
- `app/documents/parsers.py`
- `app/documents/chunking.py`
- `app/documents/schemas.py`
- `tests/unit/test_document_parsers.py`
- `tests/unit/test_chunking.py`
- `tests/integration/test_document_service.py`

Fluxo esperado:

1. Upload registra arquivo local e metadados.
2. Ingestao carrega arquivo.
3. Parser extrai texto.
4. Chunker divide texto em partes.
5. Chunks sao persistidos.
6. Embeddings sao gerados quando provider esta configurado.
7. Vetores sao indexados no Qdrant.

Exercicios:

- Explique `chunk_size` e `chunk_overlap`.
- Rode um exemplo pequeno de chunking e veja como o texto e dividido.
- Explique o que acontece quando um documento nao gera chunks.
- Explique o que acontece quando embeddings falham.
- Liste quais tipos de arquivo sao suportados e quais riscos existem em cada um.

Criterio de dominio:

- Voce consegue explicar por que chunking ruim prejudica retrieval, resposta,
  avaliacao e custo.

## Modulo 6: Embeddings E Qdrant

Objetivo: entender busca vetorial alem do nome da ferramenta.

Leia:

- `app/rag/embeddings.py`
- `app/rag/vector_store.py`
- `tests/unit/test_embeddings.py`
- `tests/unit/test_vector_store.py`
- `.env.example`

Conceitos para estudar:

- embeddings como representacao numerica de texto;
- tamanho do vetor;
- collection;
- payload;
- top-k;
- score;
- filtros por `document_id`;
- diferenca entre erro de configuracao e erro de provider.

Exercicios:

- Explique por que `qdrant_vector_size` precisa bater com o modelo de embedding.
- Explique o payload salvo em cada ponto do Qdrant.
- Explique como `document_ids` limita a busca.
- Rode os testes de vector store e explique por que eles usam Qdrant em memoria.
- Descreva o que aconteceria se trocasse o modelo de embedding sem recriar os
  vetores.

Criterio de dominio:

- Voce consegue explicar retrieval como uma cadeia concreta: pergunta -> embedding
  da pergunta -> busca top-k -> chunks recuperados -> contexto limitado.

## Modulo 7: RAG E Geracao De Resposta

Objetivo: dominar o coracao tecnico do projeto.

Leia:

- `app/rag/service.py`
- `app/rag/chat_models.py`
- `app/rag/schemas.py`
- `tests/unit/test_rag_service.py`
- `tests/unit/test_chat_models.py`
- `docs/responsible-ai-safety.md`

Conceitos para estudar:

- grounded answers;
- prompt baseado apenas em chunks recuperados;
- fontes e citacoes;
- fallback por contexto insuficiente;
- status de retrieval;
- limitacao de contexto por caracteres;
- token usage;
- custo estimado;
- provider failure;
- diferenca entre retrieval e generation.

Exercicios:

- Para cada `retrieval_status`, ache o ponto exato no codigo em que ele e
  retornado.
- Explique por que `INSUFFICIENT_CONTEXT_ANSWER` e uma constante.
- Explique por que fontes retornadas refletem o contexto limitado, nao todo
  resultado bruto do Qdrant.
- Altere localmente `RAG_CONTEXT_MAX_CHARS` e observe o impacto.
- Pegue um teste de falha de geracao e explique o comportamento esperado.

Criterio de dominio:

- Voce consegue explicar uma resposta ruim usando causas concretas: parsing,
  chunking, embedding, top-k, filtro, contexto, prompt, modelo, fallback ou
  avaliacao.

## Modulo 8: Agentes, LangGraph E Acoes Controladas

Objetivo: entender o workflow sem cair na fantasia de "agente autonomo".

Leia:

- `app/agents/service.py`
- `app/agents/state.py`
- `app/agents/routing.py`
- `app/agents/webhooks.py`
- `app/tickets/classifier.py`
- `tests/unit/test_agent_workflow.py`
- `tests/unit/test_agent_routing.py`
- `tests/unit/test_webhook_simulation.py`

Conceitos para estudar:

- state machine;
- nos e edges do LangGraph;
- deterministic routing;
- LLM routing opt-in;
- fallback para roteador deterministico;
- acoes simuladas;
- human approval;
- n8n como boundary, nao automacao livre;
- logs sem conteudo sensivel.

Exercicios:

- Desenhe o grafo do workflow.
- Explique quando a rota e `answer`.
- Explique quando a rota e `classify_ticket`.
- Explique por que email nunca e enviado automaticamente.
- Explique quais condicoes permitem n8n live.
- Explique por que o roteador LLM nao e default.

Criterio de dominio:

- Voce consegue defender que o projeto tem workflows controlados, nao automacao
  irresponsavel.

## Modulo 9: Observabilidade, Logs, Langfuse E Seguranca De Dados

Objetivo: entender como medir sem vazar dados sensiveis.

Leia:

- `app/core/logging.py`
- `app/observability/tracing.py`
- `scripts/smoke_langfuse.py`
- `tests/unit/test_logging.py`
- `tests/unit/test_tracing.py`
- `tests/unit/test_smoke_langfuse.py`
- `docs/responsible-ai-safety.md`

Conceitos para estudar:

- structured logging;
- spans;
- metadata minimizada;
- token usage;
- cost details;
- latency;
- no-op tracer;
- diferenca entre observabilidade local e observabilidade de producao;
- por que nao logar prompt completo, contexto completo, URL de webhook ou corpo
  de email.

Exercicios:

- Explique o que aparece no Langfuse e o que deliberadamente nao aparece.
- Rode o smoke de Langfuse quando as credenciais estiverem configuradas.
- Compare um span de RAG com um span de agent workflow.
- Liste 5 campos seguros para log e 5 campos perigosos.

Criterio de dominio:

- Voce consegue explicar observabilidade como ferramenta de debug e governanca,
  nao como enfeite de demo.

## Modulo 10: Avaliacao E Regressao

Objetivo: entender como saber se o sistema melhorou ou piorou.

Leia:

- `docs/evaluation-plan.md`
- `scripts/run_eval.py`
- `scripts/run_agent_eval.py`
- `scripts/seed_eval_corpus.py`
- `evals/initial_rag.jsonl`
- `evals/initial_agent_workflow.jsonl`
- `evals/agent_answer_seeded.jsonl`
- `evals/agent_router_llm.jsonl`
- `tests/unit/test_run_eval.py`
- `tests/unit/test_run_agent_eval.py`

Conceitos para estudar:

- dataset;
- expected facts;
- expected sources;
- forbidden terms;
- fallback checks;
- semantic heuristic;
- latency;
- custo;
- guardas contra configuracao errada;
- diferenca entre smoke test, eval deterministica e benchmark robusto.

Exercicios:

- Explique por que a avaliacao CLI existe antes da API `/evals/run`.
- Adicione mentalmente um novo caso de avaliacao e diga quais campos usaria.
- Leia um relatorio gerado em `reports/evals/`.
- Explique quando uma falha e problema do modelo e quando e problema do dataset.
- Explique por que o dataset de LLM-router ainda e pequeno demais para mudar o
  default do projeto.

Criterio de dominio:

- Voce consegue discutir qualidade de RAG sem dizer apenas "a resposta pareceu
  boa".

## Modulo 11: Testes, Qualidade E CI

Objetivo: entender como o projeto evita regressoes.

Leia:

- `tests/unit/*.py`
- `tests/integration/*.py`
- `scripts/dev.ps1`
- `.github/workflows/ci.yml`
- `pyproject.toml`

Comandos principais:

```powershell
.\.venv\Scripts\python.exe -m compileall app scripts tests
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\scripts\dev.ps1 check
```

Conceitos para estudar:

- diferenca entre unit e integration tests;
- fixtures;
- async tests;
- fake services;
- provider disabled para CI;
- por que live tests nao devem rodar por padrao;
- lint;
- compileall;
- Docker build como validacao de empacotamento.

Exercicios:

- Escolha 5 testes e explique qual risco cada um protege.
- Crie localmente um bug simples e veja qual teste falha.
- Explique por que CI desabilita OpenAI e Langfuse.
- Explique por que Docker build no CI e util mesmo sem publicar imagem.

Criterio de dominio:

- Voce consegue dizer o que testaria antes de mexer em chunking, prompt,
  roteamento ou tracing.

## Modulo 12: Docker, Ambiente Local E Operacao

Objetivo: entender como o sistema sobe e quais dependencias precisa.

Leia:

- `docker-compose.yml`
- `docker/Dockerfile`
- `scripts/dev.ps1`
- `.env.example`
- `docs/deployment-readiness.md`
- `docs/demo-guide.md`

Conceitos para estudar:

- infraestrutura local;
- Postgres healthcheck;
- Qdrant local;
- migrations no startup;
- variaveis de ambiente;
- safe defaults;
- diferenca entre demo local e deploy publico.

Exercicios:

- Suba infra com `.\scripts\dev.ps1 infra`.
- Rode migrations com `.\scripts\dev.ps1 migrate`.
- Suba API com `.\scripts\dev.ps1 api`.
- Explique a ordem correta: infra -> migrations -> API -> seed -> eval.
- Explique o que mudaria para deploy publico.

Criterio de dominio:

- Voce consegue diagnosticar se o problema esta no app, banco, Qdrant, env vars,
  API externa ou comando errado.

## Modulo 13: Demo E Entrevista Tecnica

Objetivo: transformar dominio tecnico em comunicacao clara.

Leia:

- `docs/demo-guide.md`
- `docs/final-checklist.md`
- `README.md`
- `docs/known-limitations.md`

Prepare tres versoes:

- Pitch de 30 segundos.
- Explicacao tecnica de 5 minutos.
- Deep dive de 20 minutos com arquitetura, codigo, testes e limitacoes.

Perguntas que voce deve treinar:

- Por que voce usou Qdrant e PostgreSQL?
- Como o sistema evita hallucination?
- Como voce mede qualidade das respostas?
- Como voce controla custo?
- Como voce evita vazar dados em logs e Langfuse?
- Por que o roteador LLM nao e default?
- O que acontece se OpenAI falhar?
- O que acontece se Qdrant falhar?
- Por que `/evals/run` retorna 501?
- O que falta para producao?
- Que parte voce refatoraria primeiro?
- Qual decisao tecnica voce mudaria hoje?

Exercicio final:

- Grave uma explicacao de 10 minutos do projeto.
- Assista e marque onde voce usou termos vagos.
- Regrave explicando com fluxo, arquivo, contrato e trade-off.

Criterio de dominio:

- Voce consegue responder perguntas dificeis sem supervalorizar o projeto e sem
  diminuir seu proprio trabalho.

## Ordem Recomendada De Leitura De Codigo

Use esta ordem se estiver perdido:

1. `README.md`
2. `docs/architecture.md`
3. `app/main.py`
4. `app/api/router.py`
5. `app/api/routes/health.py`
6. `app/core/config.py`
7. `app/db/models.py`
8. `app/documents/service.py`
9. `app/documents/chunking.py`
10. `app/rag/embeddings.py`
11. `app/rag/vector_store.py`
12. `app/rag/chat_models.py`
13. `app/rag/service.py`
14. `app/agents/routing.py`
15. `app/agents/service.py`
16. `app/agents/webhooks.py`
17. `app/observability/tracing.py`
18. `scripts/run_eval.py`
19. `scripts/run_agent_eval.py`
20. `.github/workflows/ci.yml`

## Checkpoints De Dominio

Use estes checkpoints como prova real de aprendizado:

- Checkpoint 1: explicar arquitetura completa sem abrir o codigo.
- Checkpoint 2: abrir uma rota e seguir a chamada ate o banco ou provider.
- Checkpoint 3: explicar todos os `retrieval_status`.
- Checkpoint 4: explicar como um documento vira chunks e vetores.
- Checkpoint 5: explicar como uma pergunta vira resposta com fontes.
- Checkpoint 6: explicar como o agent workflow decide rota e acoes.
- Checkpoint 7: explicar o que e logado e o que nao e logado.
- Checkpoint 8: adicionar um caso de teste simples sem quebrar contratos.
- Checkpoint 9: adicionar um caso de eval simples e interpretar o relatorio.
- Checkpoint 10: fazer uma demo local completa e explicar cada comando.

## Pequenos Desafios Praticos

Faca estes desafios sem pedir para a IA implementar tudo. Use a IA apenas para
revisar sua solucao ou explicar erros.

1. Adicione um teste para um novo caso de `retrieval_status`.
2. Adicione um caso novo em `evals/initial_rag.jsonl`.
3. Melhore uma mensagem de erro sem mudar contrato.
4. Adicione um campo seguro de metadata em um log.
5. Crie um teste que garanta que uma informacao sensivel nao aparece no tracing.
6. Adicione um filtro simples por metadata e documente a limitacao.
7. Explique e depois altere um threshold de avaliacao heuristica.
8. Simule provider disabled e explique a resposta da API.
9. Simule n8n live bloqueado por human approval e explique o guardrail.
10. Rode o CI local equivalente e explique cada etapa.

## Como Estudar Com IA Sem Virar Dependente

Use a IA para:

- pedir explicacoes de codigo que voce ja tentou ler;
- revisar seu raciocinio;
- criar perguntas de entrevista;
- comparar alternativas;
- apontar riscos;
- ajudar a depurar erros especificos.

Evite usar a IA para:

- implementar modulos inteiros sem voce antes desenhar o fluxo;
- aceitar explicacoes sem verificar no codigo;
- escrever respostas de entrevista que voce nao consegue defender;
- pular testes porque "parece certo".

Regra pratica:

- Primeiro tente explicar sozinho.
- Depois peca critica.
- Depois corrija sua explicacao.
- So entao peca ajuda com implementacao.

## Lacunas Atuais Que Voce Deve Fechar

Com base no estado do projeto, estas sao as lacunas mais importantes para voce
como desenvolvedor:

- Python idiomatico: tipos, async, exceptions, protocols e testes.
- FastAPI e Pydantic: contratos e validacao.
- SQLAlchemy/Alembic: persistencia e migrations.
- RAG: retrieval, grounding, fontes, fallback e eval.
- Observabilidade: logs estruturados, tracing e privacidade.
- Test strategy: saber o que testar e em qual camada.
- Debug operacional: distinguir erro de ambiente, provider, banco, vetor e API.
- Comunicacao tecnica: explicar trade-offs sem parecer que decorou buzzwords.

## O Que Estudar Depois Para Chegar A Uma Senioridade Forte

Depois de dominar este projeto, avance nestas frentes.

### Backend Engineering Forte

Estude:

- design de APIs;
- autenticacao e autorizacao;
- rate limiting;
- idempotencia;
- transacoes;
- filas e processamento assincrono;
- caching;
- resilencia;
- retries, timeouts e circuit breakers;
- versionamento de contratos;
- migracoes seguras;
- observabilidade em producao.

Pratica recomendada:

- Adicione autenticacao simples ao projeto.
- Adicione rate limit.
- Adicione uma fila para ingestao assincrona.
- Adicione uma tabela de audit trail.
- Crie uma estrategia de retencao de uploads.

### Python Profissional

Estude:

- typing avancado;
- pytest avancado;
- async internals;
- SQLAlchemy profundo;
- Pydantic v2 profundo;
- packaging;
- profiling;
- mypy;
- design de bibliotecas pequenas.

Pratica recomendada:

- Rode mypy e corrija problemas reais aos poucos.
- Refatore uma parte pequena para reduzir acoplamento.
- Escreva testes antes de alterar comportamento.

### AI Engineering

Estude:

- chunking strategies;
- hybrid search;
- reranking;
- query rewriting;
- metadata filters;
- token-aware context windows;
- prompt evaluation;
- LLM-as-judge;
- Ragas ou ferramentas equivalentes;
- dataset design;
- drift e regressao;
- safety e policy enforcement;
- custos e latencia em LLM apps.

Pratica recomendada:

- Adicione token-aware context budgeting.
- Compare top-k simples com reranking.
- Expanda evals com casos negativos.
- Adicione LLM-as-judge controlado.
- Compare dois modelos por custo, latencia e qualidade.

### Distributed Systems E Operacao

Estude:

- Docker alem do basico;
- deploy;
- secret managers;
- health checks profundos;
- logs, metricas e traces;
- filas;
- workers;
- storage;
- backups;
- disaster recovery;
- SLOs e SLIs;
- incident response.

Pratica recomendada:

- Faca deploy privado.
- Configure secrets fora do `.env`.
- Adicione readiness real para Postgres e Qdrant.
- Adicione dashboard de metricas.
- Simule uma falha e escreva um mini postmortem.

### Arquitetura E Lideranca Tecnica

Estude:

- trade-offs arquiteturais;
- documentacao de decisoes;
- revisao de codigo;
- planejamento incremental;
- gestao de risco tecnico;
- priorizacao;
- comunicacao com produto;
- mentoring;
- ownership de producao.

Pratica recomendada:

- Escreva ADRs curtos para 3 decisoes do projeto.
- Faca uma code review do seu proprio projeto como se fosse de outra pessoa.
- Crie um roadmap de producao com custo, risco e impacto.
- Explique o projeto para alguem nao tecnico e depois para alguem senior.

## Criterio Realista De Senioridade

Junior:

- consegue implementar com orientacao;
- entende partes isoladas;
- precisa de ajuda para arquitetura e debug complexo.

Pleno:

- entende fluxos completos;
- entrega features com testes;
- reconhece trade-offs;
- debuga problemas reais;
- comunica limitacoes.

Senior:

- antecipa riscos;
- simplifica arquitetura;
- define contratos estaveis;
- cria estrategia de testes;
- pensa em operacao, seguranca, custo e manutencao;
- orienta outras pessoas;
- sabe dizer "nao" para features que pioram o sistema.

Meta para voce:

- curto prazo: consolidar pleno em Python/backend aplicado;
- medio prazo: pleno forte em AI Engineering;
- longo prazo: senioridade forte combinando backend, operacao, arquitetura,
  avaliacao de LLMs e comunicacao tecnica.

## Definicao De Conclusao

Considere este plano concluido quando voce conseguir:

- fazer a demo sem consultar notas;
- explicar os principais arquivos;
- responder perguntas de falha e limitacao;
- alterar um comportamento pequeno com teste;
- interpretar um relatorio de eval;
- justificar por que algo ainda nao foi implementado;
- dizer com honestidade qual parte do projeto voce domina e qual parte ainda
  esta estudando.

Quando chegar nesse ponto, o projeto deixa de ser apenas um projeto feito com
ajuda de IA e passa a ser um projeto que voce realmente possui tecnicamente.
