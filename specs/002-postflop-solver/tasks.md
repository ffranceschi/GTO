---

description: "Lista de tarefas — 002 Solver GTO Postflop Heads-Up"
---

# Tasks: Solver GTO Postflop Heads-Up

**Input**: Design documents from `/specs/002-postflop-solver/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml,
websocket.md, engine-api.md), quickstart.md

**Tests**: OBRIGATÓRIOS. A constituição (Princípio IV, INEGOCIÁVEL) exige test-first no motor, e
os Princípios I, II e V exigem testes de referência, gates de explotabilidade e benchmarks. Em
cada fase, as tarefas de teste vêm antes da implementação e MUST falhar antes do código existir.

**Organization**: tarefas agrupadas por user story (spec.md) para implementação e teste
independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: user story da spec (US1–US4)
- Caminhos relativos à raiz do repositório, conforme a estrutura do plan.md: `engine/` (pacote
  `gto_engine`), `api/` (pacote `gto_api`), `web/` (React + Vite)

## Referências rápidas

- Unidades: fichas em bb (arredondadas a 0,01 bb); frequências em [0, 1] no motor, % na UI.
- Explotabilidade (research R6): `(BR_OOP(σ_IP) + BR_IP(σ_OOP) − P) / 2`, em % do pote inicial `P`.
- Configuração padrão da árvore: bets 33% e 75%, raise 100% (pote após o call), 3 raises por
  street, all-in threshold 0,67, `add_allin_action = false`, `allow_donk = false`.
- Limites: `GTO_MAX_SOLVE_MEMORY_BYTES` = 4 GiB; `GTO_SOLUTION_RETENTION_DAYS` = 30;
  `GTO_MAX_IMPORT_BYTES` = 2 GiB; cálculo leve ≤ 200 ms (constituição V).
- Kernels Numba: `@njit(cache=True, nogil=True, fastmath=False)`; sem soma de float compartilhada
  entre threads em `prange`; nenhum laço Python puro em hot loops.
- Mensagens de erro e textos de UI em pt-BR; erros HTTP em RFC 9457 com `code` estável.

## Dependência externa: feature 001

A 002 reutiliza da 001 o avaliador de mãos, cartas/combos, a notação de ranges, a grade 13x13 e
os ranges salvos. A 001 ainda não tem plano nem tarefas. Para que este arquivo seja executável
sozinho, a Phase 2 inclui **as partes do motor da 001 de que a 002 precisa** (cartas, combos,
avaliador, notação de ranges) e uma grade **somente leitura**. O editor interativo de ranges e os
ranges salvos (FR-001, parte "carregar ranges salvos") ficam para a tarefa T098 da fase
final, que depende da 001 estar implementada. Ao planejar a 001, reaproveite estes módulos em vez
de recriá-los.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: inicializar o monorepo, ferramentas e CI.

- [X] T001 Criar `pyproject.toml` na raiz como workspace `uv` (members `engine`, `api`), Python `>=3.12`; configurar ruff (lint + format, linha 100) com `flake8-tidy-imports` banindo `fastapi`, `starlette`, `pydantic`, `sqlalchemy`, `uvicorn` e `gto_api` dentro de `engine/` (regra `TID251`, Princípio III); configurar `mypy --strict` com override `ignore_missing_imports = true` apenas para `numba.*` e `phevaluator.*`, em pyproject.toml
- [X] T002 [P] Criar pacote `engine/pyproject.toml` (`gto_engine`, runtime: `numpy`, `numba`; dev: `pytest`, `hypothesis`, `pytest-benchmark`, `phevaluator`), marcador pytest `benchmark_ref` (excluído por padrão via `addopts = -m "not benchmark_ref"`), e `engine/src/gto_engine/__init__.py` com `__version__ = "0.1.0"` (usado como `engine_version`)
- [X] T003 [P] Criar pacote `api/pyproject.toml` (`gto_api`, deps: `fastapi`, `uvicorn` (sem o extra `[standard]`), `websockets`, `pydantic>=2`, `sqlalchemy>=2`, `python-multipart`, `gto_engine` via workspace; dev: `pytest`, `httpx`; sem `pytest-asyncio`: testes da API e do WebSocket usam o `TestClient` síncrono do FastAPI; nenhuma dependência fora da tabela do plan.md) e `api/src/gto_api/__init__.py`
- [X] T004 [P] Criar o front em `web/` com Vite + React + TypeScript (strict), Vitest, Playwright, `openapi-typescript` e `openapi-fetch`; scripts em web/package.json: `dev`, `build`, `test`, `e2e`, `gen:api` (gera `web/src/api/schema.d.ts` a partir de `http://127.0.0.1:8000/openapi.json`, com fallback para `specs/002-postflop-solver/contracts/openapi.yaml`)
- [X] T005 [P] Criar `.github/workflows/ci.yml` com jobs: `ruff check` + `ruff format --check`; `mypy --strict engine/src api/src`; `uv run pytest engine/tests api/tests`; `pytest-benchmark --benchmark-compare --benchmark-compare-fail=mean:20%` contra baseline em `engine/tests/benchmarks/.baseline`; `npm ci && npm test` em `web/`
- [X] T006 [P] Criar `web/src/i18n/pt-BR.ts` (dicionário de textos) e `web/src/i18n/format.ts` com formatadores pt-BR: número com vírgula decimal, `formatPct(0.819) → "81,9%"`, `formatBb(7.5) → "7,5 bb"`, bytes (`"1,8 MB"`), datas relativas ("em 5 dias")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: primitivas do motor, núcleo do solver validado (Kuhn/Leduc) e infraestrutura da
API e do front. **⚠️ Nenhuma user story começa antes desta fase terminar.**

### Testes do motor (escrever primeiro; devem falhar)

- [X] T007 [P] Testes de cartas e combos: 52 cartas distintas; bijeção índice ↔ combo para os 1326 combos; parse/format `"AhKh"`; ordem canônica (maior carta primeiro); rejeição de `"AhAh"` e `"Xx"`, em engine/tests/unit/test_cards.py
- [X] T008 [P] Teste exaustivo do avaliador de 5 cartas: as 2.598.960 mãos geram exatamente 7.462 classes de força distintas, com contagens por categoria: 40 straight flushes, 624 quadras, 3.744 full houses, 5.108 flushes, 10.200 sequências, 54.912 trincas, 123.552 dois pares, 1.098.240 pares, 1.302.540 cartas altas, em engine/tests/unit/test_evaluator_exhaustive.py
- [X] T009 [P] Property tests (hypothesis) do avaliador de 7 cartas contra `phevaluator`: para pares de mãos aleatórias de 7 cartas, a ordem (maior/menor/igual) coincide; a força independe da ordem das cartas; avaliar 7 cartas = melhor das 21 combinações de 5, em engine/tests/property/test_evaluator_vs_phevaluator.py
- [X] T010 [P] Testes da notação de ranges: `"22+, A2s+, KTo+"` = 162 combos; `"QQ"`, `"55-22"`, `"AK"` (16 combos), `"K9s-K6s"`, `"AhKh"`, pesos `"KQo:0.5"` e `"KQo:50%"`; item repetido mantém o último peso; erro com posição do trecho inválido para `"AKx, 33++"`; ida e volta texto → range → texto canônico → range idêntico (property test com hypothesis), em engine/tests/unit/test_range_notation.py
- [X] T011 [P] Testes de `TreeConfig`: padrão = bets [0.33, 0.75], raise [1.0], `max_raises_per_street = 3`, `allin_threshold = 0.67`, `add_allin_action = False`, `allow_donk = False`; validações exatas do data-model: frações em "(0, 10]", "até 5 por lista", `max_raises_per_street` em "0–6", `allin_threshold` em "(0, 1]", `name` "1–60 caracteres se presente"; violação levanta `InvalidTreeConfigError` com mensagem pt-BR, em engine/tests/unit/test_tree_config.py
- [X] T012 [P] Testes do builder de river (spec US3 cenários 1–4 aplicados ao river): bets 33%/75%, raise 100%, limite 2 ⇒ raiz OOP com `check`, `b33`, `b75`; após 2 raises só `c`/`f`; aposta ≥ 67% do stack restante vira all-in; tamanho acima do stack vira all-in; raise abaixo do mínimo NL é ajustado ao mínimo; ações de mesmo valor são unificadas; rótulos `"Bet 75% (7,5 bb)"`; ids de ação estáveis (`x`, `b75`, `r100`, `c`, `f`, `a`); spot validado (`pot` > 0 e ≤ 10.000, `effective_stack` ≥ 0 e ≤ 10.000, board com 3–5 cartas distintas, cada range com ≥ 1 combo após bloqueios, senão `InvalidSpotError` pt-BR), em engine/tests/unit/test_tree_builder.py
- [X] T013 [P] Testes de `input_hash`: SHA-256 hex de 64 caracteres; ordem das cartas do flop não altera o hash; mudar qualquer peso de range, pote, stack, árvore, algoritmo, parâmetro, seed ou `engine_version` altera o hash; notação e vetor de pesos equivalentes geram o mesmo hash, em engine/tests/unit/test_hashing.py
- [X] T014 [P] Testes de `estimate_tree` (R3): contagem de nós de decisão igual à da árvore construída e pico estimado dentro de ±15% dos bytes realmente alocados em árvores de **river** (ranges a 100% e de referência de research R9); `estimated_solution_bytes` = Σ_n [A(n) × C × 4 + C × 8]; sem isomorfismo, `isomorphism_factor` = 1 e a estimativa de turn/flop é conservadora (≥ a real); executa sem alocar os arrays do solver, em engine/tests/unit/test_estimate.py; e benchmark de cálculo leve (Princípio V, research R3 item 6): parse da notação + validação do spot + `input_hash` + `estimate_tree` somam ≤ 200 ms no pior caso (flop padrão bets 33%/75%, raise 100%, 3 raises, 6/97 bb, os dois ranges a 100%), em engine/tests/benchmarks/test_bench_light.py
- [X] T015 [P] Criar `engine/tests/reference/REFERENCES.md` com a tabela de fontes e tolerâncias de research R7 (Kuhn 1950; Lanctot et al. 2017, arXiv:1711.00832; contagens do avaliador) e as regras exatas do Leduc; cada teste de referência cita no docstring a linha correspondente. Teste de referência Kuhn (Princípio I, research R7): com número fixo de iterações de DCFR(1,5; 0; 2), valor do jogo para o 1º jogador = −1/18 ± 0,001; estratégia do 1º jogador na família de equilíbrio (aposta com J com frequência α ∈ [0, 1/3] e com K com 3α, ± 0,01; nunca aposta com Q); explotabilidade < 0,1% do pote; repetir para `cfr_plus` e `linear_cfr`, em engine/tests/reference/test_kuhn.py
- [X] T016 [P] Teste de referência Leduc (fonte: Lanctot et al. 2017, LP na forma sequencial; regras de research R7): com número fixo de iterações, valor do jogo para o 1º jogador = −0,085606424078 ± 0,005 e explotabilidade < 0,1% do pote; reportar também em mbb/mão, em engine/tests/reference/test_leduc.py
- [X] T017 [P] Testes de explotabilidade (R6): resultado ≥ 0; ≈ 0 (± 1e-9) para o equilíbrio exato de um jogo trivial construído à mão; valor em % do pote inicial; estratégia uniforme em Kuhn tem explotabilidade > 0 conhecida, em engine/tests/unit/test_best_response.py
- [X] T018 [P] Teste de determinismo (Princípio VI): duas execuções com mesmas entradas, parâmetros e `max_iterations` produzem `strategy` idêntica byte a byte, para `dcfr`, `cfr_plus` e `linear_cfr`, com e sem paralelismo (`NUMBA_NUM_THREADS` = 1 e = 4), em engine/tests/unit/test_determinism.py
- [X] T019 [P] Testes de controle cooperativo (R4): `should_stop()` é consultado a cada bloco com duração-alvo ~200 ms; `wait_if_paused()` bloqueia sem consumir iterações; parar retorna estratégia e explotabilidade exata com `stop_reason = "user_stopped"`; alvo atingido ⇒ `target_reached`; tempo esgotado ⇒ `time_limit`; `on_progress` recebe `Progress` com `exploitability_pct = None` até a primeira medição; explotabilidade medida no máximo a cada 2 s e com custo ≤ 10% do tempo, em engine/tests/unit/test_solve_control.py

### Implementação do motor

- [X] T020 Implementar `Card`, `Combo` (índices 0..1325), parse/format e matriz de conflito de cartas entre combos, em engine/src/gto_engine/cards.py
- [X] T021 Implementar o avaliador de 7 cartas com tabelas de perfect hash geradas na primeira execução e cacheadas em `.npy` (em `$NUMBA_CACHE_DIR` ou no diretório do pacote), com kernels `@njit` `eval5`/`eval7` e avaliação em lote de todos os combos para um board de 5 cartas, em engine/src/gto_engine/evaluator/ (`tables.py`, `kernels.py`, `__init__.py`)
- [X] T022 Implementar `Range` (vetor float64 de 1326 pesos em [0, 1]), contagem de combos com bloqueios e o parser/formatador canônico da notação, em engine/src/gto_engine/ranges/range.py e engine/src/gto_engine/ranges/notation.py
- [X] T023 Implementar `Street`, `Position`, `TreeConfig` (dataclass `frozen=True`), `default_tree_config()`, validação e `InvalidTreeConfigError`, em engine/src/gto_engine/game/config.py
- [X] T024 Implementar a árvore vetorizada: `Spot` (com validação e `InvalidSpotError`), `Action`, `DecisionNode`, `ChanceNode`, `TerminalNode`, `NodePath`, `GameTree` com offsets planos (`regret_offset`, `strategy_offset`, `combo_offset`) e `TreeEstimate` (dataclass), em engine/src/gto_engine/game/tree.py
- [X] T025 Implementar `build_tree(spot, config)` para spots de river (uma street), com regras NL de T012, em engine/src/gto_engine/game/builder.py
- [X] T026 Implementar `input_hash(spot, config, params)` sobre JSON canônico (ranges como vetor de 1326 pesos, flop ordenado), em engine/src/gto_engine/game/hashing.py
- [X] T027 Implementar `estimate_tree(spot, config)` por contagem analítica (linhas de aposta por street com memoização por (street, pote, stack) × cartas de cada nó de chance; proibido percorrer a árvore nó a nó, research R3 item 1), sem alocar, calculando pico (`1,2 × Σ_n A(n) × C × 8` + tabelas de showdown) e tamanho em disco; nesta fase sem isomorfismo (fator 1, estimativa conservadora), que é aplicado na US2, em engine/src/gto_engine/game/estimate.py
- [X] T028 Implementar kernels `@njit(cache=True, nogil=True, fastmath=False)`: regret matching (positivo/normalizado), propagação de reach e de valores contrafactuais por nó × combo, payoff de fold com remoção de cartas, varredura ordenada de showdown com remoção de cartas (O(n log n) por board), descontos DCFR (α, β, γ) incluindo os casos CFR+ (α=∞, β=−∞) e Linear CFR (1, 1, 1), em engine/src/gto_engine/solver/kernels.py
- [X] T029 Implementar `exploitability(tree, strategy)` via best response exata (kernels `@njit`), retornando % do pote inicial conforme R6, em engine/src/gto_engine/solver/best_response.py
- [X] T030 Implementar `solve(tree, params, control, on_progress)`: `SolveParams` (`algorithm` em `dcfr|cfr_plus|linear_cfr`, padrão α=1,5 β=0 γ=2, `target_exploitability_pct` padrão 0,5 em (0, 100], `time_limit_s` em (0, 86.400] com padrão por street do board: river 60 s, turn 120 s, flop 900 s (função `default_time_limit(street)`), `max_iterations`, `seed`), Protocols `SolveControl` e `ProgressSink`, `NEVER_STOP`, `Progress`, atualizações alternadas, blocos com `k` adaptativo para ~200 ms, cadência da explotabilidade e `stop_reason`; sem laço Python sobre combos, em engine/src/gto_engine/solver/dcfr.py
- [X] T031 Implementar Kuhn (3 mãos privadas J/Q/K, ante 1, aposta 1) e Leduc (baralho J, J, Q, Q, K, K; ante 1; 1 carta pública; apostas fixas 2 e 4; no máximo 2 apostas (bet + raise) por rodada; par com a carta pública vence, senão a maior carta — exatamente as regras de research R7) na mesma forma vetorizada (vetor de mãos privadas, matriz de conflito, função de showdown), em engine/src/gto_engine/toy_games/kuhn.py e engine/src/gto_engine/toy_games/leduc.py
- [X] T032 Implementar `python -m gto_engine.warmup`: compila e cacheia todos os kernels resolvendo Kuhn e um river minúsculo e avaliando um board, em engine/src/gto_engine/warmup.py

### Infraestrutura da API

- [X] T033 [P] Implementar `Settings` (`GTO_DATA_DIR` padrão `./data`, `GTO_MAX_SOLVE_MEMORY_BYTES` padrão 4 GiB, `GTO_SOLUTION_RETENTION_DAYS` padrão 30, `GTO_MAX_IMPORT_BYTES` padrão 2 GiB, host `127.0.0.1`, porta 8000, `GTO_CORS_ORIGINS` padrão `http://localhost:5173`), em api/src/gto_api/settings.py
- [X] T034 Implementar modelos SQLAlchemy 2 e sessão, com `create_all` no startup (sem Alembic), exatamente como data-model.md: `tree_configs` (`name` "único, 1–60 caracteres"), `solves` (`input_hash` texto(64) indexado e não único; `status` no enum do ciclo de vida incluindo `finalizing` e `expired`; `origin` `solve|import`; snapshots JSON; `pinned` booleano padrão `false`; `last_used_at`, `size_bytes`, `solution_dir`, `error_code`, `error_detail`, timestamps UTC) e `aux_jobs` (`kind` `export|import|cleanup`, `progress` 0–1, `result_path`), em api/src/gto_api/db/models.py e api/src/gto_api/db/session.py
- [X] T035 [P] Implementar erros RFC 9457 (`application/problem+json` com `type`, `title`, `status`, `code`, `detail` pt-BR, `errors[]` por campo) e handlers para `InvalidSpotError`, `InvalidTreeConfigError`, validação Pydantic e 404/409, em api/src/gto_api/errors.py
- [X] T036 Testes do runner local (R4, FR-027): raia `solve` executa 1 job por vez em FIFO com `queue_position` 1, 2, …; job pausado mantém a raia ocupada; raia `aux` roda em paralelo à `solve`; pause/resume/stop/cancel refletem em < 1 s; `stop` grava e `cancel` descarta; worker que não responde a um comando em 10 s é encerrado ⇒ `failed` com `worker_sem_resposta`; ao reiniciar, jobs `queued|running|paused|stopping|finalizing` viram `failed` com `servidor_reiniciado`, em api/tests/integration/test_local_runner.py
- [X] T037 Implementar `Lane = Literal["solve", "aux"]`, `Job`, `JobEvent` e o Protocol `JobRunner` (`submit`, `control`, `events`, `queue_position`, `shutdown`) conforme plan.md, mais um `FakeJobRunner` síncrono para os testes da API, em api/src/gto_api/jobs/runner.py e api/tests/fakes.py
- [X] T038 Implementar `LocalProcessJobRunner`: dois `ProcessPoolExecutor(max_workers=1)` (raias `solve` e `aux`), `multiprocessing.Manager` com `Event` de pausa/parada e `Queue` de eventos por job, task asyncio que consome a fila, atribui `seq` monotônico e repassa aos assinantes, warm-up de cada worker antes de aceitar jobs e reconciliação no startup, em api/src/gto_api/jobs/local_process.py
- [X] T039 Testes de contrato do WebSocket (contracts/websocket.md): primeira mensagem sempre `snapshot`; `seq` monotônico começando em 0; campos `type`, `job_id`, `job_kind`; `progress` ≥ 1×/s e ≤ 5×/s durante `running`; `finished` seguido de fechamento com código 1000; job inexistente fecha com 4404; reconexão recebe novo `snapshot` e o job continua, em api/tests/contract/test_ws_job_events.py
- [X] T040 Implementar o WebSocket `GET /api/v1/jobs/{job_id}/events` (somente servidor → cliente, agregação a no máximo 5 mensagens/s), em api/src/gto_api/ws/job_events.py
- [X] T041 Teste de contrato OpenAPI: todo path, método, parâmetro e schema de specs/002-postflop-solver/contracts/openapi.yaml existe no OpenAPI gerado pelo FastAPI, com os mesmos campos obrigatórios e enums, em api/tests/contract/test_openapi_contract.py
- [X] T042 Implementar o app: lifespan (cria `GTO_DATA_DIR/{solutions,exports,imports}`, banco, runner com warm-up, reconciliação), `GET /api/v1/health` (`503` + `warming_up` até o warm-up terminar, depois `200` + `ready` + `engine_version`), CORS restrito a `GTO_CORS_ORIGINS`, registro do WebSocket (cada router é registrado em `main.py` pela tarefa da story que o cria); entrypoint `uvicorn gto_api.main:app --host 127.0.0.1`, em api/src/gto_api/main.py

### Infraestrutura do front

- [X] T043 [P] Implementar `RangeGrid` somente leitura em SVG: 13x13 com ordem A, K, Q, J, T, 9 … 2, pares na diagonal, suited acima e offsuit abaixo; cada célula dividida em faixas proporcionais às frequências das ações; legenda com cor fixa por tipo de ação (fold, check, call, bet/raise por tamanho, all-in); seleção de célula por clique; teste Vitest em web/tests/unit/RangeGrid.test.tsx, em web/src/components/RangeGrid/RangeGrid.tsx
- [X] T044 [P] Implementar o cliente da API (`openapi-fetch` sobre o schema gerado) e o cliente WebSocket de jobs com reconexão (backoff de 1 s, 2 s, 4 s… até 10 s), descarte de mensagens com `seq` repetido e reconstrução do estado a partir de `snapshot`; teste Vitest em web/tests/unit/jobEvents.test.ts, em web/src/api/client.ts e web/src/api/jobEvents.ts

**Checkpoint**: Kuhn e Leduc passam, o determinismo está garantido, a API sobe com `/health =
ready` e o WebSocket de jobs funciona com o runner falso e o local.

---

## Phase 3: User Story 1 - Resolver um spot de river (Priority: P1) 🎯 MVP

**Goal**: resolver um spot de river com progresso ao vivo, pausar/retomar/parar, fila de solves e
ver a estratégia do nó raiz (agregada, por mão e por combo, com EV e equity). Ranges entram
só pela notação textual; o editor interativo e os ranges salvos da 001 (parte do FR-001) chegam
na T098.

**Independent Test**: resolver o spot de referência (pote 10 bb, stack 50 bb, bets 50% e 100%,
raise 100%) e verificar explotabilidade < 1% do pote em < 30 s e frequências de cada combo
somando 100% (quickstart §1–3).

### Tests for User Story 1 ⚠️ (escrever primeiro; devem falhar)

- [X] T045 [US1] Criar fixtures JSON do spot de referência de river (range OOP `22-TT, A2s-AQs, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A8o-AQo, K9o+, Q9o+, J9o+, T9o, 98o` e range IP `22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A5o+, K9o+, Q9o+, J9o+, T9o, 98o`, exatamente como em research R9; board `Ks 7d 2c Jh 3s`, pote 10, stack 50, bets [0.5, 1.0] para OOP e IP, raise [1.0], 3 raises, threshold 0.67) e do pedido de solve correspondente (`target_exploitability_pct` 0.5, `time_limit_s` 60), em engine/tests/fixtures/river_reference.json e engine/tests/fixtures/river_reference_solve.json — executar antes dos demais testes da US1, que usam estas fixtures
- [X] T046 [P] [US1] Teste de referência do river (gate de CI): com número fixo de iterações, explotabilidade < 1% do pote; para todo combo com reach > 0, a soma das frequências é 1 ± 1e-4 (SC-005), em engine/tests/reference/test_river_reference.py
- [X] T047 [P] [US1] Testes da finalização (R3 item 3, R15): `strategy` normalizada; `ev` por combo do jogador da vez consistente com o EV agregado do nó (± 1e-3 bb); `equity` no river igual (± 1e-6) à equity de showdown calculada por força bruta com `phevaluator` contra o range do oponente que chega ao nó; EV de referência (Princípio I): aplicando a finalização às soluções de Kuhn e Leduc, o EV do 1º jogador na raiz, ponderado pelo range inicial, é −1/18 ± 0,001 e −0,085606424078 ± 0,005 (fontes em engine/tests/reference/REFERENCES.md); pico de memória da finalização ≤ pico do treino; `cancel` durante a finalização encerra em ≤ 1 bloco (~200 ms) sem gravar solução, e `finalize_fraction` cresce de 0 a 1, em engine/tests/unit/test_finalize.py
- [X] T048 [P] [US1] Testes do armazenamento interno: `save_solution_dir` grava `meta.json` (`format_version "1.0"`, `engine_version`, `input_hash`, `spot`, `tree_config`, `solve_params`, `iterations`, `final_exploitability_pct`, `stop_reason`, `created_at`) e `.npy` sem compressão; `open_solution_dir` abre com `mmap_mode="r"` e arrays idênticos; retorna o tamanho em bytes, em engine/tests/unit/test_solution_dir.py
- [X] T049 [P] [US1] Testes de `node_view` na raiz e em nós de decisão do river: `aggregate_frequency` ponderada por pesos e reach; 169 células com frequências, EV médio, equity média e combos efetivos; combos com `reach_weight`, `ev_bb`, `equity`; combos e células com reach 0 no nó aparecem marcados como fora do range (`reach_weight = 0`) e são excluídos das agregações (edge case "Mão com frequência zero"); rótulos das ações, em engine/tests/unit/test_node_view.py
- [X] T050 [P] [US1] Benchmarks: `benchmark_ref` do spot de referência < 1% do pote em < 30 s (SC-001) e `node_view` da raiz ≤ 200 ms; benchmark relativo (CI) de 100 iterações do river, em engine/tests/benchmarks/test_bench_river.py
- [X] T051 [P] [US1] Testes de integração da API de solves (com `FakeJobRunner` e com o runner local): `POST /api/v1/solves` responde 202 em ≤ 200 ms com `status` `queued|running`; pedido com o mesmo `input_hash` de solução concluída devolve 200 com o solve existente, salvo `force: true`; erros 422 pt-BR para board inválido, range sem combos após bloqueios, pote ≤ 0, e `arvore_grande_demais` quando a estimativa passa de `GTO_MAX_SOLVE_MEMORY_BYTES`; board de 3 ou 4 cartas ⇒ 422 `street_nao_suportada` com `detail` "Nesta versão só spots de river podem ser resolvidos" (restrição temporária do MVP, removida na US2); `GET /solves` (mais recentes primeiro, filtro `status`), `GET /solves/{id}`; `POST pause|resume|stop` idempotentes (202) e 409 em estado incompatível; `DELETE` cancela ativo (202) ou remove terminado (204); `GET /solves/{id}/nodes?path=` retorna 409 `solucao_indisponivel` antes de `completed|stopped`, em api/tests/integration/test_solves_api.py
- [X] T052 [P] [US1] Testes da fila (FR-027): um segundo solve criado com outro ativo fica `queued` com `queue_position = 1` e inicia sozinho quando o primeiro termina, é parado ou cancelado; solve pausado mantém a vez; solve na fila pode ser cancelado; o WebSocket emite `status` com a nova posição, em api/tests/integration/test_solve_queue.py

### Implementation for User Story 1

- [X] T053 [US1] Implementar a finalização em `@njit`, processando os nós de decisão em lotes de ~200 ms e consultando `SolveControl` entre lotes (research R4): converte `strategy_sum` em estratégia média normalizada no mesmo buffer, libera os regrets e calcula `ev` e `equity` por combo do jogador da vez em cada nó de decisão; integrar ao fim de `solve()` (inclusive em `stop`), publicando `finalize_fraction`, em engine/src/gto_engine/solver/finalize.py
- [X] T054 [US1] Implementar `Solution`, `SolutionMeta`, `save_solution_dir` e `open_solution_dir` (arrays `strategy`, `ev`, `equity` em float32; `node_offsets`, `combo_offsets` em int64; `exploitability_history` float64 [k, 3]), em engine/src/gto_engine/io/solution_dir.py
- [X] T055 [US1] Implementar `node_view(tree, solution, path)` só com leitura de fatias e agregação vetorizada (sem cálculo de equity/EV), em engine/src/gto_engine/analysis/node_view.py
- [X] T056 [US1] Implementar schemas Pydantic v2 espelhando contracts/openapi.yaml: `RangeInput` (`notation` ou `weights` com exatamente 1326 itens em [0, 1]), `Spot` (board `^[AKQJT2-9][shdc]$`, 3–5 cartas; `pot` > 0 e ≤ 10.000; `effective_stack` ≥ 0 e ≤ 10.000), `TreeConfig`, `SolveParams`, `SolveRequest`, `Solve`, `SolveStatus`, `NodeView`, `ActionView`, `HandView`, `ComboView`, `RangeAtNode`, e conversores para os tipos do motor, em api/src/gto_api/schemas/
- [X] T057 [US1] Implementar caminhos por hash (`solutions/<input_hash>/`), cache LRU de soluções abertas (máx. 2) e atualização de `last_used_at` limitada a 1 escrita por minuto por solução, em api/src/gto_api/storage/solutions.py
- [X] T058 [US1] Implementar o job de solve (executa no worker da raia `solve`): monta a árvore, roda `solve()` com adaptadores de `SolveControl`/`ProgressSink` sobre os Events/Queue do Manager, grava a solução com `save_solution_dir` e atualiza `solves` (`status`, `iterations`, `exploitability_pct`, `stop_reason`, `solution_dir`, `size_bytes`, `last_used_at`, timestamps), em api/src/gto_api/jobs/tasks.py
- [X] T059 [US1] Implementar o router de solves: `POST /solves` (valida, recusa board de 3 ou 4 cartas com 422 `street_nao_suportada` enquanto a US2 não estiver pronta, estima memória com `estimate_tree` e rejeita com `arvore_grande_demais`, calcula `input_hash`, reaproveita solução concluída salvo `force`, submete à raia `solve`), `GET /solves`, `GET /solves/{id}` (com `queue_position` e `expires_at`), `POST /solves/{id}/pause|resume|stop`, `DELETE /solves/{id}`, `GET /solves/{id}/nodes?path=` (leitura via `node_view`, executada em thread para não bloquear o event loop), em api/src/gto_api/routers/solves.py
- [X] T060 [P] [US1] Implementar o formulário do spot: ranges OOP/IP em notação textual com contagem de combos (grade somente leitura), board (só 5 cartas nesta fase, com aviso de que flop e turn chegam na próxima versão), pote e stack em bb, alvo de explotabilidade (padrão 0,5%), tempo-limite (padrão pela street do board: river 60 s, turn 120 s, flop 15 min), árvore padrão, botão "Resolver"; erros da API exibidos por campo em pt-BR, em web/src/features/solver/SpotForm.tsx
- [X] T061 [P] [US1] Implementar o painel de progresso via WebSocket: status, posição na fila, iterações, explotabilidade (% do pote, pt-BR), tempo decorrido, gráfico da explotabilidade por iteração (FR-017), botões pausar/retomar/parar/cancelar, aviso "alvo não alcançado" quando `target_reached = false`, e faixa "Entradas alteradas — a solução exibida corresponde às entradas anteriores" com "Restaurar entradas do solve" e "Novo solve" (research R13), em web/src/features/solver/SolveProgress.tsx
- [X] T062 [US1] Implementar a visão do nó raiz: cabeçalho da solução com a explotabilidade final (% do pote), iterações e motivo de parada, visível em todos os nós (Princípio II); frequência agregada e combos por ação, `RangeGrid` colorido por ação (células fora do range no nó em cinza, sem estratégia exibida) e painel da célula selecionada com frequência, EV (bb) e equity de cada combo (spec US1 cenários 5–6), em web/src/features/solver/NodeStrategy.tsx
- [X] T063 [US1] Montar a página do solver (formulário, progresso e estratégia) e a rota inicial, em web/src/features/solver/SolverPage.tsx e web/src/App.tsx
- [X] T064 [US1] Teste E2E Playwright: configurar o spot de referência, resolver, ver o progresso atualizar, pausar e retomar, ver a grade colorida e o detalhe de `AQs` ao fim (o range OOP de referência não tem AK: `AKs` aparece fora do range), em web/tests/e2e/solve-river.spec.ts

**Checkpoint**: MVP: um spot de river é resolvido de ponta a ponta, com fila, controle e
estratégia da raiz.
Nesta fase, spots de flop e turn são recusados com 422 `street_nao_suportada`.

---

## Phase 4: User Story 2 - Navegar pela árvore de decisão (Priority: P2)

**Goal**: percorrer a árvore nó a nó (ações e cartas de turn/river), ver ranges que chegam a cada
nó, EV e equity por mão; inclui o suporte a spots de turn e flop (nós de chance, isomorfismo).

**Independent Test**: resolver o spot de referência, navegar `Check › Bet 100% › OOP` e conferir
que o range de OOP é o range que deu check ponderado pela frequência de check de cada combo;
resolver o turn padrão em < 60 s e navegar até um river.

### Tests for User Story 2 ⚠️ (escrever primeiro; devem falhar)

- [ ] T065 [P] [US2] Testes de isomorfismo de naipes (R5): o grupo de permutações deixa invariantes o board e os dois ranges; flop rainbow ⇒ grupo trivial; monotone ⇒ até 6 permutações; um range com peso diferente num naipe quebra a simetria; a estratégia de uma carta não canônica é a da canônica com combos permutados, em engine/tests/unit/test_isomorphism.py
- [ ] T066 [US2] Criar as fixtures `turn_reference.json`, `flop_reference.json` e `flop_default_tree.json` em engine/tests/fixtures/ com os ranges, boards, pote/stack e árvores da tabela de research R9 (executar antes dos demais testes da US2, que as usam). Testes do builder multi-street: nós de chance de turn/river com cartas canônicas e pesos de órbita; call de all-in leva direto aos runouts sem decisões; stack efetivo 0 ⇒ showdown direto; donk bet ausente quando `allow_donk = False`; `estimate_tree` dentro de ±15% dos bytes alocados nas árvores de turn e flop de referência (research R9) e `isomorphism_factor` > 1 em board monotone, em engine/tests/unit/test_tree_builder_streets.py
- [ ] T067 [P] [US2] Testes de navegação em `node_view`: caminho `["x", "b75", "c", "Kh", "x"]`; ranges que chegam ao nó = pesos iniciais × produto das frequências ao longo do caminho; `next_cards` exclui cartas do board; nós terminais com `terminal.kind` `fold|showdown`; `breadcrumb` com rótulos pt-BR; caminho inválido levanta erro com mensagem pt-BR; equity em nós de flop/turn igual (± 1e-6) à equity calculada por força bruta, enumerando todos os runouts restantes com `phevaluator`, em um spot de turn e um de flop com ~20 combos por range (teste de referência do Princípio I), em engine/tests/unit/test_node_navigation.py
- [ ] T068 [P] [US2] Benchmarks (usam as fixtures criadas em T066): `benchmark_ref`: `turn_reference` < 1% do pote em < 60 s; `flop_reference` < 1% em < 10 min com pico ≤ 4 GiB; `node_view` ≤ 200 ms em qualquer nó desse flop, em engine/tests/benchmarks/test_bench_turn_flop.py
- [ ] T069 [P] [US2] Testes de integração da navegação: `GET /solves/{id}/nodes?path=x/b75/c/Kh` retorna `kind`, `player`, `pot`, `stacks`, `ranges`, `next_cards` em nós de chance e `terminal` em nós terminais; caminho inválido ⇒ 422 pt-BR; resposta ≤ 200 ms; `POST /solves` e `POST /trees/estimate` aceitam boards de 3 e 4 cartas (a restrição `street_nao_suportada` da US1 deixou de existir), em api/tests/integration/test_nodes_api.py

### Implementation for User Story 2

- [ ] T070 [US2] Implementar o grupo de permutações de naipes que fixa board e ranges, a canonicalização de cartas de chance e o mapeamento de combos para cartas não canônicas; aplicar o fator de isomorfismo nas cartas de chance de `estimate_tree` (engine/src/gto_engine/game/estimate.py), em engine/src/gto_engine/game/isomorphism.py
- [ ] T071 [US2] Estender `build_tree` para flop e turn: nós de chance com cartas canônicas (via isomorfismo), sequências de streets, all-in com runouts e regras de donk, em engine/src/gto_engine/game/builder.py; remover a recusa `street_nao_suportada` de api/src/gto_api/routers/solves.py
- [ ] T072 [US2] Estender os kernels para nós de chance: média ponderada pelas órbitas, remoção de cartas por runout e tabelas de showdown por board de river (`showdown_rank`/`showdown_order` int32), em engine/src/gto_engine/solver/kernels.py
- [ ] T073 [US2] Estender a finalização para equity sobre os runouts restantes, com varredura de baixo para cima (média dos showdowns por carta de chance), em engine/src/gto_engine/solver/finalize.py
- [ ] T074 [US2] Estender `node_view` para caminhos com cartas, nós de chance (`next_cards`), nós terminais, ranges dos dois jogadores e mapeamento de cartas não canônicas, em engine/src/gto_engine/analysis/node_view.py
- [ ] T075 [P] [US2] Liberar boards de 3 e 4 cartas no formulário do spot (web/src/features/solver/SpotForm.tsx) e implementar o navegador: breadcrumb clicável, botões das ações do nó atual, seletor de carta em transições de street (cartas bloqueadas desabilitadas), pote e stacks, grades dos ranges dos dois jogadores e indicação de nó terminal com resultado esperado por mão, em web/src/features/solver/TreeNavigator.tsx
- [ ] T076 [US2] Teste E2E: resolver um turn pequeno, navegar `Check › Bet 75% › Call`, escolher uma carta de river, voltar pelo breadcrumb, em web/tests/e2e/navigate-tree.spec.ts

**Checkpoint**: US1 e US2 funcionam; turn e flop reduzido são resolvidos e navegáveis.

---

## Phase 5: User Story 3 - Configurar a árvore de apostas (Priority: P3)

**Goal**: configurar sizings, raises, threshold, all-in extra e donk bets, ver a estimativa de
nós e memória antes de resolver e salvar configurações nomeadas.

**Independent Test**: montar uma árvore com 1 bet, 1 raise e limite de 1 raise no river e conferir
as ações de cada nó; pedir a estimativa da árvore padrão de flop e ver a recusa com sugestões.

### Tests for User Story 3 ⚠️ (escrever primeiro; devem falhar)

- [ ] T077 [P] [US3] Testes das opções do builder: `add_allin_action = true` adiciona all-in como ação extra sem duplicar quando coincide com um tamanho; `allow_donk = true` permite OOP apostar primeiro numa street depois de IP ter apostado na anterior, em engine/tests/unit/test_tree_builder_options.py
- [ ] T078 [P] [US3] Testes de integração: `POST /api/v1/trees/estimate` retorna `decision_nodes`, `chance_nodes`, `terminal_nodes`, `estimated_bytes`, `estimated_solution_bytes`, `max_bytes`, `within_limit`, `isomorphism_factor` e `suggestions` pt-BR quando `within_limit = false`; CRUD de `/api/v1/tree-configs`: `name` "1–60 caracteres", nome duplicado ⇒ 409 salvo `overwrite: true`, configuração padrão listada com `is_default = true` e não excluível, em api/tests/integration/test_tree_configs_api.py

### Implementation for User Story 3

- [ ] T079 [US3] Implementar `add_allin_action` e `allow_donk` no builder, em engine/src/gto_engine/game/builder.py
- [ ] T080 [US3] Implementar `POST /api/v1/trees/estimate` com sugestões pt-BR (reduzir tamanhos, reduzir raises, reduzir ranges) quando passar do limite, em api/src/gto_api/routers/trees.py
- [ ] T081 [US3] Implementar o CRUD `GET|POST /api/v1/tree-configs` e `PUT|DELETE /api/v1/tree-configs/{config_id}`, com a configuração padrão semeada no startup, em api/src/gto_api/routers/tree_configs.py
- [ ] T082 [P] [US3] Implementar o editor de árvore: tamanhos de bet e raise por street e posição (até 5, em % do pote), limite de raises (0–6), threshold, all-in extra, donk; estimativa ao vivo (nós, memória, tamanho em disco, dentro/fora do limite com sugestões); salvar, carregar, renomear e excluir configurações nomeadas, em web/src/features/solver/TreeConfigEditor.tsx
- [ ] T083 [US3] Teste E2E: configurar 1 bet, 1 raise e limite 1 no river e conferir as ações no navegador; tentar a árvore padrão de flop e ver o botão "Resolver" bloqueado com as sugestões, em web/tests/e2e/tree-config.spec.ts

**Checkpoint**: US1–US3 funcionam de forma independente.

---

## Phase 6: User Story 4 - Exportar, importar e gerenciar soluções (Priority: P4)

**Goal**: exportar e importar soluções (`.npz` comprimido) como jobs da raia `aux`, e gerenciar
o armazenamento: retenção de 30 dias sem uso, fixação, tamanho e exclusão (FR-024, FR-025,
FR-028 a FR-030).

**Independent Test**: exportar uma solução, importá-la e conferir frequências, EVs e
explotabilidade idênticos; fixar uma solução e verificar que a limpeza não a remove.

### Tests for User Story 4 ⚠️ (escrever primeiro; devem falhar)

- [ ] T084 [P] [US4] Testes de troca: `export_npz` → `import_npz` → `open_solution_dir` reproduz arrays e `meta` byte a byte e `node_view` idêntico (SC-006); importar e reexportar produz um `.npz` com arrays e `meta` equivalentes ao original (Princípio VI); leitura com `allow_pickle=False`; arquivo corrompido ou de outro tipo ⇒ `SolutionFormatError`; `format_version` não suportada ⇒ `IncompatibleVersionError`; `on_progress` recebe valores crescentes em [0, 1]; o `.npz` exportado é lido por `numpy.load`; cancelar via `control` durante a exportação ou a importação levanta `Cancelled` em ≤ 1 bloco e não deixa arquivo nem diretório parcial; recalcular a explotabilidade da solução importada dá o valor registrado em `meta` (spec US4 cenário 4), em engine/tests/unit/test_exchange.py
- [ ] T085 [P] [US4] Testes de integração: `POST /solves/{id}/exports` ⇒ 202 com `AuxJob`; eventos no WebSocket com `job_kind = "export"`; `GET /aux-jobs/{id}/file` baixa o `.npz` quando concluído, 409 antes e 410 depois de 24 h; `POST /solutions/import` ⇒ 202, cria solve `completed` com `origin = "import"`, 413 acima de `GTO_MAX_IMPORT_BYTES` e falha com `arquivo_invalido`/`versao_incompativel`; exportação roda enquanto um solve ocupa a raia `solve`, em api/tests/integration/test_exchange_api.py
- [ ] T086 [P] [US4] Testes de retenção: com `GTO_SOLUTION_RETENTION_DAYS = 0`, o job `cleanup` marca como `expired` e remove o diretório das soluções não fixadas; fixadas, solves ativos ou em fila e soluções com exportação em andamento são preservadas; `PATCH /solves/{id}` com `pinned` alterna e zera `expires_at`; `GET /storage` retorna `total_bytes`, `solutions`, `pinned`, `retention_days` e `expiring_soon` (≤ 7 dias); consultar nós atualiza `last_used_at` no máximo 1×/min e exportar também atualiza `last_used_at` (FR-028); o job `cleanup` publica `progress` como fração das soluções avaliadas, em api/tests/integration/test_retention.py

### Implementation for User Story 4

- [ ] T087 [US4] Implementar `export_npz` (zip `ZIP_DEFLATED` com membros `.npy` escritos em fatias via `numpy.lib.format` + `meta.json`, consultando `control` entre fatias e removendo o arquivo parcial ao cancelar) e `import_npz` (leitura em fatias com `control`, removendo o diretório parcial ao cancelar) (validação de formato e versão, escrita no diretório interno), ambos com progresso, em engine/src/gto_engine/io/exchange.py
- [ ] T088 [US4] Implementar os jobs `export` (atualiza `last_used_at` da solução, FR-028), `import` e `cleanup` (consulta o controle e publica `progress` entre soluções) na raia `aux`, passando o `SolveControl` do runner para `export_npz`/`import_npz`, atualizando `aux_jobs` (`progress`, `result_path`, erros) e, no import, criando o registro em `solves`, em api/src/gto_api/jobs/tasks.py
- [ ] T089 [US4] Implementar `POST /solves/{id}/exports`, `POST /solutions/import` (upload gravado em streaming em `imports/`, com limite de tamanho), `GET|DELETE /aux-jobs/{job_id}` e `GET /aux-jobs/{job_id}/file` (streaming, expira em 24 h), em api/src/gto_api/routers/solutions.py e api/src/gto_api/routers/aux_jobs.py
- [ ] T090 [US4] Implementar a retenção: `expires_at` derivado, `PATCH /solves/{id}` (`pinned`), `GET /storage`, e o agendamento do job `cleanup` no startup e a cada 6 h (task asyncio no lifespan), incluindo a remoção de exportações com mais de 24 h, em api/src/gto_api/storage/solutions.py, api/src/gto_api/routers/storage.py e api/src/gto_api/main.py
- [ ] T091 [P] [US4] Implementar a lista de soluções: explotabilidade final (% do pote, Princípio II), tamanho, último uso, "expira em N dias" (destaque ≤ 7 dias), fixar/desafixar, excluir com confirmação, total ocupado e retenção; exportar com progresso via WebSocket e download; importar arquivo com progresso e abrir a solução importada, em web/src/features/solutions/SolutionsPage.tsx
- [ ] T092 [US4] Teste E2E: exportar uma solução de river, importá-la e conferir que a raiz exibe as mesmas frequências e explotabilidade; fixar e desafixar, em web/tests/e2e/export-import.spec.ts

**Checkpoint**: todas as user stories funcionam de forma independente.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: empacotamento, gates de CI, latências de controle, integração com a 001 e validação
final.

- [ ] T093 [P] Criar o `Dockerfile` multi-stage: estágio de build com `uv sync --frozen` e `python -m gto_engine.warmup` para gravar o cache do Numba em `NUMBA_CACHE_DIR=/opt/numba-cache`; estágio runtime com `GTO_DATA_DIR=/data`, volume `/data` e `uvicorn` escutando em `0.0.0.0` dentro do container; documentar `docker run -p 127.0.0.1:8000:8000` (R16), em Dockerfile
- [ ] T094 [P] Adicionar ao CI o job "gates de qualidade": `pytest engine/tests/reference` (Kuhn, Leduc, river com iterações fixas e limites de explotabilidade) como etapa obrigatória e separada, e gravar o baseline do pytest-benchmark no primeiro run da main, em .github/workflows/ci.yml
- [ ] T095 [P] Teste que percorre os módulos de `gto_engine` e falha se algum importa `fastapi`, `starlette`, `pydantic`, `sqlalchemy`, `uvicorn` ou `gto_api` (reforço do `TID251`, Princípio III), em engine/tests/unit/test_engine_has_no_web_imports.py
- [ ] T096 [P] Property tests (hypothesis) do solver em spots de river pequenos e aleatórios: frequências somam 1, explotabilidade ≥ 0 e não cresce entre a 1ª medição e a final em mais de 1e-6 após 200 iterações de DCFR, em engine/tests/property/test_solver_properties.py
- [ ] T097 Teste de latência de controle (SC-008): com um solve de turn rodando no runner local, `pause`, `stop` e `cancel` refletem no WebSocket em < 1 s, inclusive `cancel` durante `finalizing` e `DELETE /aux-jobs/{id}` durante uma exportação de flop (job vira `cancelled` em < 1 s, sem arquivo parcial) e `POST /solves` responde em ≤ 200 ms, em api/tests/integration/test_control_latency.py
- [ ] T098 Integrar o editor interativo de ranges e os ranges salvos da feature 001 no formulário do spot (FR-001), substituindo o campo de notação textual quando a 001 estiver disponível; **depende da implementação da 001**, em web/src/features/solver/SpotForm.tsx
- [ ] T099 [P] Revisar todos os textos da UI e os `detail` de erros da API para pt-BR, com números em formato pt-BR e ações em jargão de poker (FR-023 e Princípio VIII da constituição), em web/src/i18n/pt-BR.ts e api/src/gto_api/errors.py
- [ ] T100 Executar specs/002-postflop-solver/quickstart.md de ponta a ponta (motor, benchmarks de referência, API, front, Docker) incluindo a validação manual do SC-009 (configurar e iniciar o spot de referência de river em menos de 2 min), e registrar os tempos medidos no hardware de referência em specs/002-postflop-solver/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende do Setup e **bloqueia todas as user stories**. Dentro dela:
  testes do motor (T007…T019) → implementação do motor (T020…T032); infraestrutura
  da API depende de T032 (warm-up) e de T030 (tipos de progresso); o front depende de T004.
- **US1 (Phase 3)**: depende só da Foundational. É o MVP.
- **US2 (Phase 4)**: depende da Foundational; usa `node_view` e a finalização da US1
  (T055, T053), que estende. Pode começar em paralelo à US1 pelos testes e pelo
  isomorfismo (T065, T070).
- **US3 (Phase 5)**: depende da Foundational. O `estimate_tree` já existe desde a Foundational
  (T014/T027); a US3 adiciona o endpoint de estimativa, as opções do builder, as configurações
  nomeadas e a UI.
- **US4 (Phase 6)**: depende da US1 (soluções gravadas, T054) e da raia `aux` (T038).
- **Polish (Phase 7)**: depois das user stories desejadas; T098 depende da feature 001.

### Ordem dentro de cada story

Testes (falhando) → motor → schemas/jobs → routers → front → E2E.

### Parallel Opportunities

- Setup: T002, T003, T004, T005, T006 em paralelo depois de T001.
- Foundational: todos os testes do motor (T007…T019) em paralelo; T033, T035,
  T043 e T044 em paralelo com o motor.
- US1: todos os testes (T045…T052) em paralelo; T060 e T061 em paralelo com o
  backend.
- US2/US3: podem ser feitas por pessoas diferentes depois da US1.

---

## Parallel Example: User Story 1

```text
# Testes da US1 juntos (todos devem falhar no início):
T046  engine/tests/reference/test_river_reference.py
T047  engine/tests/unit/test_finalize.py
T048 engine/tests/unit/test_solution_dir.py
T049 engine/tests/unit/test_node_view.py
T051 api/tests/integration/test_solves_api.py
T052  api/tests/integration/test_solve_queue.py

# Front em paralelo com o backend da US1:
T060     web/src/features/solver/SpotForm.tsx
T061 web/src/features/solver/SolveProgress.tsx
```

## Parallel Example: User Story 2

```text
T065 T066 T067 T068 T069   # testes em paralelo
T070 → T071 → T072 → T073 → T074   # motor em sequência
T075                                    # front em paralelo ao motor
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) e Phase 2 (Foundational): os gates de Kuhn/Leduc precisam passar antes de
   seguir (Princípio I).
2. Phase 3 (US1): river de ponta a ponta.
3. **Parar e validar**: quickstart §1–3 com o spot de referência (< 1% em < 30 s).

### Incremental Delivery

1. US1 → MVP (river).
2. US2 → turn e flop reduzido + navegação.
3. US3 → árvores customizadas e estimativa exata.
4. US4 → exportar/importar e retenção.
5. Polish → Docker, gates, integração com a 001.

### Notes

- [P] = arquivos diferentes, sem dependência de tarefa incompleta.
- Cada teste MUST falhar antes da implementação correspondente (Princípio IV).
- Commit ao fim de cada tarefa ou grupo lógico; gates de explotabilidade e benchmarks devem passar
  antes de merge.
