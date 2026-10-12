# Quickstart — validação da feature 001 (ranges e equity)

Contratos: [openapi.yaml](./contracts/openapi.yaml), [websocket.md](./contracts/websocket.md).
Modelo: [data-model.md](./data-model.md). Pré-requisitos e setup: os mesmos da 002
(`uv sync --all-packages --all-groups`, `cd web && npm ci`).

## 1. Motor (sem API nem UI)

```bash
uv run pytest engine/tests -k "equity or range"
```

Esperado:
- `test_equity_reference`: AA vs KK pré-flop exato = 81,95% ± 0,1 pp (SC-001); conjunto de
  confrontos mão vs mão e mão vs range em todas as streets igual à força bruta do `phevaluator`.
- `test_equity_montecarlo::test_cobertura_da_margem_sc005`: em 200 sementes, o valor exato cai
  dentro da margem exibida em ≥ 95% (SC-005).
- `test_equity_montecarlo::test_mesma_semente_mesmo_resultado_com_1_e_4_threads` e
  `test_equity_exact`: mesma entrada (+ semente) ⇒ resultado idêntico com 1 e 4 threads.
- `test_equity_exact::test_multiway_empate_divide_e_soma_1`: empate entre k jogadores conta 1/k;
  soma das equities = 1.
- `test_equity_distribution` e `property/test_equity_properties`: agregação por mão e propriedades
  (soma 1, simetria, naipes, exato × Monte Carlo).

Benchmarks no hardware de referência (8 núcleos, 16 GB):

```bash
uv run pytest engine/tests -m benchmark_ref -k equity -s
```

Esperado: SC-002 range vs range no flop (100% cada) exato < 2 s; SC-003 mão vs mão exato < 1 s;
Monte Carlo heads-up ≥ 5 milhões de amostras/s; parse/format/estimativa ≤ 200 ms.

## 2. API

```bash
B=http://127.0.0.1:8000/api/v1
curl -s -X POST $B/ranges/parse -H 'content-type: application/json' \
  -d '{"notation":"22+, A2s+, KTo+"}' | jq '.combos, .pct_of_total'          # 162, 0.1222
curl -s -X POST $B/equity/estimate -H 'content-type: application/json' \
  -d '{"participants":[{"notation":"AA"},{"notation":"KK"}]}' | jq             # method: exact
J=$(curl -s -X POST $B/equity-jobs -H 'content-type: application/json' \
  -d '{"participants":[{"notation":"AA"},{"notation":"KK"}]}' | jq -r .id)
websocat ws://127.0.0.1:8000/api/v1/jobs/$J/events                             # snapshot … finished
curl -s $B/equity-jobs/$J | jq '.result.participants[].equity'                 # 0.8195, 0.1805
```

Monte Carlo com parada e cancelamento (≤ 1 s):

```bash
J=$(curl -s -X POST $B/equity-jobs -H 'content-type: application/json' -d '{"participants":[
  {"notation":"22+, A2+, K2+"},{"notation":"22+, A2s+"},{"notation":"QQ+, AK"}],"seed":7}' | jq -r .id)
curl -s -X POST $B/equity-jobs/$J/stop       # resultado parcial "Estimado", stop_reason user_stopped
```

Ranges salvos:

```bash
curl -s -X POST $B/saved-ranges -H 'content-type: application/json' \
  -d '{"name":"BTN open 100bb","notation":"22+, A2s+, KTo+, KQo:0.5"}' | jq .id
curl -s $B/saved-ranges | jq '.[].name'
```

## 3. Front

```bash
(cd web && npm run gen:api && npm test && npx playwright test)
```

Cenários manuais:
- Montar `22+, A2s+, KTo+` só pela grade em < 30 s (SC-009); conferir 162 combos (12,2%).
- Board `As 7d 2c` e range `AA` ⇒ 3 combos.
- Mudar um range com o cálculo rodando ⇒ cancelado e aviso "Entradas alteradas".
- Salvar "BTN open 100bb", recarregar a página e carregar de volta, idêntico (SC-010); o mesmo
  range aparece no formulário do solver.

## Resultados medidos (2026-10-12)

Máquina: Apple M1 Max (10 núcleos, 32 GB) — mais rápida que o hardware de referência (8 núcleos,
16 GB); os orçamentos valem para o de referência.

| Etapa | Resultado |
|-------|-----------|
| `pytest engine/tests -k "equity or range"` | 92 passaram |
| SC-001 AA vs KK pré-flop | 81,9461% exato em 1,28 s |
| SC-002 100% vs 100% no flop, exato | 0,08 s |
| SC-003 mão vs mão (0/3/4/5 cartas) | 0,53 s / 0,01 s / 0,01 s / 0,01 s |
| Monte Carlo heads-up | 11,5 M amostras/s |
| Monte Carlo 6-way até ±0,1 pp | 0,3 s (1,0 M amostras) |
| Taxa do kernel exato medida no warm-up | ≈ 29–33 M avaliações/s (estimativa AA vs KK: 1,06 s ⇒ exato) |
| API (seção 2) | `162`, `0,1222`; AA vs KK `0,8195 / 0,1805` em 1,2 s; `stop` ⇒ `user_stopped` com resultado parcial (semente 7, ~1 M amostras); range salvo na notação canônica (`22+, A2s+, KJo-KTo, KQo:0.5`, 156 combos) |
| Parar / cancelar Monte Carlo 6-way (runner de processos) | < 1 s (`test_equity_latency`) |
| `npm run gen:api` contra a API ao vivo | schema idêntico ao versionado |
| Vitest / Playwright | 17 / 15 passaram |
| SC-009 montar `22+, A2s+, KTo+` pela grade | automatizado (arrasto + 16 cliques): 1,6 s. **Validação manual por uma pessoa (< 30 s) pendente** |

Observação de implementação: com a camada de threads `workqueue` do Numba, cada lançamento
paralelo custa ~6,5 ms; o exato agrupa o trabalho em blocos de ≥ ~1 M avaliações (no máximo 50)
para que casos pequenos (ex.: river) não paguem 50 lançamentos.
