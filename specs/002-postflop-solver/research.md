# Research — 002 Solver GTO Postflop Heads-Up

**Data**: 2026-10-12 (revisado após a constituição v2.0.0 e o clarify da spec) | **Plano**:
[plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Cada item segue o formato **Decisão / Racional / Alternativas consideradas**. A stack foi definida
pelo usuário em `/speckit.plan`; este documento justifica as escolhas em aberto e registra os
números que viram critérios de aceitação.

---

## R1. Algoritmo: CFR+ vs DCFR vs Linear CFR

**Decisão**: implementar **um único núcleo de Discounted CFR (DCFR)** parametrizado por
(α, β, γ), com atualizações alternadas (OOP, depois IP). Padrão de produção:
**DCFR(α=1,5, β=0, γ=2)**. CFR+ e Linear CFR saem do mesmo núcleo como configurações:

| Variante | Parâmetros no núcleo | Uso |
|----------|----------------------|-----|
| DCFR (padrão) | α=1,5; β=0; γ=2 | produção |
| Linear CFR | α=1; β=1; γ=1 | benchmark/comparação |
| CFR+ | regret positivo sem desconto e regret negativo zerado (α=∞, β=−∞), média com γ=2 (média ponderada quadrática; o CFR+ original usa linear, γ=1 também suportado) | teste de referência e comparação |

**Racional**:
- Na literatura (Brown & Sandholm, *Solving Imperfect-Information Games via Discounted Regret
  Minimization*, AAAI 2019) o DCFR(1,5; 0; 2) converge mais rápido que CFR+ e LCFR em jogos de
  poker de grande porte, sobretudo em árvores com ações muito ruins (ex.: folds com mão forte),
  porque desconta regrets negativos acumulados no início.
- Os três algoritmos diferem só nos pesos de desconto aplicados a regrets e à estratégia média;
  um núcleo parametrizado é **menos código** (Princípio VII) e permite comparar variantes pela
  explotabilidade (Princípio II) sem duplicar kernels.
- DCFR e CFR+ são **determinísticos** (não amostram): dado o número de iterações, o resultado é
  único (Princípio VI). A seed só afeta o Monte Carlo de equity (feature 001).
- Atualizações alternadas reduzem pela metade o trabalho por iteração "efetiva" e são o padrão
  dos solvers modernos.

**Alternativas consideradas**:
- *CFR vanilla*: convergência O(1/√T) muito lenta; descartado.
- *MCCFR (external/outcome sampling)*: útil quando a árvore não cabe na memória, mas introduz
  variância, exige seed por iteração e torna a explotabilidade ruidosa entre execuções; não
  resolve o gargalo real (memória de regrets). Descartado nesta feature.
- *PCFR+ / Predictive CFR*: promissor, porém com ganhos menos consistentes em poker e menos
  literatura de referência; pode ser avaliado depois usando a mesma infraestrutura de
  benchmark.

**Validação**: o mesmo núcleo resolve Kuhn e Leduc representados na mesma forma vetorial
(estado público × vetor de mãos privadas), ver R7.

---

## R2. Núcleo: Numba vs Cython vs Rust (PyO3)

**Decisão**: **Numba** (`@njit(cache=True, nogil=True, fastmath=False)`, `prange` onde não há
redução em ponto flutuante entre threads), com kernels atrás de uma fronteira estreita
"arrays NumPy entram / arrays NumPy saem".

| Critério | Numba | Cython | Rust + PyO3 (maturin) |
|----------|-------|--------|------------------------|
| Desempenho em loops numéricos | ~C com LLVM | ~C | ~C, melhor controle de memória e SIMD |
| Paralelismo | `prange` pronto | OpenMP via `prange` (config de compilador) | rayon; GIL liberado com `allow_threads` |
| Linguagens no repositório | 1 (Python) | Python + dialeto Cython | Python + Rust |
| Build/CI | sem compilação AOT; JIT + cache | compilador C em todo ambiente | toolchain Rust + maturin; wheels por plataforma |
| Tipagem com mypy | kernels opacos para mypy | parcial | fronteira tipada via stubs `.pyi` |
| Custo de partida | compilação JIT (mitigada por `cache=True` e warm-up) | nenhum | nenhum |
| Velocidade de iteração no estudo dos algoritmos | alta | média | menor |

**Racional**:
- Princípio VII: mantém uma linguagem e zero etapas de compilação nativa no build, o que importa
  num projeto de estudo em que os algoritmos vão mudar muito.
- O gargalo do solver é aritmética densa em vetores de combos (multiplicar reach por estratégia,
  somar valores contrafactuais, varredura ordenada no showdown), um caso em que Numba gera código
  equivalente a C.
- `nogil=True` permite que a leitura e agregação de nós (R15) e os kernels de finalização rodem
  em threads sem segurar o GIL.
- O risco conhecido (latência de JIT) é tratado por `cache=True` + warm-up no startup (R8).

**Riscos e mitigação**:
- *Determinismo*: `fastmath=False` (sem reassociação de somas) e nenhuma redução de float
  compartilhada em `prange`; cada thread escreve em posições disjuntas. Somas por thread são
  combinadas em ordem fixa, sequencialmente.
- *mypy strict*: `numba` não tem stubs; configurar `ignore_missing_imports` só para `numba` e
  expor os kernels por wrappers Python tipados (`def solve_iterations(arrays: SolverArrays,
  n: int) -> None`).
- *Rota de saída*: se o flop exigir controle fino de memória (ex.: regrets em 16 bits com
  escala), os kernels podem ser portados para Rust sem mudar a API pública do `gto_engine`.

**Alternativas consideradas**: Cython (build nativo em todo ambiente, sem ganho de desempenho
relevante sobre Numba) e Rust/PyO3 (melhor teto de desempenho e memória, mas duas linguagens e
toolchain extra; reavaliar se o flop completo virar requisito).

---

## R3. Estimativa de memória por tamanho de árvore e limite da API

**Decisão**:

1. **Fórmula de estimativa** (implementada em `gto_engine.game.estimate`, sem alocar arrays e
   **sem percorrer a árvore nó a nó**, pois roda dentro da requisição e precisa ser cálculo leve
   segundo o Princípio V):
   - para cada street, enumera as **linhas de aposta** possíveis a partir de (pote, stack,
     sizings, limite de raises), que são poucas dezenas e dependem só de valores monetários;
   - agrupa as linhas que terminam a street com o mesmo (pote, stack) e multiplica pelo número de
     cartas canônicas do nó de chance seguinte (≤ 52, após o isomorfismo);
   - com memoização por (street, pote, stack), o custo não cresce com o número de nós; orçamento
     **≤ 200 ms** na maior árvore, verificado por benchmark;

   ```text
   bytes ≈ 1,2 × Σ_nós de decisão n [ A(n) × C(jogador(n)) × 8 ]  +  tabelas de showdown
   ```

   - `A(n)`: número de ações do nó; `C(p)`: combos com peso > 0 no range de `p` depois dos
     bloqueios do board inicial;
   - 8 bytes = regret acumulado (float32) + estratégia média acumulada (float32);
   - 1,2 = folga para vetores de reach/valores contrafactuais por profundidade, índices e
     metadados;
   - tabelas de showdown: para cada board de river alcançável, força da mão e ordem de cada combo
     (≈ 8 bytes × combos × boards de river; < 25 MB mesmo no flop);
   - nós de chance são multiplicados pelas cartas canônicas depois do isomorfismo de naipes
     (R5).

2. **Limite**: `GTO_MAX_SOLVE_MEMORY_BYTES`, padrão **4 GiB** por solve, configurável por
   variável de ambiente. A API recusa (`422`, código `arvore_grande_demais`) qualquer solve cuja
   estimativa passe do limite. No MVP roda **1 solve por vez** (os demais ficam na fila), então o
   pico do serviço é ≈ limite + ~0,5 GiB do processo da API.

3. **Fase de finalização e pico de memória**: ao terminar, o job converte `strategy_sum` em
   estratégia média normalizada (no mesmo buffer), **libera os regrets** e só então aloca EV e
   equity por combo do jogador da vez em cada nó de decisão (`C × 8` bytes por nó, R15). Como
   `A(n) ≥ 2`, o espaço liberado (`A × C × 4`) cobre o novo, e o pico continua sendo o da fase de
   treino; a fórmula acima não muda.

4. **Tamanho da solução em disco** (exibido na estimativa e na lista de soluções, FR-030):
   `Σ_n [A(n) × C × 4 + C × 8]` bytes, sem compressão (R12). Na prática, cerca de 50–60% da
   memória de treino.

5. **Precisão do estimador**: teste automatizado compara a estimativa com a memória realmente
   alocada pelos arrays do solver em 10 árvores de referência; erro máximo aceito de ±15%.

6. **Cálculos leves na requisição** (Princípio V): `POST /solves` e `POST /trees/estimate`
   executam na requisição apenas parse da notação, validação do spot, `input_hash` e
   `estimate_tree`. Os quatro juntos têm orçamento de **≤ 200 ms** e benchmark próprio
   (`engine/tests/benchmarks/test_bench_light.py`) no pior caso: flop padrão, 6/97 bb, os dois
   ranges a 100%.

**Estimativas de referência** (pico com a folga de 1,2; sem isomorfismo; "100%" = ranges
completos; "referência" = ranges de referência de R9, 430 combos OOP / 526 combos IP antes dos
bloqueios):

| Árvore | Pote/stack | Nós de decisão | Memória 100% | Memória com ranges de referência |
|--------|-----------|---------------:|-------------:|---------------:|
| River, bets 50%/100%, raise 100%, 3 raises | 10/50 bb | 12 | < 1 MiB | < 1 MiB |
| Turn padrão (bets 33%/75%, raise 100%, 3 raises) | 10/50 bb | ≈ 4,7 mil | ≈ 0,12 GiB | ≈ 0,05 GiB |
| Turn padrão | 6/97 bb | ≈ 6,6 mil | ≈ 0,18 GiB | ≈ 0,07 GiB |
| Flop reduzido (1 bet 66%, raise 100%, 1 raise) | 10/50 bb | ≈ 147 mil | ≈ 3,4 GiB | ≈ 1,4 GiB |
| Flop reduzido (1 bet 66%, raise 100%, 2 raises) | 6/97 bb | ≈ 454 mil | ≈ 11,4 GiB | ≈ 4,6 GiB (recusado) |
| Flop padrão (bets 33%/75%, raise 100%, 3 raises) | 6/97 bb | ≈ 1,76 milhão | ≈ 48 GiB | ≈ 19 GiB (recusado) |

Números gerados por um contador de nós protótipo; o estimador definitivo será validado pelo
teste acima.

**Consequências para o escopo (resolve SC-004 da spec)**:
- **River e turn** com a árvore padrão cabem com folga em 4 GiB.
- **Flop** só com árvores reduzidas e ranges realistas; a árvore padrão de flop não cabe e é
  recusada com sugestões de redução (menos tamanhos, menos raises, ranges menores).
- Orçamentos (hardware de referência em R9):

  | Spot de referência | Alvo | Orçamento |
  |--------------------|------|-----------|
  | River, 2 bets, 1 raise (SC-001) | < 1% do pote | < 30 s |
  | Turn, árvore padrão, ranges de referência (R9), 10/50 bb | < 1% do pote | < 60 s |
  | Flop, 1 bet 66% + raise 100%, 1 raise, ranges de referência (R9), 10/50 bb | < 1% do pote | < 10 min, ≤ 4 GiB |
  | Kuhn | < 0,1% do pote | < 1 s |
  | Leduc | < 0,1% do pote | < 30 s |

**Alternativas consideradas**:
- *Regrets em 16 bits com escala por nó* (≈ metade da memória): fica para depois; aumenta a
  complexidade e afeta a precisão. Reavaliar quando o flop padrão virar requisito.
- *Sem limite e só avisar*: viola o Princípio V (orçamento explícito) e pode derrubar o serviço
  por OOM.
- *MCCFR para o flop*: ver R1.

---

## R4. Cancelamento, pausa e progresso cooperativos

**Decisão**: o solver roda em **blocos de iterações** dentro do processo worker; entre blocos
ele consulta um objeto de controle e publica progresso. Os kernels Numba nunca são
interrompidos no meio de uma iteração.

```text
loop no worker (Python, fora do hot loop):
  enquanto não terminou:
    controle.aguardar_se_pausado()          # bloqueia em Event; não consome CPU
    se controle.parar_ou_cancelar(): sair
    executar_iteracoes(k)                   # kernel @njit; k ajustado p/ ~200 ms
    se hora_de_medir: exp = explotabilidade()  # best response exata (kernel @njit)
    publicar(Progresso(iteração, exp, tempo))
    se exp <= alvo ou tempo >= limite: sair
```

- **Tamanho do bloco adaptativo**: `k` começa em 1 e é ajustado pela duração medida para ficar
  em ~200 ms; isso garante latência de pausa/parada < 1 s (SC-008) mesmo no flop, onde uma
  iteração isolada pode passar de 200 ms (nesse caso `k = 1`).
- **Frequência da explotabilidade**: medir custa ≈ 1 iteração. É medida em intervalos de tempo
  que mantêm o custo ≤ 10% do total e ao menos a cada 2 s; o progresso é publicado a cada bloco
  com a última explotabilidade medida e a iteração em que foi medida.
- **Primitivas**: `SolveControl` é um `Protocol` do motor (`deve_parar()`,
  `aguardar_se_pausado()`) e `ProgressSink` é um callable. O motor não conhece processos, filas
  ou rede (Princípio III).
- **Implementação local (MVP)**: `multiprocessing.Manager` fornece `Event` de pausa e de
  parada e uma `Queue` de eventos, que são passados ao worker do `ProcessPoolExecutor`. Uma task
  asyncio no processo da API consome a fila e repassa aos assinantes WebSocket.
- **Semântica**:
  - *pause*: o worker para no fim do bloco atual; a execução mantém a memória e o slot do pool.
  - *resume*: libera o Event.
  - *stop*: termina no fim do bloco, mede a explotabilidade final, grava a solução (estado
    `stopped`), conforme FR-015.
  - *cancel*: termina no fim do bloco **sem** gravar solução (estado `cancelled`).
  - Se o worker não responder em 10 s (ex.: travamento), o processo é encerrado e o solve fica
    `failed`; o pool é recriado.
- **Raias de execução** (FR-027 e Princípio V): o `JobRunner` tem duas raias, cada uma com 1
  worker:
  - `solve`: 1 solve por vez; os demais ficam na fila FIFO com `queue_position`. Um solve
    **pausado** continua ocupando a raia.
  - `aux`: jobs curtos e pesados de I/O e CPU que também não podem rodar no ciclo HTTP:
    exportação (compactar a solução), importação (descompactar e validar) e limpeza por
    retenção. Rodam em paralelo ao solve, para que exportar não espere um solve de 10 min.
- **Cancelamento ≤ 1 s em todas as fases** (Princípio V: todo job é cancelável): a finalização
  do solve e os jobs `export` e `import` também trabalham em **blocos de ~200 ms** e consultam o
  `SolveControl` entre blocos:
  - finalização: processa os nós de decisão em lotes; `cancel` durante `finalizing` descarta a
    solução (`cancelled`); `stop` já está em andamento e é ignorado;
  - exportação: escreve cada array como membro `.npy` de um zip `ZIP_DEFLATED`, em fatias (cabeçalho
    via `numpy.lib.format` + dados em blocos), em vez de um único `savez_compressed`; ao cancelar,
    remove o arquivo parcial. O resultado continua sendo um `.npz` válido, legível por
    `numpy.load`;
  - importação: lê e valida cada membro em fatias; ao cancelar, remove o diretório parcial;
  - limpeza: verifica o controle entre soluções e publica `progress` como fração das soluções
    avaliadas.
- **Reinício do servidor**: no startup, jobs persistidos como `queued`, `running`, `paused` ou
  `stopping` são marcados `failed` com `error_code = "servidor_reiniciado"` (edge case da spec).
- **Troca futura por fila distribuída**: o `JobRunner` (plano, seção Estrutura) é a única
  peça que muda. Com arq/Celery, os Events viram chaves no Redis consultadas entre blocos e a
  `Queue` vira um canal pub/sub. O motor não muda.

**Alternativas consideradas**: matar o processo (`terminate`) para cancelar perde a solução
parcial exigida por *stop* e pode deixar arquivos inconsistentes; checar flags dentro do kernel
Numba exige passar arrays compartilhados e polui o hot loop; threads em vez de processos
competiriam com o event loop e não isolam falhas de memória.

---

## R5. Isomorfismo de naipes

**Decisão**: calcular o grupo de permutações de naipes que deixam **o board e os dois ranges**
invariantes (ranges com pesos por combo podem quebrar a simetria). Nós de chance enumeram só as
cartas canônicas, com peso igual ao tamanho da órbita; ao navegar para uma carta
não canônica, a estratégia é obtida aplicando a permutação aos combos.

**Racional**: reduz memória e tempo sem aproximação. Ganhos esperados: board rainbow no flop
(1 naipe livre) → nenhum ganho; two-tone → ≈ 1,5–2× nas cartas do turn; monotone → até ≈ 3×.
Por isso o limite de memória (R3) usa a contagem **depois** do isomorfismo, específica do
board.

**Alternativas**: assumir simetria sempre (errado com ranges assimétricos por naipe) ou não usar
isomorfismo (perde de graça até 3× nos boards com naipes repetidos).

---

## R6. Explotabilidade em % do pote

**Decisão**: utilidades definidas como fichas que cada jogador recebe do pote a partir do
início do spot (soma constante = pote inicial `P` + apostas dos dois, isto é, jogo de soma
constante em relação a `P`). Com BR = valor da melhor resposta:

```text
explotabilidade (fichas) = (BR_OOP(σ_IP) + BR_IP(σ_OOP) − P) / 2
explotabilidade (% do pote) = 100 × explotabilidade (fichas) / P
```

Para Kuhn e Leduc (pote inicial = antes de 2 fichas), a mesma fórmula; relatamos também
mbb/mão para comparar com a literatura.

**Racional**: alinha com FR-013 da spec ("média dos ganhos de cada melhor resposta") e com o
Princípio II; é zero exatamente no equilíbrio.

---

## R7. Validação com Kuhn e Leduc no mesmo núcleo

**Decisão**: o núcleo de CFR opera sobre uma **árvore pública vetorizada**: nós de decisão
(jogador, ações), nós de chance públicos (cartas comunitárias) e terminais (fold/showdown), com
vetores por "mão privada". Kuhn (3 mãos privadas: J, Q, K, sem carta pública) e Leduc (6 cartas
privadas, 1 carta pública, apostas de limite fixo 2/4) são construídos como árvores nessa mesma
forma, com matriz de conflito de cartas e função de showdown próprias. O hold'em postflop usa
os 1326 combos.

**Critérios** (testes de aceitação do motor):
- Kuhn: valor do jogo −1/18 ± 0,001; estratégia do primeiro jogador dentro da família de
  equilíbrio (aposta com J com frequência α ∈ [0, 1/3], com K com 3α; etc.); explotabilidade
  < 0,1% do pote.
- Leduc: valor do jogo −0,085606424078 ± 0,005 e explotabilidade < 0,1% do pote.

**Fontes e tolerâncias** (seção "Referências de Validação" da constituição), registradas em
`engine/tests/reference/REFERENCES.md`:

| Caso | Valor | Fonte | Tolerância |
|------|-------|-------|------------|
| Kuhn: valor do jogo (1º jogador) | −1/18 | H. W. Kuhn, "A Simplified Two-Person Poker", *Contributions to the Theory of Games* I, 1950 (solução analítica) | ±0,001 |
| Kuhn: família de equilíbrio | J aposta com α ∈ [0, 1/3], K com 3α, Q nunca abre | idem | ±0,01 nas frequências |
| Leduc: valor do jogo (1º jogador) | −0,085606424078 | M. Lanctot et al., "A Unified Game-Theoretic Approach to Multiagent Reinforcement Learning", NeurIPS 2017 (arXiv:1711.00832), equilíbrio exato por LP na forma sequencial | ±0,005 |
| Avaliador: contagens de 5 cartas | 2.598.960 mãos, 7.462 classes, contagens por categoria | combinatória padrão (C(52,5) e contagens clássicas das categorias) | exato |

As regras do Leduc precisam coincidir com as da fonte: baralho J, J, Q, Q, K, K; ante 1; aposta
fixa 2 na 1ª rodada e 4 na 2ª; no máximo 2 apostas (bet + raise) por rodada; par com a carta
pública vence, senão vence a maior carta. Com a explotabilidade < 0,1% de um pote de 2 fichas
(0,002), o erro do valor fica limitado a ≈ 0,004, compatível com a tolerância de ±0,005.

O spot de referência de river não é um caso de referência com valor conhecido: é um **gate de
qualidade** (explotabilidade < 1% do pote), sem fonte externa.
- Os testes rodam por **número fixo de iterações** (determinístico), não por tempo.

---

## R8. Warm-up do JIT e empacotamento

**Decisão**: `cache=True` em todos os kernels, `NUMBA_CACHE_DIR` apontando para um diretório
gravável; na imagem Docker, o estágio de build roda `python -m gto_engine.warmup` (resolve um
Kuhn e um river minúsculo e calcula uma equity) para gravar o cache. No startup da API, cada
worker do pool executa o mesmo warm-up antes de aceitar jobs, e a API só fica `ready`
(`GET /api/v1/health`) depois disso.

**Racional**: o cache do Numba é por arquitetura de CPU; se a máquina de execução for diferente
da de build, o warm-up do startup recompila uma vez, fora do caminho da primeira requisição.

---

## R9. Hardware de referência e benchmarks

**Decisão**: "notebook comum" = **8 núcleos, 16 GB de RAM** (ex.: MacBook Air M2 ou notebook
x86 equivalente de 2022+), execução nativa (fora de Docker). Os orçamentos absolutos (R3) são
verificados nessa máquina por `uv run pytest -m benchmark_ref`. No CI (runners menores):
- benchmarks com `pytest-benchmark --benchmark-compare` contra baseline salvo, falhando com
  regressão > 20%;
- gates de qualidade por **número fixo de iterações**: Kuhn, Leduc e o spot de referência de river
  precisam ficar abaixo do limite de explotabilidade (independe da velocidade do runner).

**Spots de referência dos benchmarks** (fixtures versionadas em `engine/tests/fixtures/`; os
mesmos ranges em todos, para que os tempos sejam comparáveis):

- Range de referência **OOP** (430 combos antes dos bloqueios):
  `22-TT, A2s-AQs, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A8o-AQo, K9o+, Q9o+, J9o+, T9o, 98o`
- Range de referência **IP** (526 combos antes dos bloqueios):
  `22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 85s+, 74s+, 63s+, 53s+, 43s, A5o+, K9o+, Q9o+, J9o+, T9o, 98o`

Os ranges foram escolhidos para fixar o tamanho e a forma (estilo BB defendendo contra open do
BTN), não como recomendação de estratégia pré-flop.

| Fixture | Board | Pote/stack | Árvore | Orçamento |
|---------|-------|-----------|--------|-----------|
| `river_reference.json` (SC-001) | `Ks 7d 2c Jh 3s` | 10/50 bb | bets 50%/100%, raise 100%, 3 raises, threshold 0,67 | < 1% em < 30 s |
| `turn_reference.json` | `Ks 7d 2c Jh` | 10/50 bb | padrão (bets 33%/75%, raise 100%, 3 raises) | < 1% em < 60 s |
| `flop_reference.json` | `Ks 7d 2c` | 10/50 bb | bets 66%, raise 100%, 1 raise | < 1% em < 10 min, ≤ 4 GiB |
| `flop_default_tree.json` | `Ks 7d 2c` | 6/97 bb | padrão | recusado (`arvore_grande_demais`) |

Ranges a 100% são usados só nos testes de memória e de estimativa (R3, pior caso).

---

## R10. Transporte de progresso: WebSocket vs SSE

**Decisão**: **WebSocket** apenas servidor → cliente; comandos (pausar, retomar, parar,
cancelar) via REST.

**Racional**: suporte nativo no FastAPI/Starlette sem dependência extra; ao reconectar, o
cliente recebe um `snapshot` com o estado atual. Comandos via REST mantêm a idempotência e
aparecem no OpenAPI (cliente gerado).

**Alternativa**: SSE (reconexão automática do navegador, mas exige `sse-starlette` ou
implementação manual e não traria ganho real aqui).

---

## R11. Contrato da API

**Decisão**: REST versionado em `/api/v1`, JSON, erros no formato *Problem Details*
(RFC 9457) com `code` estável em snake_case e `detail` em pt-BR. O OpenAPI gerado pelo FastAPI é
a fonte da verdade; [contracts/openapi.yaml](./contracts/openapi.yaml) é o contrato de
referência que o código precisa respeitar (teste de contrato compara os dois). Mensagens do
WebSocket em [contracts/websocket.md](./contracts/websocket.md). Cliente TypeScript gerado com
`openapi-typescript` + `openapi-fetch` (só tipos + fetch fino, sem runtime pesado).

---

## R12. Formato e armazenamento das soluções

**Decisão** (revisada: a v1 do plano usava um `.npz` comprimido como armazenamento interno):

- **Armazenamento interno**: um diretório por solução, `$GTO_DATA_DIR/solutions/<input_hash>/`,
  com `meta.json` e arrays `.npy` **sem compressão**: `strategy` (float32), `ev` (float32),
  `equity` (float32), `node_offsets` / `combo_offsets` (int64) e `exploitability_history`
  (float64). A leitura usa `numpy.load(mmap_mode="r")`, então a consulta de um nó lê só a fatia
  daquele nó do disco (R15).
- **Exportação/importação**: um arquivo `.npz` **comprimido** (zip `ZIP_DEFLATED` com membros
  `.npy`, escrito em fatias para permitir progresso e cancelamento, R4) com os mesmos arrays mais
  `meta.json`. Exportar e importar são jobs da raia `aux` (R4), porque compactar
  ou descompactar uma solução de flop leva segundos. O download e o upload em si são streaming de
  arquivo, sem cálculo. A leitura usa sempre `allow_pickle=False`.
- **Chave**: SHA-256 da entrada canônica (ranges como vetor de 1326 pesos, board canônico, pote,
  stack, árvore, algoritmo e parâmetros, seed, versão do motor). Mesma entrada ⇒ mesma chave; a
  API reaproveita uma solução concluída com a mesma chave, salvo `force`.
- **EV e equity são gravados** (mudança em relação à v1, que os recalculava sob demanda):
  recalcular na requisição violaria o Princípio V v2.0.0 (orçamento de até 2 s no flop). O cálculo
  passa a ser a fase final do próprio job de solve (R3, item 3).
- Regrets não são persistidos: pausar/retomar vale enquanto o processo do solve existir.

**Racional**: `.npz` comprimido não pode ser mapeado em memória. Ler um nó exigiria descomprimir
o array inteiro, o que leva segundos numa solução de flop de centenas de MB e passaria do limite
de cálculo leve (200 ms). O formato comprimido continua sendo o de troca (exportação), como
pedido na stack.

**Alternativas**: `.npz` como armazenamento interno com cache em memória (primeira abertura de
vários segundos e RAM duplicada); HDF5/Zarr (dependência extra); recalcular EV/equity em job a
cada nó aberto (navegação lenta, e a fila de solves bloquearia as consultas).

---

## R13. Alterar entradas com um solve em andamento

**Decisão**: o solve é **imutável**: ao ser criado, recebe um snapshot das entradas e a chave
(hash). Editar ranges/board/árvore no front **não** afeta o solve em andamento; a tela passa a
mostrar "Entradas alteradas — a solução exibida corresponde às entradas anteriores" com as
opções "Restaurar entradas do solve" e "Novo solve" (o novo entra na fila; o usuário pode cancelar
o anterior).

**Racional**: mantém a reprodutibilidade (Princípio VI) e evita estado parcialmente misturado.
Atende ao edge case "Alteração das entradas" da spec.

---

## R14. Retenção das soluções (FR-028 a FR-030)

**Decisão**:
- `last_used_at` é atualizado ao consultar um nó (no máximo 1 escrita por minuto por solução),
  ao exportar e ao concluir ou importar. Os campos `pinned` e `size_bytes` ficam na tabela
  `solves`.
- Expira quando `pinned = false` e `now − last_used_at > GTO_SOLUTION_RETENTION_DAYS` (padrão
  30). `expires_at` é derivado e devolvido pela API; a UI destaca as que estão a ≤ 7 dias.
- **Limpeza**: um job `cleanup` na raia `aux`, agendado no startup e a cada 6 h por uma task
  asyncio. O job remove o diretório da solução e marca o registro `expired`. O registro é
  mantido para o histórico; uma limpeza manual pode removê-lo.
- Nunca remove solves em `queued`, `running`, `paused` ou `stopping`, nem soluções com exportação
  em andamento.

**Alternativas**: TTL no sistema de arquivos ou cron externo (fora do controle do app);
remoção imediata do registro (perde o histórico de explotabilidade e as entradas).

---

## R15. Consulta de nós dentro do limite de cálculo leve (Princípio V)

**Decisão**: `GET /solves/{id}/nodes` só **lê e agrega**: lê as fatias `strategy`/`ev`/`equity`
do nó (mmap), calcula os ranges que chegam ao nó multiplicando a estratégia ao longo do caminho
(≤ profundidade × ações × 1326 operações vetorizadas) e agrega os 1326 combos nas 169 células.
O custo é limitado pela profundidade máxima da árvore, independe do tamanho total e tem
orçamento de **≤ 200 ms**, verificado por benchmark no maior flop aceito (4 GiB).

**Equity armazenada**: equity all-in do combo do jogador da vez contra o range do oponente que
chega ao nó, sobre os runouts restantes, calculada na finalização por uma varredura de baixo
para cima (média dos showdowns por carta de chance).

**Validação** (Princípio I): a equity é comparada com força bruta via `phevaluator` (todos os
runouts) em spots pequenos de river, turn e flop; o EV da finalização é ancorado nos valores de
Kuhn e Leduc (R7).

---

## R16. Uso pessoal: rede e segurança

**Decisão**: sem autenticação (spec, Clarifications). Para não expor um serviço sem senha:
- `uvicorn` escuta em `127.0.0.1` por padrão. No Docker, o serviço escuta em `0.0.0.0` dentro do
  container, mas a porta é publicada em `127.0.0.1:8000:8000` (documentado no quickstart).
- CORS restrito à origem do front local (`http://localhost:5173` em desenvolvimento,
  configurável).
- Limite de upload na importação: `GTO_MAX_IMPORT_BYTES` (padrão 2 GiB).

**Alternativa**: token único. Desnecessário enquanto o serviço só escuta em localhost; vira
requisito se a spec passar a permitir acesso pela rede.
