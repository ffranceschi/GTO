# WebSocket — eventos de jobs de equity

Mesmo endpoint e regras gerais da 002 (`specs/002-postflop-solver/contracts/websocket.md`):
`GET /api/v1/jobs/{job_id}/events`, só servidor → cliente, `snapshot` primeiro, `seq` monotônico,
`progress` ≥ 1×/s e ≤ 5×/s, `finished` e fechamento 1000, 4404 para job inexistente.

Para jobs de equity, `job_kind = "equity"`. O WebSocket leva só **progresso**; o resultado
completo é lido em `GET /api/v1/equity-jobs/{id}` depois do `finished`.

## `progress` — Monte Carlo

```json
{
  "type": "progress", "job_id": "…", "job_kind": "equity", "seq": 7,
  "method": "monte_carlo",
  "samples": 2400000,
  "elapsed_s": 1.4,
  "samples_per_s": 1714285,
  "equities": [0.4821, 0.5179],
  "margins": [0.0006, 0.0006],
  "target_margin": 0.001
}
```

## `progress` — exato

```json
{ "type": "progress", "job_id": "…", "job_kind": "equity", "seq": 3, "method": "exact",
  "fraction": 0.42, "elapsed_s": 0.4 }
```

## `finished`

```json
{ "type": "finished", "job_id": "…", "job_kind": "equity", "seq": 12, "status": "completed",
  "stop_reason": "target_reached" }
```

`status ∈ {completed, cancelled, failed}`; `stop_reason ∈ {exact, target_reached, time_limit,
user_stopped}` ou `null`. Códigos de erro novos: `confronto_improvavel` (taxa de rejeição do Monte
Carlo acima de 99%).
