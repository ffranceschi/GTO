# Quickstart — validação da feature 002 (Solver postflop)

Guia de execução e validação ponta a ponta. Contratos: [openapi.yaml](./contracts/openapi.yaml),
[websocket.md](./contracts/websocket.md), [engine-api.md](./contracts/engine-api.md). Modelo:
[data-model.md](./data-model.md).

## Pré-requisitos

- Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+ (front), Docker (opcional).
- Feature 001 implementada (avaliador de mãos, ranges, notação), pois o solver a reutiliza.

```bash
uv sync --all-packages            # workspace: engine + api
(cd web && npm ci)
```

## 1. Motor isolado (sem API nem UI) — Princípios I, II, III

```bash
uv run pytest engine/tests -m "not benchmark_ref"
```

Esperado:
- `test_kuhn_equilibrium`: valor do jogo −1/18 ± 0,001; explotabilidade < 0,1% do pote.
- `test_leduc_reference`: valor ≈ −0,0856 ± 0,005; explotabilidade < 0,1% do pote.
- `test_river_reference_quality`: spot de referência de river < 1% do pote dentro do nº fixo de
  iterações.
- `test_determinism`: duas execuções ⇒ `strategy` idêntica byte a byte.
- `test_solution_roundtrip`: diretório → `.npz` → diretório ⇒ arrays e `node_view` idênticos.
- `test_estimate_accuracy`: estimativa de memória dentro de ±15%.
- `test_engine_has_no_web_imports` (ruff `TID251` também no CI).

## 2. Orçamentos no hardware de referência — Princípio V

```bash
uv run pytest engine/tests -m benchmark_ref --benchmark-only
```

Esperado (8 núcleos/16 GB, ver research R9): river < 30 s; turn padrão < 60 s; flop reduzido
< 10 min e ≤ 4 GiB; Kuhn < 1 s; Leduc < 30 s; `node_view` ≤ 200 ms no maior flop aceito.

## 3. API

```bash
uv run uvicorn gto_api.main:app --host 127.0.0.1 --port 8000
curl -s localhost:8000/api/v1/health            # {"status":"ready",...} após o warm-up
```

Estimar a árvore e criar o solve de referência de river:

```bash
curl -s -X POST localhost:8000/api/v1/trees/estimate -H 'content-type: application/json' \
  -d @engine/tests/fixtures/river_reference.json | jq '.within_limit, .estimated_bytes'

SOLVE=$(curl -s -X POST localhost:8000/api/v1/solves -H 'content-type: application/json' \
  -d @engine/tests/fixtures/river_reference_solve.json | jq -r .id)
```

Acompanhar o progresso (qualquer cliente WebSocket, ex.: `websocat`):

```bash
websocat ws://localhost:8000/api/v1/jobs/$SOLVE/events
```

Esperado: `snapshot`, depois `progress` ≥ 1×/s, `status: finalizing` e por fim `finished` com
`stop_reason = "target_reached"` e `exploitability_pct ≤ 0.5`. Fechar o `websocat` e reconectar
não interrompe o solve (o primeiro frame é um novo `snapshot`).

Fila (FR-027): criar um segundo solve enquanto o primeiro roda ⇒ `status = "queued"`,
`queue_position = 1`; ele inicia sozinho quando o primeiro termina.

Controle (cada um deve refletir em `status` em < 1 s):

```bash
curl -s -X POST localhost:8000/api/v1/solves/$SOLVE/pause
curl -s -X POST localhost:8000/api/v1/solves/$SOLVE/resume
curl -s -X POST localhost:8000/api/v1/solves/$SOLVE/stop
```

Navegar e exportar/importar:

```bash
curl -s "localhost:8000/api/v1/solves/$SOLVE/nodes?path=" | jq '.actions'
curl -s "localhost:8000/api/v1/solves/$SOLVE/nodes?path=x/b100" | jq '.player, .actions'
EXP=$(curl -s -X POST localhost:8000/api/v1/solves/$SOLVE/exports | jq -r .id)   # 202, job aux
websocat ws://localhost:8000/api/v1/jobs/$EXP/events                              # até finished
curl -s -o sol.npz localhost:8000/api/v1/aux-jobs/$EXP/file
IMP=$(curl -s -F file=@sol.npz localhost:8000/api/v1/solutions/import | jq -r .id)  # 202, job aux
curl -s localhost:8000/api/v1/aux-jobs/$IMP | jq '.status, .solve_id'
```

Esperado: frequências por combo somam 1; a solução importada retorna nós idênticos; a consulta
de nó responde em ≤ 200 ms; nenhum endpoint fica bloqueado durante exportação/importação.

Retenção (FR-028 a FR-030):

```bash
curl -s -X PATCH localhost:8000/api/v1/solves/$SOLVE -H 'content-type: application/json' \
  -d '{"pinned": true}' | jq '.pinned, .expires_at'        # true, null
curl -s localhost:8000/api/v1/storage | jq                  # total_bytes, retention_days = 30
GTO_SOLUTION_RETENTION_DAYS=0 uv run pytest api/tests -k retention   # expira não fixadas, preserva fixadas e ativas
```

Árvore grande demais:

```bash
curl -s -X POST localhost:8000/api/v1/solves -H 'content-type: application/json' \
  -d @engine/tests/fixtures/flop_default_tree.json | jq '.code'   # "arvore_grande_demais"
```

```bash
uv run pytest api/tests           # contrato (OpenAPI gerado ⊇ contracts/openapi.yaml), runner, WS
```

## 4. Front-end

```bash
(cd web && npm run gen:api && npm run dev)     # gera o cliente a partir do OpenAPI
(cd web && npm test && npx playwright test)
```

Cenário manual (SC-009, < 2 min): carregar ranges salvos para OOP/IP → board de river → pote 10,
stack 50 → árvore padrão → Resolver → ver progresso → pausar/retomar → ao fim, grade colorida
por ação na raiz → clicar `AKs` → navegar `Check › Bet 75%` → exportar.

## 5. Docker

```bash
docker build -t gto-api .
docker run -p 127.0.0.1:8000:8000 -v gto-data:/data gto-api   # só localhost (R16)
```

A primeira requisição após `health = ready` não deve sofrer compilação JIT (cache gravado no
build e warm-up no startup).
