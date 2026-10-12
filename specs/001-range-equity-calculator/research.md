# Research — 001 Editor de Ranges e Calculadora de Equity

**Data**: 2026-10-12 | **Plano**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

A stack é a mesma da feature 002 (Python 3.12 + uv, `gto_engine` com Numba, FastAPI, SQLite,
React + Vite). Este documento registra só as decisões novas desta feature. Formato: **Decisão /
Racional / Alternativas**.

## R1. Reaproveitamento da 002

**Decisão**: reaproveitar sem duplicar:

| Já existe (002) | Uso na 001 |
|-----------------|------------|
| `gto_engine.cards`, `evaluator` (tabelas + `eval7`, validado exaustivamente e contra `phevaluator`) | avaliação de mãos da equity |
| `gto_engine.ranges` (notação, `format_range` com ida e volta) | parse/format, contagem de combos |
| `POST /api/v1/ranges/parse` | contagem com bloqueios (estendido com `dead_cards`, R8) |
| `LaneJobRunner`, WebSocket `/jobs/{id}/events`, erros RFC 9457, SQLite | jobs de equity e ranges salvos |
| `RangeGrid` (SVG somente leitura), cliente `openapi-fetch`, `jobEvents.ts`, i18n pt-BR | base do editor interativo e das telas |

**Racional**: Princípio VII (simplicidade) e um único avaliador validado (Princípio I).

## R2. Enumeração exata

**Decisão**: dois kernels Numba, escolhidos pelo formato da entrada:

1. **Heads-up (2 participantes, ranges ou mãos)**: para cada board completo possível (completar o
   board atual com as cartas restantes), avaliar as mãos dos dois ranges e acumular vitória,
   empate e total por par compatível (sem cartas repetidas), ponderado pelos pesos. Paralelizado
   com `prange` sobre a **primeira carta** da completação: partição fixa, um acumulador por
   fatia e soma final em ordem fixa (determinístico — Princípio VI).
   - Para ranges grandes, a comparação par a par vira a **varredura ordenada com remoção de
     cartas** já usada no showdown do solver (`showdown_sums`, O(n log n) por board).
2. **Multiway (3 a 6 participantes)**: enumeração do produto das mãos compatíveis × boards
   completos, mesmo esquema de paralelismo; só é escolhida quando a estimativa (R4) cabe em 2 s,
   na prática quando há mãos específicas ou ranges muito pequenos.

Saída por participante: vitórias, empates (contagem fracionária: empate entre k divide o pote em
1/k — FR-019) e total; por combo: os mesmos acumuladores.

**Medição do protótipo** (M1 Max, 10 núcleos): AA vs KK pré-flop, exato = **81,946%** (win
81,715%, tie 0,463%) em **1,05 s**; AhKh vs QsQd = 46,214% em 0,18 s. O protótipo avaliava
também os boards bloqueados; o kernel final enumera só cartas livres e reaproveita a força do
board por combo, o que deve dar folga para os orçamentos no hardware de referência (8 núcleos).

**Alternativas**: tabelas pré-computadas de equity pré-flop (169×169) — cobrem só mão vs mão sem
board e viram dados não verificados; enumeração em Python — proibida pelo Princípio V.

## R3. Monte Carlo

**Decisão**:
- **Amostragem**: a cada amostra, sorteia um combo por participante proporcionalmente ao peso
  (busca binária na soma acumulada), **rejeita** se houver carta repetida entre participantes e
  completa o board com cartas livres. A rejeição produz exatamente a distribuição conjunta
  correta (produto dos pesos restrito a combinações compatíveis). Se a taxa de rejeição passar
  de 99% num bloco, o job termina com erro `confronto_improvavel` em pt-BR.
- **PRNG**: xoshiro256** implementado em Numba; cada bloco *b* e fatia *f* recebem a semente
  `splitmix64(seed, b, f)`. Número fixo de fatias (64) por bloco ⇒ o resultado independe do nº de
  threads (Princípio VI). A semente aparece no resultado e pode ser informada (FR-022).
- **Margem de erro**: para cada participante, a equity por amostra é 1 (vence), 1/k (empata com
  k) ou 0; margem = 1,96 × desvio-padrão amostral / √n (IC de 95%). Mesmo cálculo por mão e por
  combo com as amostras daquele combo (FR-023).
- **Parada** (FR-018): margem de todos os participantes ≤ alvo (padrão ±0,1 pp, entre ±0,05 e ±1
  pp), tempo-limite (padrão 60 s) ou o jogador parar; o motivo vai no resultado.
- **Blocos de ~200 ms** com o mesmo controle cooperativo da 002 (`SolveControl`) e progresso
  publicado a cada bloco (amostras, margens, tempo).

**Validação** (SC-005): em casos com valor exato conhecido, o valor exato fica dentro da margem
exibida em ≥ 95% das execuções (teste com 200 sementes; tolerância binomial).

## R4. Escolha entre exato e Monte Carlo (FR-016)

**Decisão**: antes de criar o job, a API estima o custo da enumeração exata:

```text
avaliações = nº de boards completos × Σ mãos (heads-up)
           = nº de boards completos × nº de combinações compatíveis de mãos × participantes (multiway)
tempo estimado = avaliações / taxa de avaliações por segundo
```

A **taxa** é medida no warm-up do worker (benchmark de 0,1 s do kernel exato) e guardada; sem
medição, usa-se uma taxa conservadora fixa. Exato se tempo estimado ≤ 2 s; senão Monte Carlo.
O jogador pode forçar `exact` ou `monte_carlo`; forçar exato acima de 2 s exige confirmação na UI
com o tempo estimado.

A estimativa é **contagem** (combinações), sem enumerar boards: é cálculo leve, com benchmark de
≤ 200 ms no pior caso (6 ranges de 100%, board vazio) — Princípio V.

## R5. Raia de execução para equity

**Decisão**: terceira raia no `LaneJobRunner`: **`equity`** (1 worker). Equity não espera um solve
de 10 min na raia `solve`, nem atrasa exportações na `aux`.

**Racional**: jobs de equity duram de milissegundos a 60 s e são interativos; a raia `aux` é
para I/O curto. O runner já é genérico nas raias (mudança pequena). Justificado em Complexity
Tracking do plano.

**Alternativas**: usar a raia `aux` (exportação esperaria até 60 s); rodar na requisição
(proibido para cálculo pesado — Princípio V).

## R6. Cancelamento ao alterar entradas (Clarifications Q3)

**Decisão**: o front guarda o id do job ativo; qualquer alteração de participante, board ou
método envia `DELETE /api/v1/equity-jobs/{id}` (efeito ≤ 1 s, blocos de 200 ms) e mostra
"Entradas alteradas". Novo cálculo só com "Calcular". O servidor descarta resultados de jobs
cancelados.

## R7. Ranges salvos (Clarifications Q1)

**Decisão**: tabela `saved_ranges` no SQLite da 002 (`name` único 1–60, `notation` canônica,
`combos`, timestamps). A notação canônica é exata (ida e volta comprovada na 002, inclusive pesos
e combos específicos), então guardar a notação preserva os pesos por combo (FR-026). CRUD
`/api/v1/saved-ranges`, com 409 `nome_em_uso` salvo `overwrite`, como as configurações de árvore.

## R8. Contagem de combos com bloqueios (FR-011) e conversão grade → texto

**Decisão**:
- `POST /api/v1/ranges/parse` ganha `dead_cards` (board + cartas das mãos específicas dos outros
  participantes); a contagem desconta todos. Compatível com o uso atual (campo opcional).
- `POST /api/v1/ranges/format` (novo): pesos (1326) → notação canônica. A grade edita pesos no
  cliente e pede o texto ao servidor (debounce 150 ms), mantendo um único formatador (o do motor).

Ambos são cálculo leve (≤ 200 ms, já coberto pelo benchmark de parse/format).

**Alternativa rejeitada**: reimplementar a notação em TypeScript — duplicaria a lógica validada
e criaria risco de divergência.

## R9. Resultado e retenção

**Decisão**: o resultado completo (por participante, por mão e por combo) fica em
`equity_jobs.result_json` e é lido com `GET /api/v1/equity-jobs/{id}` após o `finished` do
WebSocket (o WebSocket só leva progresso). Resultados ficam 24 h e são removidos pelo job
`cleanup` da 002 (são recalculáveis e determinísticos).

Tamanho: até 6 × 1326 combos × poucos campos ≈ algumas centenas de KB de JSON.

## R10. Referências de validação (Princípio I)

| Caso | Valor | Fonte | Tolerância |
|------|-------|-------|------------|
| AA vs KK pré-flop (todos os combos) | 81,95% / 18,05% | enumeração exata, conferida pelo oráculo independente `phevaluator` (força bruta) | ±0,1 pp (SC-001) |
| Mão vs mão e mão vs range (conjunto de ~20 confrontos em todas as streets) | valores calculados por força bruta com `phevaluator` | oráculo independente | ±1e-9 (exato) |
| Contagens de combos (`22+, A2s+, KTo+` = 162; AA com um ás no board = 3) | — | combinatória | exato |

Os valores "tabelados" da constituição (AA vs KK ≈ 81,9%) são confirmados pelo oráculo; os demais
casos usam o oráculo em vez de números copiados de tabelas externas, para que cada valor tenha
fonte verificável (`engine/tests/reference/REFERENCES.md` é estendido).

## R11. Editor interativo (FR-005 a FR-010)

**Decisão**: `RangeEditor` no front, sobre o `RangeGrid`:
- clique e arrasto com *pointer events*; a 1ª célula define a ação (selecionar ou remover);
- peso ativo 0–100% em passos de 1%; faixa proporcional na célula mostra o peso;
- detalhe da célula com os combos de naipe (4/6/12) e peso por combo;
- texto ↔ grade sincronizados via `/ranges/parse` e `/ranges/format` (R8);
- "Limpar" e "Tudo"; carregar/salvar ranges nomeados.

O mesmo componente substitui o campo de texto no formulário do solver (T098 da 002).

## R12. Orçamentos (hardware de referência: 8 núcleos, 16 GB)

| Medida | Orçamento |
|--------|-----------|
| SC-001 AA vs KK pré-flop exato | resultado exato (≤ 2 s pela regra do R4) |
| SC-002 heads-up range vs range no flop (até 100% cada), exato | < 2 s |
| SC-003 mão vs mão em qualquer street, exato | < 1 s |
| Monte Carlo heads-up | ≥ 5 milhões de amostras/s |
| Monte Carlo 6-way, ranges amplos, até ±0,1 pp | < 60 s |
| Parse, format, estimativa (na requisição) | ≤ 200 ms |
| Cancelar / progresso | ≤ 1 s / ≥ 1×/s |
