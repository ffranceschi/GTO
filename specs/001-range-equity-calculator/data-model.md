# Data Model — 001 Editor de Ranges e Calculadora de Equity

**Data**: 2026-10-12 | **Plano**: [plan.md](./plan.md)

Entidades já existentes na 002 e reaproveitadas: `Card`, `Combo` (0..1325), `Range` (vetor de 1326
pesos), notação canônica. Unidades: equity, win e tie em [0, 1] no motor e % na UI.

## Motor (`gto_engine.equity`)

### Participant

| Campo | Tipo | Regras |
|-------|------|--------|
| `range` | `Range` | ≥ 1 combo com peso > 0 depois dos bloqueios (board + mãos específicas dos outros) |
| `is_hand` | `bool` | derivado: exatamente 1 combo com peso 1 (mão específica) |

### EquityRequest

| Campo | Tipo | Regras |
|-------|------|--------|
| `participants` | `list[Participant]` | 2 a 6 (FR-013) |
| `board` | `tuple[int, ...]` | 0, 3, 4 ou 5 cartas distintas (FR-014) |
| `method` | `Literal["auto", "exact", "monte_carlo"]` | padrão `auto` (R4) |
| `target_margin_pp` | `float` | em [0,05; 1]; padrão 0,1 (FR-018) |
| `time_limit_s` | `float` | (0, 3.600]; padrão 60 |
| `seed` | `int` | 0..2⁶⁴−1; padrão 0 (FR-022) |

Validação (FR-015, `InvalidEquityRequestError` em pt-BR): cartas duplicadas entre board e mãos
específicas; board com tamanho inválido; participante sem combos; nenhuma combinação compatível
entre todos ("não há confronto possível").

### EquityEstimate

`method` (`exact` | `monte_carlo`), `exact_evaluations` (int), `estimated_exact_s` (float),
`rate_evals_per_s` (float).

### EquityResult

| Campo | Tipo |
|-------|------|
| `method` | `exact` \| `monte_carlo` |
| `stop_reason` | `exact` \| `target_reached` \| `time_limit` \| `user_stopped` |
| `samples` | int (Monte Carlo) ou nº de combinações avaliadas (exato) |
| `seed` | int |
| `elapsed_s` | float |
| `participants[]` | `ParticipantResult` |

`ParticipantResult`: `equity`, `win`, `tie`, `margin` (meia-largura do IC 95%; 0 no exato),
`hands[]` (`HandResult`: `hand` ex. "AKs", `combos`, `equity`, `win`, `tie`, `margin`, `samples`),
`combos[]` (`ComboResult`: `combo`, `weight`, `equity`, `win`, `tie`, `margin`, `samples`).

Invariantes:
- Σ equities dos participantes = 1 (± 1e-9 no exato; ± soma das margens no Monte Carlo).
- Média das equities por combo ponderada por peso × combinações compatíveis = equity do
  participante (± 0,05 pp no exato — US3 cenário 3).
- `margin > 0,02` ⇒ marcado para destaque na UI (FR-023).

## Ciclo de vida de um job de equity

```text
queued ──► running ──► completed (exact | target_reached | time_limit | user_stopped)
   │          │
   └──────────┴──► cancelled   (DELETE, inclusive ao alterar entradas — R6)
              └──► failed      (erro; ex.: confronto_improvavel)
```

## Persistência (SQLite da 002)

### `saved_ranges`

| Coluna | Tipo | Regras |
|--------|------|--------|
| `id` | UUID (texto) | PK |
| `name` | texto | único, 1–60 caracteres (FR-025) |
| `notation` | texto | notação canônica (ida e volta exata ⇒ pesos preservados — FR-026) |
| `combos` | real | soma dos pesos (sem bloqueios) |
| `created_at`, `updated_at` | datetime UTC | |

### `equity_jobs`

| Coluna | Tipo | Regras |
|--------|------|--------|
| `id` | UUID (texto) | PK; também o id do job no runner (raia `equity`) |
| `status` | texto | `queued` \| `running` \| `completed` \| `cancelled` \| `failed` |
| `request_json` | JSON | `EquityRequest` (participantes em notação canônica) |
| `method` | texto \| nulo | método escolhido |
| `result_json` | JSON \| nulo | `EquityResult` quando concluído |
| `error_code`, `error_detail` | texto \| nulo | |
| `created_at`, `finished_at` | datetime UTC | removidos pelo `cleanup` após 24 h (R9) |
