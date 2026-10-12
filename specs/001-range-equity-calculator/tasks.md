---

description: "Lista de tarefas — 001 Editor de Ranges e Calculadora de Equity"
---

# Tasks: Editor de Ranges e Calculadora de Equity

**Input**: Design documents from `/specs/001-range-equity-calculator/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml,
websocket.md), quickstart.md. Feature 002 já implementada na `main` (motor, API, runner,
WebSocket, `RangeGrid`).

**Tests**: OBRIGATÓRIOS (constituição, Princípio IV). Em cada fase, os testes vêm antes e MUST
falhar antes da implementação.

**Organization**: tarefas agrupadas por user story da spec (US1–US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: user story da spec (US1–US4)
- Caminhos relativos à raiz do repositório (monorepo da 002: `engine/`, `api/`, `web/`)

## Referências rápidas

- Equity: vitória = 1, empate entre k jogadores = 1/k (FR-019); combos ponderados pelos pesos;
  combinações com cartas repetidas excluídas.
- Exato quando o tempo estimado ≤ 2 s (R4); o jogador pode forçar `exact` ou `monte_carlo`.
- Monte Carlo: margem-alvo padrão ±0,1 pp (IC 95%), configurável em [0,05; 1] pp; tempo-limite
  padrão 60 s (FR-018); semente exibida e informável (FR-022).
- Kernels `@njit(nogil=True, fastmath=False)`; `cache=True` só em funções não recursivas (R8 da 002);
  nenhum laço Python sobre boards, combos ou amostras (Princípio V).
- Cálculo leve na requisição (parse, format, estimativa): ≤ 200 ms com benchmark.
- Textos e erros em pt-BR, números com vírgula decimal; notação `22+, A2s+, KTo+, AKs:0.5`.

---

## Phase 1: Setup

- [X] T001 Criar os pacotes `engine/src/gto_engine/equity/__init__.py`, `web/src/features/equity/`, `web/src/features/ranges/` e `web/src/components/RangeEditor/`, e acrescentar em engine/tests/reference/REFERENCES.md as referências de equity de research R10 (AA vs KK = 81,95% ± 0,1 pp por enumeração exata conferida pelo oráculo `phevaluator`; confrontos mão vs mão e mão vs range por força bruta com `phevaluator`, tolerância 1e-9; contagens de combos), em engine/tests/reference/REFERENCES.md
- [X] T002 [P] Copiar a abordagem do teste de contrato da 002 para também verificar specs/001-range-equity-calculator/contracts/openapi.yaml contra o OpenAPI gerado (paths, métodos, parâmetros, schemas obrigatórios), marcando como xfail as rotas de stories ainda não implementadas, em api/tests/contract/test_openapi_contract_001.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ Nenhuma user story começa antes desta fase terminar.**

### Testes (escrever primeiro; devem falhar)

- [X] T003 [P] Testes do PRNG: `xoshiro256**` com `splitmix64(seed, bloco, fatia)` reproduz a mesma sequência para a mesma semente; sementes diferentes geram sequências diferentes; distribuição uniforme de `randint(0, n)` aprovada num teste qui-quadrado a 99% (10⁶ sorteios), em engine/tests/unit/test_equity_rng.py
- [X] T004 [P] Testes de `EquityRequest`: 2 a 6 participantes; board com 0, 3, 4 ou 5 cartas distintas; `target_margin_pp` em [0,05; 1]; `time_limit_s` em (0, 3600]; mensagens pt-BR para carta duplicada entre board e mãos específicas (indica a carta), participante sem combos após bloqueios (indica o participante) e "não há confronto possível" quando nenhuma combinação compatível existe (FR-015, edge cases da spec), em engine/tests/unit/test_equity_request.py
- [X] T005 [P] Testes da raia `equity` no runner: um job de equity roda enquanto as raias `solve` e `aux` estão ocupadas; FIFO e `queue_position` dentro da raia `equity`; cancelamento ≤ 1 s, em api/tests/integration/test_equity_lane.py

### Implementação

- [X] T006 Implementar `xoshiro256**`, `splitmix64` e `randint`/`random` em `@njit(cache=True, nogil=True)`, em engine/src/gto_engine/equity/rng.py
- [X] T007 Implementar `Participant`, `EquityRequest` (dataclasses `frozen=True`), validação com `InvalidEquityRequestError` em pt-BR e o vetor de combos/pesos por participante após bloqueios do board, em engine/src/gto_engine/equity/request.py
- [X] T008 Acrescentar a raia `"equity"` ao `LaneJobRunner` (tipo `Lane`, executores, warm-up), em api/src/gto_api/jobs/runner.py e api/src/gto_api/jobs/local_process.py
- [X] T009 Acrescentar os modelos `SavedRangeRow` (`name` "único, 1–60 caracteres", `notation` canônica, `combos`, timestamps) e `EquityJobRow` (`status` em `queued|running|completed|cancelled|failed`, `request_json`, `method`, `result_json`, erros, timestamps) conforme data-model.md; incluir na reconciliação após reinício (jobs `queued|running` viram `failed` com `servidor_reiniciado`) e no job `cleanup` a remoção de `equity_jobs` com mais de 24 h, em api/src/gto_api/db/models.py, api/src/gto_api/db/session.py, api/src/gto_api/routers/aux_jobs.py e api/src/gto_api/jobs/tasks.py

**Checkpoint**: PRNG, validação da entrada, raia `equity` e tabelas prontos.

---

## Phase 3: User Story 1 - Calcular equity entre mãos e ranges digitados (Priority: P1) 🎯 MVP

**Goal**: 2 a 6 participantes em notação textual, qualquer street, resultado exato ou estimado com
margem, progresso ao vivo, parar e cancelar.

**Independent Test**: `AA` vs `KK` sem board ⇒ 81,9% / 18,1% (± 0,1 pp), marcado como "Exato".

### Tests for User Story 1 ⚠️ (escrever primeiro; devem falhar)

- [X] T010 [P] [US1] Teste de referência (Princípio I, REFERENCES.md): AA vs KK pré-flop exato = 0,8195 ± 0,001 (SC-001); ~20 confrontos mão vs mão e mão vs range em pré-flop, flop, turn e river iguais (± 1e-9) à força bruta com `phevaluator`; `AsAd` vs `KsKd` com board `2c 7h 9d Jc 3s` ⇒ 100% / win 100% / tie 0% (US1 cenário 3); equities **por combo** de um range vs range exato (flop e turn) e de um multiway pequeno (3 participantes) iguais (± 1e-9) à força bruta com `phevaluator` do combo contra os demais (Princípio I, base da distribuição da US3), em engine/tests/reference/test_equity_reference.py
- [X] T011 [P] [US1] Testes do exato: heads-up com ranges ponderados (pesos parciais) igual à soma ponderada dos confrontos mão vs mão; multiway (3 a 6) com empates contando 1/k e soma das equities = 1 (± 1e-9); combinações com cartas repetidas excluídas; resultado independente do nº de threads (byte a byte, `NUMBA_NUM_THREADS` 1 e 4), em engine/tests/unit/test_equity_exact.py
- [X] T012 [P] [US1] Testes do Monte Carlo: mesma entrada + semente ⇒ resultado idêntico com 1 e 4 threads (FR-022); cobertura: em 200 sementes, o valor exato cai dentro da margem exibida em ≥ 95% (SC-005, limite binomial); parada por margem-alvo, tempo-limite e `stop` (resultado parcial "Estimado" com margem); cancelamento levanta `Cancelled` em ≤ 1 bloco; taxa de rejeição > 99% ⇒ erro `confronto_improvavel`, em engine/tests/unit/test_equity_montecarlo.py
- [X] T013 [P] [US1] Testes da estimativa (R4): nº de avaliações por contagem (sem enumerar) igual ao contado pelo kernel em casos pequenos; `auto` escolhe exato para AA vs KK, para HU range vs range no flop e para qualquer HU no river, e Monte Carlo para 6 ranges de 100% pré-flop e para multiway de ranges amplos no river; `exact`/`monte_carlo` forçados respeitados; benchmark de cálculo leve ≤ 200 ms no pior caso (6 ranges de 100%, board vazio) em engine/tests/benchmarks/test_bench_equity_light.py, e testes em engine/tests/unit/test_equity_estimate.py
- [X] T014 [P] [US1] Benchmarks `benchmark_ref`: SC-001 AA vs KK exato; SC-002 HU range vs range (100% cada) no flop exato < 2 s; SC-003 mão vs mão em qualquer street < 1 s; Monte Carlo HU ≥ 5 M amostras/s e 6-way ranges amplos até ±0,1 pp < 60 s (SC-011); benchmark relativo (CI) de 1 s de Monte Carlo, em engine/tests/benchmarks/test_bench_equity.py
- [X] T015 [P] [US1] Testes de integração (com `FakeJobRunner`): `POST /api/v1/equity/estimate` (método e tempo estimado); `POST /api/v1/equity-jobs` ⇒ 202 em ≤ 200 ms com `method`; `GET /api/v1/equity-jobs/{id}` traz o resultado após `finished` (participantes com `equity`, `win`, `tie`, `margin`); `POST .../stop` mantém resultado parcial com `stop_reason = "user_stopped"`; `DELETE` cancela (≤ 1 s) e não guarda resultado; 409 em estado incompatível; 422 pt-BR para carta duplicada, board inválido, participante vazio e sem confronto, em api/tests/integration/test_equity_api.py
- [X] T016 [P] [US1] Teste de contrato do WebSocket para `job_kind = "equity"` (specs/001-range-equity-calculator/contracts/websocket.md): `progress` do Monte Carlo com `samples`, `equities`, `margins`, `target_margin`; do exato com `fraction`; `finished` com `stop_reason`, em api/tests/contract/test_ws_equity.py

### Implementation for User Story 1

- [X] T017 [US1] Implementar `EquityResult`, `ParticipantResult`, `ComboResult` (por combo: peso, equity, win, tie, margem, amostras), em engine/src/gto_engine/equity/result.py
- [X] T018 [US1] Implementar os kernels exatos (R2): heads-up com varredura ordenada e remoção de cartas por board completo (reaproveitando `showdown_sums` e as tabelas do avaliador) e multiway pelo produto de mãos compatíveis; `prange` sobre fatias fixas da primeira carta da completação, acumuladores por fatia somados em ordem fixa; acumuladores por combo, em engine/src/gto_engine/equity/exact.py
- [X] T019 [US1] Implementar o Monte Carlo (R3): sorteio por peso (soma acumulada + busca binária), rejeição de cartas repetidas, completação do board, acumuladores por participante e por combo (soma e soma dos quadrados para o IC 95%), 64 fatias fixas por bloco com sementes `splitmix64(seed, bloco, fatia)`, em engine/src/gto_engine/equity/montecarlo.py
- [X] T020 [US1] Implementar `estimate_equity(request, rate)` por contagem (boards completos × mãos; multiway × combinações compatíveis contadas por inclusão-exclusão de cartas) e a escolha `auto` com limite de 2 s, em engine/src/gto_engine/equity/estimate.py
- [X] T021 [US1] Implementar `run_equity(request, control, on_progress)`: exato em blocos (fração concluída) ou Monte Carlo em blocos de ~200 ms (amostras, equities, margens), parada por margem/tempo/`stop`, `Cancelled` ao cancelar, e a medição da taxa de avaliações no warm-up (`gto_engine.warmup`), em engine/src/gto_engine/equity/run.py e engine/src/gto_engine/warmup.py
- [X] T022 [US1] Implementar schemas Pydantic de `EquityRequest` (participantes em `notation` ou `weights` com exatamente 1326 itens; `method` `auto|exact|monte_carlo`; `target_margin_pp` em [0,05; 1]; `time_limit_s` em (0, 3600]; `seed` ≥ 0), `EquityEstimate`, `EquityJob`, `EquityResult`, em api/src/gto_api/schemas/equity.py
- [X] T023 [US1] Implementar o job `equity_job` (raia `equity`): monta o request, roda `run_equity` com o controle do worker, publica progresso conforme websocket.md e devolve o resultado; o hook de persistência grava `result_json`, `method` e status em `equity_jobs`, em api/src/gto_api/jobs/tasks.py e api/src/gto_api/jobs/persist.py
- [X] T024 [US1] Implementar `POST /equity/estimate`, `POST /equity-jobs`, `GET|DELETE /equity-jobs/{job_id}` e `POST /equity-jobs/{job_id}/stop`, e registrar o router, em api/src/gto_api/routers/equity.py e api/src/gto_api/main.py
- [X] T025 [P] [US1] Implementar a página "Equity" (nova aba): 2 a 6 participantes com campo de notação, board (0, 3, 4 ou 5 cartas), método (automático/exato/Monte Carlo), margem-alvo e tempo-limite, semente, botão "Calcular"; progresso via WebSocket (amostras, margens, tempo, fração no exato); botões parar e cancelar; resultado por participante com equity, win, tie, "Exato"/"Estimado" e margem; ao alterar qualquer entrada com job ativo, enviar `DELETE` e mostrar "Entradas alteradas" sem recalcular (R6), em web/src/features/equity/EquityPage.tsx e web/src/App.tsx
- [X] T026 [US1] Teste E2E: AA vs KK ⇒ 81,9% / 18,1% "Exato"; 3 ranges amplos ⇒ "Estimado" com margem e progresso; alterar um range durante o cálculo ⇒ "Entradas alteradas", em web/tests/e2e/equity-basic.spec.ts

**Checkpoint**: MVP — calculadora de equity por texto, exata e Monte Carlo.

---

## Phase 4: User Story 2 - Montar ranges na grade 13x13 (Priority: P2)

**Goal**: editor interativo com clique, arrasto, peso parcial, combos de naipe, texto ↔ grade e
contagem com bloqueios do board e das mãos conhecidas.

**Independent Test**: digitar `22+, A2s+, KTo+` ⇒ grade correta e 162 combos (12,2%); editar a
grade ⇒ texto atualizado.

### Tests for User Story 2 ⚠️

- [X] T027 [P] [US2] Testes de integração: `POST /ranges/parse` com `dead_cards` desconta board e mãos específicas (`AA` com `As` morto ⇒ 3); `POST /ranges/format` devolve a notação canônica (`AKs` com `AsKs` removido ⇒ `AhKh, AdKd, AcKc`; `KQo:0.5`); ambos em ≤ 200 ms, em api/tests/integration/test_ranges_api.py
- [X] T028 [P] [US2] Testes Vitest do `RangeEditor`: clique seleciona com peso 100% e conta 4 combos para `AKs`; arrasto a partir de célula vazia seleciona e a partir de célula selecionada remove (FR-006); peso ativo 50% em `KQo` ⇒ 6 combos e faixa parcial; detalhe da célula com 4/6/12 combos e peso por combo (FR-008); "Limpar" e "Tudo" (FR-010); texto inválido mostra o trecho e não altera a grade (FR-004), em web/tests/unit/RangeEditor.test.tsx

### Implementation for User Story 2

- [X] T029 [US2] Acrescentar `dead_cards` em `/ranges/parse` e criar `POST /ranges/format` (pesos → notação canônica), em api/src/gto_api/routers/ranges.py
- [X] T030 [US2] Implementar o `RangeEditor`: grade interativa sobre o `RangeGrid` (pointer events para arrasto; ação definida pela 1ª célula), peso ativo 0–100% em passos de 1%, faixa proporcional ao peso, detalhe de combos de naipe por célula, "Limpar"/"Tudo", texto ↔ grade via `/ranges/parse` e `/ranges/format` com debounce, contagem de combos e % de 1326 com bloqueios (FR-011, atualização imediata — FR-012), em web/src/components/RangeEditor/RangeEditor.tsx
- [X] T031 [US2] Usar o `RangeEditor` em cada participante da página Equity, passando como `dead_cards` o board e as cartas das mãos específicas dos outros participantes, em web/src/features/equity/EquityPage.tsx
- [X] T032 [US2] Teste E2E: montar `22+, A2s+, KTo+` só pela grade e conferir o texto e 162 combos (12,2%); board `As 7d 2c` com `AA` ⇒ 3 combos; detalhe de `AKs` desmarcando `AsKs` ⇒ texto `AhKh, AdKd, AcKc`, em web/tests/e2e/range-editor.spec.ts

**Checkpoint**: US1 e US2 funcionam de forma independente.

---

## Phase 5: User Story 3 - Distribuição de equity dentro do range (Priority: P3)

**Goal**: equity, win e tie por mão e por combo, grade colorida por equity e curva de equity,
inclusive em multiway e Monte Carlo (com margem e amostras por mão/combo).

**Independent Test**: `QQ+, AKs` vs `JJ-99` num flop ⇒ cada mão listada e média ponderada igual
à equity total (± 0,05 pp).

### Tests for User Story 3 ⚠️

- [X] T033 [P] [US3] Testes da agregação por mão: média das equities por combo ponderada por peso × combinações compatíveis = equity do participante (± 0,05 pp no exato — US3 cenário 3); no Monte Carlo, cada mão e combo tem `margin` e `samples` e `margin > 0,02` é sinalizado (FR-023, cenário 5); multiway com 3 participantes, em engine/tests/unit/test_equity_distribution.py
- [X] T034 [P] [US3] Testes Vitest da distribuição: tabela ordenável por equity com combos, equity, win, tie (e margem/amostras no Monte Carlo); destaque visual para margem > ±2 pp; grade colorida por equity média; curva "fração do range com equity ≥ X", em web/tests/unit/EquityDistribution.test.tsx

### Implementation for User Story 3

- [X] T035 [US3] Implementar a agregação por mão (`HandResult`: combos, equity, win, tie, margem, amostras) e o sinal de margem alta no resultado, em engine/src/gto_engine/equity/result.py
- [X] T036 [US3] Implementar a distribuição: tabela por mão e por combo (ordenável), grade colorida por equity (escala contínua com legenda), curva de equity do range e destaque de margens altas, em web/src/features/equity/EquityDistribution.tsx
- [X] T037 [US3] Teste E2E: `QQ+, AKs` vs `JJ-99` no flop `Ks 7d 2c` ⇒ distribuição com as mãos do primeiro range e grade colorida; 3 ranges amplos (Monte Carlo) ⇒ margens por mão visíveis, em web/tests/e2e/equity-distribution.spec.ts

**Checkpoint**: US1–US3 funcionam de forma independente.

---

## Phase 6: User Story 4 - Ranges nomeados (Priority: P4)

**Goal**: salvar, listar, carregar, renomear e excluir ranges no servidor local, disponíveis na
calculadora e no solver.

**Independent Test**: salvar um range com pesos parciais, recarregar a página, carregá-lo e
conferir grade, texto e contagem idênticos.

### Tests for User Story 4 ⚠️

- [X] T038 [P] [US4] Testes de integração do CRUD `/api/v1/saved-ranges`: `name` "1–60 caracteres"; nome duplicado ⇒ 409 `nome_em_uso` salvo `overwrite: true`; notação inválida ⇒ 422; pesos preservados exatamente (ida e volta da notação canônica) e persistência após reiniciar o app (SC-010); renomear com nome em uso ⇒ 409; excluir ⇒ 204/404, em api/tests/integration/test_saved_ranges_api.py

### Implementation for User Story 4

- [X] T039 [US4] Implementar o router `GET|POST /saved-ranges` e `PUT|DELETE /saved-ranges/{range_id}` (notação validada e normalizada para a canônica), em api/src/gto_api/routers/saved_ranges.py e api/src/gto_api/main.py
- [X] T040 [P] [US4] Implementar o menu de ranges salvos (salvar com nome, confirmar sobrescrita, listar, carregar no participante, renomear, excluir com confirmação) acoplado ao `RangeEditor`, em web/src/features/ranges/SavedRangesMenu.tsx
- [X] T041 [US4] Substituir os campos de notação do formulário do solver pelo `RangeEditor` com o menu de ranges salvos (fecha a T098 da 002, FR-001 da 002) e marcar a T098 como concluída em specs/002-postflop-solver/tasks.md, em web/src/features/solver/SpotForm.tsx
- [X] T042 [US4] Teste E2E: salvar "BTN open 100bb" com `KQo:0.5`, recarregar, carregar e conferir texto e combos idênticos; o mesmo range aparece e carrega no formulário do solver, em web/tests/e2e/saved-ranges.spec.ts

**Checkpoint**: todas as user stories funcionam de forma independente.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T043 [P] Property tests (hypothesis): para ranges e boards aleatórios pequenos, soma das equities = 1; trocar a ordem dos participantes permuta os resultados; permutar naipes de todo o input não muda as equities; exato e Monte Carlo concordam dentro de 3 margens, em engine/tests/property/test_equity_properties.py
- [X] T044 Teste de latência com o runner de processos: cancelar e parar um Monte Carlo 6-way refletem no WebSocket em < 1 s; `POST /equity-jobs` ≤ 200 ms, em api/tests/integration/test_equity_latency.py
- [X] T045 [P] Revisar textos e erros novos em pt-BR (números com vírgula, notação de poker) e mover literais para o dicionário, em web/src/i18n/pt-BR.ts e api/src/gto_api/errors.py
- [ ] T046 Executar specs/001-range-equity-calculator/quickstart.md de ponta a ponta, incluindo a validação manual do SC-009 (montar `22+, A2s+, KTo+` pela grade em < 30 s), e registrar os tempos medidos em specs/001-range-equity-calculator/quickstart.md

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1 (Phase 3)**: depende só da Foundational. É o MVP.
- **US2 (Phase 4)**: depende da Foundational; usa a página Equity da US1 (T025) para encaixar o
  editor, mas o editor e os endpoints são independentes.
- **US3 (Phase 5)**: depende da US1 (resultado por combo, T017, e página, T025).
- **US4 (Phase 6)**: depende da US2 (o menu se acopla ao `RangeEditor`, T030).
- **Polish (Phase 7)**: depois das stories desejadas.

Dentro de cada story: testes (falhando) → motor → schemas/job → router → front → E2E.

### Parallel Opportunities

- Foundational: T003, T004 e T005 em paralelo; implementação de T006 e T007 em paralelo
  com T008 e T009.
- US1: todos os testes (T010…T016) em paralelo; T025 em paralelo com o motor.
- US2 e US3 podem andar em paralelo depois da US1 (arquivos diferentes).

## Parallel Example: User Story 1

```text
T010 engine/tests/reference/test_equity_reference.py
T011 engine/tests/unit/test_equity_exact.py
T012 engine/tests/unit/test_equity_montecarlo.py
T013 engine/tests/unit/test_equity_estimate.py
T015 api/tests/integration/test_equity_api.py
T025 web/src/features/equity/EquityPage.tsx   # front em paralelo ao motor
```

## Implementation Strategy

1. Setup + Foundational.
2. US1 → **parar e validar**: AA vs KK 81,9% exato; SC-002/SC-003 nos benchmarks.
3. US2 (editor) → US3 (distribuição) → US4 (ranges salvos + solver).
4. Polish.
