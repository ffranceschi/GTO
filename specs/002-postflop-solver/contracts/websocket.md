# Contrato WebSocket — Eventos de jobs

**Endpoint**: `GET /api/v1/jobs/{job_id}/events` (upgrade para WebSocket)

Vale para todos os jobs assíncronos (Princípio V): **solves** (o `job_id` é o id do solve) e
**jobs auxiliares** (`export`, `import`, `cleanup`).

- Direção: **somente servidor → cliente**. Mensagens do cliente são ignoradas, exceto o
  fechamento. Comandos (pausar/retomar/parar/cancelar) usam REST
  ([openapi.yaml](./openapi.yaml)).
- Formato: um objeto JSON por frame de texto, UTF-8.
- Todas as mensagens têm `type`, `job_id`, `job_kind` (`solve` | `export` | `import` |
  `cleanup`) e `seq` (inteiro monotônico por job, começa em 0). O cliente descarta mensagens
  com `seq` menor ou igual ao último recebido.
- Cadência: `progress` pelo menos 1×/s enquanto o job está `running` ou `finalizing`, no máximo
  5×/s (o servidor agrega).
- Job inexistente: o servidor aceita e fecha com código `4404`. Erro interno: `1011`.
- Ao terminar (`completed`, `stopped`, `cancelled`, `failed`), o servidor envia `finished` e
  fecha com `1000`.
- Reconexão: o cliente reconecta com backoff (1 s, 2 s, 4 s… até 10 s); a primeira mensagem de
  toda conexão é sempre um `snapshot`. Como o job roda no servidor, fechar e reabrir a interface
  não interrompe o job.

## Mensagens de solve (`job_kind = "solve"`)

### `snapshot`

Enviado ao conectar. Estado completo para (re)construir a tela.

```json
{
  "type": "snapshot",
  "job_id": "8c0f2a5e-1d6b-4c1e-9f0a-2b7d3e4f5a6b",
  "job_kind": "solve",
  "seq": 0,
  "status": "running",
  "queue_position": null,
  "iteration": 1840,
  "exploitability_pct": 0.83,
  "exploitability_iteration": 1800,
  "elapsed_s": 12.4,
  "iterations_per_s": 148.4,
  "target_exploitability_pct": 0.5,
  "time_limit_s": 60.0,
  "history": [[100, 0.7, 12.9], [400, 2.8, 3.1], [1800, 12.1, 0.83]]
}
```

`history`: lista de `[iteração, tempo_s, explotabilidade_pct]` (todas as medições até agora).
`exploitability_pct` é `null` antes da primeira medição. Para um solve `queued`, só `status` e
`queue_position` são relevantes.

### `progress`

```json
{
  "type": "progress",
  "job_id": "8c0f2a5e-…",
  "job_kind": "solve",
  "seq": 17,
  "iteration": 2010,
  "exploitability_pct": 0.79,
  "exploitability_iteration": 2000,
  "elapsed_s": 13.6,
  "iterations_per_s": 147.8
}
```

Quando `exploitability_iteration` muda, o cliente acrescenta o ponto ao gráfico (FR-017).
Durante `finalizing`, `progress` traz `finalize_fraction` (0–1) em vez dos campos de iteração.

### `status`

Mudança de estado (`queued → running`, `running ⇄ paused`, `stopping`, `finalizing`) ou de
posição na fila.

```json
{ "type": "status", "job_id": "8c0f…", "job_kind": "solve", "seq": 18, "status": "queued", "queue_position": 2 }
```

- `stopping`: comando de parar/cancelar aceito, aguardando o fim do bloco atual (≤ 1 s,
  SC-008).
- `finalizing`: cálculo da estratégia média, EV e equity e gravação da solução.

### `finished`

```json
{
  "type": "finished",
  "job_id": "8c0f…",
  "job_kind": "solve",
  "seq": 42,
  "status": "completed",
  "stop_reason": "target_reached",
  "iterations": 2620,
  "exploitability_pct": 0.49,
  "elapsed_s": 17.7,
  "target_reached": true,
  "size_bytes": 1843200
}
```

- `status ∈ {completed, stopped, cancelled, failed}`.
- `stop_reason ∈ {target_reached, time_limit, user_stopped}` ou `null` para
  `cancelled`/`failed`.
- `target_reached = false` com `time_limit` gera o aviso "alvo não alcançado" na UI.

## Mensagens de jobs auxiliares (`export`, `import`, `cleanup`)

Todos publicam `progress` (fração 0–1) pelo menos 1×/s enquanto rodam; no `cleanup`, a fração
é a das soluções já avaliadas.

```json
{ "type": "snapshot", "job_id": "f3…", "job_kind": "export", "seq": 0, "status": "running", "progress": 0.35, "solve_id": "8c0f…" }
{ "type": "progress", "job_id": "f3…", "job_kind": "export", "seq": 4, "progress": 0.62 }
{ "type": "finished", "job_id": "f3…", "job_kind": "export", "seq": 9, "status": "completed",
  "download_url": "/api/v1/aux-jobs/f3…/file", "file_expires_at": "2026-10-13T15:02:11Z" }
{ "type": "finished", "job_id": "a1…", "job_kind": "import", "seq": 7, "status": "completed", "solve_id": "b7…" }
```

## `error`

```json
{
  "type": "error",
  "job_id": "8c0f…",
  "job_kind": "solve",
  "seq": 43,
  "code": "worker_sem_resposta",
  "detail": "O processo do solver parou de responder e foi encerrado."
}
```

Sempre seguido de `finished` com `status = "failed"`.

## Códigos de erro (`code`)

| code | Significado |
|------|-------------|
| `worker_sem_resposta` | worker não respondeu a um comando em 10 s |
| `memoria_insuficiente` | falha de alocação durante o job |
| `servidor_reiniciado` | o servidor reiniciou com o job ativo |
| `arquivo_invalido` | importação: arquivo corrompido ou de outro tipo |
| `versao_incompativel` | importação: `format_version` não suportada |
| `erro_interno` | exceção inesperada |
