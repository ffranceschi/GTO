# Implementation Plan: Editor de Ranges e Calculadora de Equity

**Branch**: `001-range-equity-calculator` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-range-equity-calculator/spec.md`

## Summary

Calculadora de equity para 2 a 6 participantes (ranges ou mãos), em qualquer street, com editor
de ranges em grade 13x13 e ranges salvos. Construída sobre o que a 002 já entregou: avaliador e
notação no `gto_engine`, runner de jobs, WebSocket de progresso, SQLite e `RangeGrid`. O motor
ganha o módulo `gto_engine.equity`:
- enumeração exata em Numba (heads-up com varredura ordenada; multiway por produto);
- Monte Carlo semeado e determinístico, com margem de erro por participante, mão e combo.

A API escolhe o método por estimativa de custo (exato se ≤ 2 s), roda o cálculo como job numa
raia nova `equity` e expõe CRUD de ranges salvos. O front ganha a aba "Equity", o
`RangeEditor` interativo (que também substitui o campo de texto do solver — T098 da 002) e a
distribuição de equity. Decisões e medições em [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12+ (motor e API), TypeScript 5 (front) — igual à 002

**Primary Dependencies**: nenhuma nova. Usa as da 002 (tabela justificada em
`specs/002-postflop-solver/plan.md`): `numpy`, `numba`, `fastapi`, `pydantic`, `sqlalchemy`,
`uvicorn`, `websockets`, React, Vite, `openapi-fetch`; `phevaluator` como oráculo nos testes.

**Storage**: SQLite da 002, com as tabelas novas `saved_ranges` e `equity_jobs` (resultado em JSON,
24 h)

**Testing**: pytest + hypothesis, testes de referência com `phevaluator`, teste estatístico de
cobertura do Monte Carlo, pytest-benchmark, Vitest, Playwright

**Target Platform**: serviço local de uso pessoal (como a 002), navegador moderno

**Project Type**: aplicação web: biblioteca + API + SPA (monorepo da 002)

**Performance Goals** (hardware de referência: 8 núcleos, 16 GB — R12):

| Medida | Orçamento |
|--------|-----------|
| SC-001 AA vs KK pré-flop | exato (protótipo: 81,946% em 1,05 s no M1 Max) |
| SC-002 HU range vs range no flop, exato | < 2 s |
| SC-003 mão vs mão, qualquer street, exato | < 1 s |
| Monte Carlo heads-up | ≥ 5 M amostras/s |
| Monte Carlo 6-way até ±0,1 pp | < 60 s |
| Parse, format, estimativa (na requisição) | ≤ 200 ms com benchmark |
| Progresso / cancelamento | ≥ 1×/s / ≤ 1 s |

**Constraints**:
- Cálculo de equity sempre como job no servidor.
- Determinismo do Monte Carlo independente do número de threads.
- Nenhum laço Python puro sobre boards, combos ou amostras.
- Uso pessoal, só localhost.

**Scale/Scope**: 1 usuário, 1 job de equity por vez (fila na raia `equity`), até 6 × 1326 combos
por resultado

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constituição **v2.0.0**.

| Princípio | Como o plano atende | Status |
|-----------|---------------------|--------|
| I. Corretude matemática | AA vs KK 81,95% exato (SC-001); confrontos conferidos por força bruta com o oráculo independente `phevaluator`; cobertura estatística do Monte Carlo (SC-005); `REFERENCES.md` estendido (R10) | ✅ |
| II. Explotabilidade | Não se aplica: a feature não tem solver | ✅ (n/a) |
| III. Motor isolado | `gto_engine.equity` sem web/DB; o teste de imports da 002 cobre o pacote novo | ✅ |
| IV. Test-first | Referências, determinismo, cobertura do MC e contratos antes dos kernels e endpoints | ✅ (a cumprir em `tasks.md`) |
| V. Jobs assíncronos, Numba, WebSocket, benchmarks | Ver detalhamento abaixo | ✅ |
| VI. Determinismo | PRNG semeado (xoshiro256**) com sementes por bloco e fatia; nº fixo de fatias; soma em ordem fixa; semente exibida e informável (FR-022) | ✅ |
| VII. Simplicidade | Nenhuma dependência nova; reaproveita runner, WebSocket, notação e grade; único acréscimo estrutural é a raia `equity` | ⚠️ justificado em Complexity Tracking |
| VIII. pt-BR e notação | UI e erros em pt-BR; notação padrão (`22+, A2s+, KTo+, AKs:0.5`); números com vírgula | ✅ |

Detalhamento do Princípio V:
- Equity roda como job na raia `equity`, nunca na requisição.
- Parse, format e estimativa são contagens com teto fixo e benchmark de ≤ 200 ms.
- Hot loops (enumeração e amostragem) em Numba.
- Progresso pelo WebSocket da 002.
- Orçamentos com benchmarks automatizados.

**Re-check pós-design (Phase 1)**: o contrato acrescenta 7 rotas e 2 tabelas sem dependências
novas. Nenhuma violação nova. Gate **aprovado**.

## Mudanças na feature 002

1. `POST /ranges/parse` ganha `dead_cards` opcional, compatível com o uso atual.
2. `LaneJobRunner` passa a ter a raia `equity`, ao lado de `solve` e `aux`.
3. O job `cleanup` também remove `equity_jobs` com mais de 24 h.
4. O formulário do solver passa a usar o `RangeEditor` e os ranges salvos, o que fecha a T098 da
   002.

## Project Structure

### Documentation (this feature)

```text
specs/001-range-equity-calculator/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/
│   ├── openapi.yaml     # acréscimos à API (/ranges/format, /saved-ranges, /equity…)
│   └── websocket.md     # mensagens job_kind = "equity"
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
engine/src/gto_engine/
├── equity/
│   ├── request.py       # EquityRequest, validação (InvalidEquityRequestError pt-BR)
│   ├── estimate.py      # contagem de avaliações e escolha do método (R4)
│   ├── exact.py         # kernels @njit: heads-up (varredura ordenada) e multiway (R2)
│   ├── montecarlo.py    # kernels @njit: amostragem com rejeição, IC 95% (R3)
│   ├── rng.py           # xoshiro256** + splitmix64 em Numba
│   ├── run.py           # run_equity(request, control, on_progress) → EquityResult (blocos ~200 ms)
│   └── result.py        # EquityResult, agregação por mão
└── warmup.py            # + medição da taxa de avaliações (R4)
engine/tests/
├── reference/test_equity_reference.py      # AA vs KK + oráculo phevaluator
├── unit/test_equity_*.py                   # exato, MC, estimativa, multiway, determinismo
├── property/test_equity_properties.py      # hypothesis: soma = 1, simetria, bloqueios
└── benchmarks/test_bench_equity.py

api/src/gto_api/
├── routers/ranges.py          # + /ranges/format, dead_cards
├── routers/saved_ranges.py    # CRUD
├── routers/equity.py          # /equity/estimate, /equity-jobs (+ stop, cancel)
├── jobs/tasks.py              # + equity_job
├── jobs/local_process.py      # + raia "equity"
└── db/models.py               # + SavedRangeRow, EquityJobRow

web/src/
├── components/RangeEditor/    # grade interativa (clique/arrasto, peso, detalhe de combos), texto ↔ grade
├── features/equity/           # EquityPage: participantes, board, método, progresso, resultados, distribuição
├── features/ranges/           # menu de ranges salvos (salvar/carregar/renomear/excluir)
└── features/solver/SpotForm.tsx   # usa RangeEditor + ranges salvos (T098 da 002)
```

**Structure Decision**: o mesmo monorepo da 002. Equity é um módulo novo do `gto_engine`. A API
ganha routers e uma raia de job. O front ganha a aba "Equity" e o `RangeEditor`, que é
compartilhado com o solver.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Terceira raia no runner (`equity`) | Equity é interativo (ms a 60 s) e não pode esperar um solve de até 10 min nem atrasar exportações | Raia `aux`: exportações esperariam o Monte Carlo. Rodar na requisição: proibido pelo Princípio V |
| Endpoint `/ranges/format` | A grade edita pesos no cliente e precisa do texto canônico | Reimplementar a notação em TypeScript duplicaria a lógica validada (Princípio I) |
