# Data Model — 002 Solver GTO Postflop Heads-Up

**Data**: 2026-10-12 | **Plano**: [plan.md](./plan.md)

Três camadas: entidades do **motor** (`gto_engine`, dataclasses imutáveis + arrays NumPy),
**schemas da API** (Pydantic v2, espelham o motor) e **persistência** (SQLite via SQLAlchemy 2 +
arquivos `.npz`). Unidades: fichas em **bb** (float64 na entrada, arredondado a 0,01 bb), frequências
em [0, 1] no motor e em % na UI.

Entidades da feature 001 reutilizadas: `Card`, `Combo` (índice 0..1325), `Range` (vetor de 1326
pesos em [0, 1]), `Board`.

---

## Motor (`gto_engine`)

### Spot

| Campo | Tipo | Regras |
|-------|------|--------|
| `oop_range` | `Range` | ≥ 1 combo com peso > 0 depois dos bloqueios do board |
| `ip_range` | `Range` | idem |
| `board` | `Board` | 3, 4 ou 5 cartas distintas |
| `pot` | `float` (bb) | > 0, ≤ 10.000 |
| `effective_stack` | `float` (bb) | ≥ 0, ≤ 10.000 |

Chave canônica: board com flop ordenado (turn/river na posição); ranges como vetor de pesos.

### TreeConfig

| Campo | Tipo | Regras |
|-------|------|--------|
| `name` | `str \| None` | 1–60 caracteres se presente (configurações salvas) |
| `bet_sizes` | `dict[Street, dict[Position, list[float]]]` | frações do pote, cada uma em (0, 10]; até 5 por lista |
| `raise_sizes` | `dict[Street, dict[Position, list[float]]]` | frações do pote após o call, (0, 10]; até 5 |
| `max_raises_per_street` | `int` | 0–6 |
| `allin_threshold` | `float` | (0, 1]; aposta ≥ threshold × stack restante vira all-in |
| `add_allin_action` | `bool` | padrão `False` |
| `allow_donk` | `bool` | padrão `False` |

Padrão (FR-010): bets 33% e 75%, raise 100%, 3 raises, threshold 0,67, sem all-in extra, sem
donk. Regras de geração: FR-006/FR-008 (raise mínimo, unificação de valores iguais).

### GameTree (vetorizada, interna)

- `DecisionNode`: `id`, `player ∈ {OOP, IP}`, `actions: list[Action]`, `pot`, `stacks`,
  `parent`, `children`, `regret_offset`, `strategy_offset` (índices nos arrays planos).
- `ChanceNode`: `street`, `cards: list[Card]` canônicas com `weight` (tamanho da órbita), mapa
  de permutação de naipes para cartas não canônicas.
- `TerminalNode`: `kind ∈ {fold, showdown}`, `pot`, `winner_if_fold`.
- `Action`: `kind ∈ {check, bet, call, raise, fold, allin}`, `amount_bb`, `pot_fraction`,
  `label` (ex.: `"Bet 75% (7,5 bb)"`), `id` estável (ex.: `x`, `b75`, `r100`, `c`, `f`, `a`).
- **Caminho de nó** (`NodePath`): sequência de ids de ação e cartas, ex.
  `["x", "b75", "c", "Kh", "x"]`; é o endereço público de um nó.

### SolverArrays (interna)

| Array | Forma | Tipo |
|-------|-------|------|
| `regrets` | Σ_n A(n)·C(p(n)) | float32 |
| `strategy_sum` | Σ_n A(n)·C(p(n)) | float32 |
| `showdown_rank` / `showdown_order` | boards de river × combos | int32 |

### SolveParams

| Campo | Tipo | Regras |
|-------|------|--------|
| `algorithm` | `Literal["dcfr", "cfr_plus", "linear_cfr"]` | padrão `dcfr` |
| `alpha`, `beta`, `gamma` | `float` | padrão 1,5 / 0 / 2 (DCFR) |
| `target_exploitability_pct` | `float` | (0, 100]; padrão 0,5 |
| `time_limit_s` | `float` | (0, 86.400]; padrão por street do board: river 60 s, turn 120 s, flop 900 s |
| `max_iterations` | `int \| None` | para testes determinísticos |
| `seed` | `int` | 0..2⁶⁴−1; registrado mesmo que o DCFR não amostre |

### Progress (evento)

`iteration: int`, `exploitability_pct: float | None` (None até a primeira medição),
`exploitability_iteration: int | None`, `elapsed_s: float`, `iterations_per_s: float`,
`status: SolveStatus`.

### Solution

| Campo | Tipo |
|-------|------|
| `meta` | `SolutionMeta` (abaixo) |
| `strategy` | float32[Σ_n A(n)·C(p(n))] — estratégia média normalizada |
| `ev` | float32[Σ_n C(p(n))] — EV (bb) de cada combo do jogador da vez em cada nó de decisão |
| `equity` | float32[Σ_n C(p(n))] — equity all-in do combo contra o range do oponente no nó (R15) |
| `node_offsets` | int64[nº de nós de decisão + 1] — início de cada nó em `strategy` |
| `combo_offsets` | int64[nº de nós de decisão + 1] — início de cada nó em `ev`/`equity` |
| `exploitability_history` | float64[k, 3] — (iteração, tempo s, explotabilidade %) |

`SolutionMeta`: `format_version` (`"1.0"`), `engine_version`, `input_hash` (SHA-256),
`spot`, `tree_config`, `solve_params`, `iterations`, `final_exploitability_pct`, `stop_reason`,
`created_at` (ISO 8601 UTC).

**Invariantes** (SC-005): para todo nó e combo com reach > 0, Σ ações `strategy` = 1 ± 1e-4; a
média de `ev` ponderada pelo reach é consistente com o EV agregado do nó (± 1e-3 bb).

### NodeView (leitura e agregação, ≤ 200 ms — R15)

`path`, `player`, `pot`, `stacks`, `actions[]` com `aggregate_frequency` e `combos`,
`hands[]` (169 células: frequências por ação, EV médio, equity média, combos efetivos),
`combos[]` (por combo: frequências, `ev_bb`, `equity`, `reach_weight`), `ranges` dos dois
jogadores que chegam ao nó, `is_terminal`, `next_street_cards` (se transição).

---

## Ciclo de vida de um solve

```text
            submit
  (novo) ─────────► queued ──► running ◄──► paused
                      │          │  │          │
                      │ cancel   │  │ stop     │ stop / cancel
                      ▼          │  ▼          ▼
                  cancelled ◄────┘ stopping ─► (stopped | cancelled)
                                 │
                                 ├─► finalizing ─► completed   (alvo atingido ou tempo-limite)
                                 └─► failed      (erro, OOM, worker sem resposta, servidor reiniciado)

  completed | stopped ── retenção expirada (R14) ──► expired   (arquivos removidos)
```

- `finalizing`: fase final do job (estratégia média, EV e equity, gravação). Também ocorre antes
  de `stopped`.
- `stop_reason ∈ {target_reached, time_limit, user_stopped}` para `completed`/`stopped`.
- Apenas `completed` e `stopped` têm solução e aceitam consulta de nós, fixação e exportação.
- Soluções importadas entram como `completed` com `origin = "import"`.
- `queue_position` (derivado): posição FIFO entre os solves `queued`; o solve ativo
  (`running`, `paused`, `stopping`, `finalizing`) ocupa a raia `solve`.

## Jobs auxiliares (raia `aux`)

`AuxJob`: `id`, `kind ∈ {export, import, cleanup}`, `status ∈ {queued, running, completed,
failed, cancelled}`, `solve_id` (export: origem; import: solve criado), `progress` ∈ [0, 1],
`result_path` (export), `error_code`, `error_detail`, timestamps. Arquivos de exportação expiram
24 h depois de prontos.

---

## Persistência (SQLite, SQLAlchemy 2)

### `tree_configs`

| Coluna | Tipo | Regras |
|--------|------|--------|
| `id` | UUID (texto) | PK |
| `name` | texto | único, 1–60 caracteres |
| `config_json` | JSON | `TreeConfig` validado |
| `created_at`, `updated_at` | datetime UTC | |

### `solves`

| Coluna | Tipo | Regras |
|--------|------|--------|
| `id` | UUID (texto) | PK; é também o id do job de solve |
| `input_hash` | texto(64) | indexado; não único (pode haver solves cancelados repetidos) |
| `status` | texto | enum do ciclo de vida |
| `origin` | texto | `solve` \| `import` |
| `spot_json`, `tree_config_json`, `params_json` | JSON | snapshot imutável das entradas (R13) |
| `estimated_bytes` | inteiro | memória estimada (R3) |
| `iterations` | inteiro | |
| `exploitability_pct` | real \| nulo | última medição |
| `stop_reason` | texto \| nulo | |
| `solution_dir` | texto \| nulo | relativo a `GTO_DATA_DIR/solutions/` |
| `size_bytes` | inteiro \| nulo | tamanho em disco da solução (FR-030) |
| `pinned` | booleano | padrão `false` (FR-029) |
| `last_used_at` | datetime UTC \| nulo | atualizado conforme R14 |
| `error_code`, `error_detail` | texto \| nulo | para `failed` |
| `created_at`, `started_at`, `finished_at` | datetime UTC | |

`expires_at` = `last_used_at + GTO_SOLUTION_RETENTION_DAYS` quando `pinned = false`; calculado,
não armazenado.

### `aux_jobs`

| Coluna | Tipo | Regras |
|--------|------|--------|
| `id` | UUID (texto) | PK |
| `kind` | texto | `export` \| `import` \| `cleanup` |
| `status` | texto | ver `AuxJob` |
| `solve_id` | UUID \| nulo | FK `solves.id` |
| `progress` | real | 0–1 |
| `result_path` | texto \| nulo | relativo a `GTO_DATA_DIR/exports/` |
| `error_code`, `error_detail` | texto \| nulo | |
| `created_at`, `finished_at` | datetime UTC | |

O histórico de explotabilidade fica nos arquivos da solução (e em memória durante a execução),
não no banco. Ranges salvos (`saved_ranges`) pertencem à feature 001.

### Arquivos

```text
$GTO_DATA_DIR/
├── gto.sqlite3
├── solutions/
│   └── <input_hash>/            # armazenamento interno, .npy sem compressão (mmap)
│       ├── meta.json
│       ├── strategy.npy  ev.npy  equity.npy
│       ├── node_offsets.npy  combo_offsets.npy
│       └── exploitability_history.npy
├── exports/
│   └── <aux_job_id>.npz         # formato de troca, comprimido; expira em 24 h
└── imports/                     # uploads em andamento (temporários)
```
