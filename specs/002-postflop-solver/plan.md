# Implementation Plan: Solver GTO Postflop Heads-Up

**Branch**: `002-postflop-solver` | **Date**: 2026-10-12 (rev. 2: constituição v2.0.0 + clarify
de 2026-10-12) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-postflop-solver/spec.md`

## Summary

Solver de equilíbrio aproximado para spots postflop heads-up (river e turn com a árvore padrão;
flop só com árvores reduzidas que caibam em 4 GiB). O núcleo é um **DCFR vetorizado** (regrets
e estratégias em arrays NumPy indexados por nó × combo, kernels Numba) no pacote independente
`gto_engine`, validado contra Kuhn e Leduc e medido por explotabilidade exata em % do pote.

Uma API FastAPI, de uso pessoal e escutando só em localhost, faz tudo que é pesado como **job
assíncrono** (Princípio V v2.0.0):
- **raia `solve`**: 1 solve por vez, com fila FIFO;
- **raia `aux`**: exportação, importação e limpeza por retenção.

Progresso de todos os jobs por WebSocket. Ao fim do treino, o job grava estratégia, EV e equity
por nó; com isso, a navegação na árvore só lê e agrega (≤ 200 ms). As soluções ficam em
diretórios `.npy` mapeados em memória e são trocadas como `.npz` comprimido. Expiram após 30
dias sem uso, salvo as fixadas. O front React consome a API por um cliente gerado do OpenAPI.
Decisões e números em [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12+ (motor e API), TypeScript 5 (front)

**Primary Dependencies** (justificativa de cada uma, Princípio VII):

| Dependência | Onde | Por quê |
|-------------|------|---------|
| `numpy` | motor (runtime) | arrays de regrets/estratégias e `.npy`/`.npz` (R2, R12) |
| `numba` | motor (runtime) | kernels compilados para os hot loops (R2, Princípio V) |
| `phevaluator` | motor (dev) | oráculo independente do avaliador de mãos (Princípios I e IV) |
| `fastapi` | API | REST + WebSocket + OpenAPI gerado (fonte do cliente tipado) |
| `pydantic` v2 | API | validação e schemas (dependência do FastAPI) |
| `uvicorn` | API | servidor ASGI |
| `websockets` | API | protocolo WebSocket para o `uvicorn` (o extra `[standard]` não é usado, para evitar `uvloop`, `httptools` e `watchfiles`) |
| `sqlalchemy` 2 | API | persistência portável SQLite → PostgreSQL (pedido do usuário) |
| `python-multipart` | API | upload `multipart/form-data` da importação (exigido pelo FastAPI) |
| `httpx` | API (dev) | exigido pelo `TestClient` do FastAPI; os testes da API e do WebSocket são síncronos, sem `pytest-asyncio` |
| `pytest`, `hypothesis`, `pytest-benchmark` | dev | testes, property-based e benchmarks (Princípios IV e V) |
| `ruff`, `mypy` | dev | lint, formatação, banimento de imports no motor (`TID251`) e tipagem estrita |
| React, Vite, TypeScript | front | SPA pedida na stack |
| `openapi-typescript` + `openapi-fetch` | front | cliente tipado gerado do OpenAPI, só tipos + `fetch` fino |
| Vitest, Playwright | front (dev) | testes unitários e E2E |

**Storage**:
- SQLite (SQLAlchemy 2; portável para PostgreSQL) com as tabelas `tree_configs`, `solves` e
  `aux_jobs`.
- Soluções em `$GTO_DATA_DIR/solutions/<sha256>/`, como `.npy` sem compressão (lidos via mmap).
- Exportações em `.npz` comprimido, em `$GTO_DATA_DIR/exports/`.

**Testing**: pytest + hypothesis (motor), testes de equilíbrio Kuhn/Leduc, pytest-benchmark
(regressão relativa no CI + orçamentos absolutos no hardware de referência), testes de contrato
OpenAPI/WebSocket, Vitest e Playwright no front

**Target Platform**: serviço local de uso pessoal (macOS/Linux, nativo ou Docker publicado em
`127.0.0.1`), navegador moderno para o front

**Project Type**: aplicação web: biblioteca de cálculo + API + SPA

**Performance Goals** (research R3/R9/R15, hardware de referência com 8 núcleos e 16 GB):

| Medida | Orçamento |
|--------|-----------|
| River de referência (SC-001) | < 1% do pote em < 30 s |
| Turn com a árvore padrão | < 1% do pote em < 60 s |
| Flop reduzido | < 1% do pote em < 10 min |
| Kuhn | < 1 s |
| Leduc | < 30 s |
| Consulta de nó (leitura e agregação) | ≤ 200 ms no maior flop aceito |
| Parse + validação + `input_hash` + `estimate_tree` (na requisição) | ≤ 200 ms no pior caso (flop padrão, ranges 100%), com benchmark |
| Endpoints que criam jobs | ≤ 200 ms (só validam, estimam e enfileiram), sem contar a transferência do upload em `POST /solutions/import` |
| Progresso via WebSocket | ≥ 1×/s |
| Pausar, parar ou cancelar | < 1 s |

**Constraints**:
- ≤ 4 GiB de pico estimado por solve (`GTO_MAX_SOLVE_MEMORY_BYTES`).
- 1 solve por vez; um solve pausado continua ocupando a raia.
- Nenhum cálculo pesado no ciclo HTTP.
- Nenhum laço Python puro em hot loops.
- Determinismo bit a bit na mesma plataforma.
- Sem autenticação: o serviço escuta só em localhost.
- Retenção de 30 dias sem uso (`GTO_SOLUTION_RETENTION_DAYS`).

**Scale/Scope**: 1 usuário, 1 solve ativo + 1 job auxiliar, árvores até ~500 mil nós de decisão,
soluções de MB (turn) a GB (flop reduzido)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constituição **v2.0.0**.

| Princípio | Como o plano atende | Status |
|-----------|---------------------|--------|
| I. Corretude matemática | O mesmo núcleo DCFR resolve Kuhn (−1/18) e Leduc (≈ −0,0856) com tolerâncias definidas (R7). O avaliador de mãos é validado contra `phevaluator` e de forma exaustiva (feature 001) | ✅ |
| II. Explotabilidade | Best response exata em todo solve, em % do pote (R6). Gates no CI por número fixo de iterações (Kuhn, Leduc, river de referência) | ✅ |
| III. Motor isolado | `gto_engine` sem dependência de web ou banco, proibida via ruff `TID251`. `SolveControl` e `ProgressSink` como Protocol. Testável com pytest puro | ✅ |
| IV. Test-first | Testes de referência, determinismo, ida e volta, estimativa e benchmarks antes dos kernels; testes de contrato antes dos endpoints | ✅ (a cumprir em `tasks.md`) |
| V. Jobs assíncronos, NumPy/Numba, WebSocket, benchmarks | Ver detalhamento abaixo | ✅ |
| VI. Determinismo | DCFR não amostra; seed registrada; `fastmath=False`; sem somas de float entre threads; `.npz` versionado com meta completa; hash canônico da entrada (R12) | ✅ (garantia por plataforma, ver nota) |
| VII. Simplicidade | Um núcleo parametrizado para DCFR, CFR+ e LCFR; sem broker; sem Alembic no MVP; duas raias fixas, sem scheduler genérico | ⚠️ justificativas em Complexity Tracking |
| VIII. pt-BR e notação | UI e `detail` dos erros em pt-BR; rótulos como `"Bet 75% (7,5 bb)"`; ranges na notação da 001 | ✅ |

Detalhamento do Princípio V:
- **Solve**, **exportação**, **importação** e **limpeza** são jobs, e os endpoints respondem
  202. Isso corrige a v1 deste plano, em que a exportação e a importação rodavam na requisição.
- EV e equity são calculados na **finalização do job**. Na v1, a consulta de nó os calculava sob
  demanda, com até 2 s no flop, o que viola o V.
- A consulta de nó virou cálculo leve: tem teto pela profundidade da árvore e benchmark de
  ≤ 200 ms (R15).
- Hot loops em Numba; o Python fica só na orquestração entre blocos (R4).
- Progresso por WebSocket para todos os jobs.
- Orçamentos explícitos e benchmarks automatizados.

Nota (VI): entre arquiteturas diferentes (ARM vs x86) o LLVM pode gerar FMA diferente; a garantia
bit a bit vale para a mesma plataforma. A importação de soluções é sempre idêntica, porque a
estratégia vem do arquivo.

**Re-check pós-design (Phase 1)**: as revisões de contratos e modelo (jobs auxiliares, retenção,
WebSocket genérico) não adicionaram dependências. Nenhuma violação nova. Gate **aprovado**, com
as justificativas abaixo.

## Mudanças em relação à revisão 1 deste plano

1. **Princípio V v2.0.0**:
   - EV e equity passam a ser calculados na finalização do job e gravados (R12, R15).
   - Exportação, importação e limpeza viram jobs da raia `aux` (R4).
   - O WebSocket vira genérico: `/jobs/{job_id}/events`.
2. **Armazenamento**: diretório `.npy` mapeado em memória como formato interno, com `.npz`
   comprimido só para troca. É um desvio do "soluções como `.npz` comprimidos" da stack pedida,
   justificado em R12: um `.npz` comprimido não pode ser lido por fatias em ≤ 200 ms.
3. **Clarify**:
   - uso pessoal, sem login: só localhost (R16);
   - 1 solve por vez, com fila (FR-027, R4);
   - retenção de 30 dias com fixação (FR-028 a FR-030, R14);
   - rake, ICM e multiway fora do escopo;
   - SC-004 confirmado (R3).
4. **Reinício do servidor**: jobs ativos viram `failed` (`servidor_reiniciado`).

Pendência fora desta feature: a spec da **001** ainda descreve cálculo e armazenamento locais no
navegador. Com o Princípio V v2.0.0, a equity range vs range e o Monte Carlo também viram jobs.

## Project Structure

### Documentation (this feature)

```text
specs/002-postflop-solver/
├── plan.md              # este arquivo
├── research.md          # Phase 0 (R1–R16)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── openapi.yaml     # REST /api/v1 (v1.1.0)
│   ├── websocket.md     # eventos de jobs
│   └── engine-api.md    # API pública do gto_engine
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # workspace uv (members: engine, api); ruff + mypy compartilhados
Dockerfile                     # multi-stage: build (uv sync + warm-up Numba) → runtime
.github/workflows/ci.yml       # ruff, mypy, pytest, benchmark relativo, gates de explotabilidade

engine/                        # pacote gto_engine (sem web/DB)
├── pyproject.toml
├── src/gto_engine/
│   ├── cards.py, ranges/, evaluator/, equity/     # feature 001 (reutilizados)
│   ├── game/
│   │   ├── config.py          # TreeConfig, default_tree_config
│   │   ├── builder.py         # build_tree (regras NL, all-in threshold, unificação)
│   │   ├── estimate.py        # estimate_tree: pico de memória + tamanho em disco (R3)
│   │   ├── isomorphism.py     # R5
│   │   └── hashing.py         # input_hash canônico
│   ├── solver/
│   │   ├── kernels.py         # @njit: regret matching, cfv, showdown sweep, DCFR discount
│   │   ├── dcfr.py            # loop em blocos, SolveControl, ProgressSink
│   │   ├── best_response.py   # exploitability (R6)
│   │   └── finalize.py        # estratégia média, EV e equity por nó (@njit, R15)
│   ├── analysis/node_view.py  # leitura + agregação (≤ 200 ms)
│   ├── io/
│   │   ├── solution_dir.py    # .npy sem compressão, mmap
│   │   └── exchange.py        # export_npz / import_npz com progresso
│   ├── toy_games/{kuhn,leduc}.py
│   └── warmup.py
└── tests/
    ├── reference/             # Kuhn, Leduc, river de referência (gates)
    ├── unit/                  # builder, estimate, isomorphism, hashing, io, finalize
    ├── property/              # hypothesis: frequências somam 1, simetria, ida e volta
    ├── benchmarks/            # pytest-benchmark (relativo) + benchmark_ref (absoluto, incl. node_view)
    └── fixtures/              # spots JSON de referência

api/                           # pacote gto_api
├── pyproject.toml
├── src/gto_api/
│   ├── main.py                # app, lifespan (warm-up, raias, reconciliação, agendador de limpeza), /health
│   ├── settings.py            # GTO_DATA_DIR, GTO_MAX_SOLVE_MEMORY_BYTES, GTO_SOLUTION_RETENTION_DAYS,
│   │                          # GTO_MAX_IMPORT_BYTES, host 127.0.0.1, CORS
│   ├── schemas/               # Pydantic v2 ↔ tipos do motor
│   ├── routers/{trees,tree_configs,solves,solutions,aux_jobs,storage}.py
│   ├── ws/job_events.py       # WebSocket /jobs/{job_id}/events (contracts/websocket.md)
│   ├── jobs/
│   │   ├── runner.py          # Protocol JobRunner, JobEvent, raias
│   │   ├── local_process.py   # 2 ProcessPoolExecutor (solve, aux) + Manager (R4)
│   │   └── tasks.py           # funções de job: solve, export, import, cleanup (chamam o motor)
│   ├── db/{models,session}.py
│   └── storage/solutions.py   # caminhos por hash, retenção (R14), LRU de soluções abertas
└── tests/{contract,integration,unit}/

web/
├── src/
│   ├── api/                   # cliente gerado (openapi-typescript) + cliente WebSocket de jobs
│   ├── components/RangeGrid/  # grade 13x13 SVG (compartilhada com a 001)
│   ├── features/solver/       # spot, árvore, fila, progresso, navegador de nós
│   ├── features/solutions/    # lista: tamanho, último uso, expiração, fixar, exportar/importar
│   └── i18n/pt-BR.ts
└── tests/{unit,e2e}/
```

**Structure Decision**: monorepo com workspace `uv` (`engine`, `api`) e `web/` separado. O
`gto_engine` é um pacote próprio e não conhece a API (Princípio III); a API depende do motor só
pela interface de [contracts/engine-api.md](./contracts/engine-api.md). A execução é isolada
pela interface `JobRunner`:

```python
Lane = Literal["solve", "aux"]

class JobRunner(Protocol):
    async def submit(self, job: Job, lane: Lane) -> None: ...
    async def control(self, job_id: UUID, command: Literal["pause", "resume", "stop", "cancel"]) -> None: ...
    def events(self, job_id: UUID) -> AsyncIterator[JobEvent]: ...
    def queue_position(self, job_id: UUID) -> int | None: ...
    async def shutdown(self) -> None: ...
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Serviço API + SPA | Exigido pelo Princípio V v2.0.0 (jobs no servidor) e pela stack pedida | Solver no navegador viola o V e não tem memória e threads para turn/flop |
| `JobRunner` como Protocol, com 2 raias | Isola o motor da execução (troca futura por arq/Celery, pedido explícito) e permite um runner falso nos testes da API. A raia `aux` evita que exportar ou importar espere um solve de até 10 min | Uma raia só: exportar esperaria o solve. Chamar o pool direto nos routers acoplaria os testes a processos reais |
| Duas representações de solução (dir `.npy` + `.npz`) | Leitura de nó por fatia em ≤ 200 ms (V) e arquivo comprimido para troca (stack) | Só `.npz`: leitura por fatia impossível. Só `.npy`: exportação de vários arquivos e sem compressão |
| SQLAlchemy em vez de `sqlite3` | Pedido do usuário (migrável para PostgreSQL); 3 tabelas | `sqlite3` puro exigiria reescrever o acesso ao migrar. Alembic fica de fora até a 1ª mudança de schema |
| Docker multi-stage | Empacotar a API com o cache do JIT pronto | `uv run` continua disponível para desenvolvimento |
| `phevaluator` (dev) | Oráculo independente para o avaliador (Princípios I e IV) | Comparar só com tabelas próprias não detecta erro sistemático |
