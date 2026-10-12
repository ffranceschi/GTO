<!--
Sync Impact Report
==================
Version change: 1.0.0 → 2.0.0
Bump rationale: MAJOR — o Princípio V foi redefinido de forma incompatível: antes permitia
cálculo no cliente ("fora da thread principal, ex.: Web Worker"); agora exige jobs assíncronos
no servidor, proíbe cálculo pesado no ciclo HTTP, fixa WebSocket para progresso e exige
NumPy/Numba em hot loops. Designs conformes à v1.0.0 (cálculo no navegador) deixam de ser
conformes.

Princípios modificados:
  - V. Performance Mensurável e UI Não Bloqueante
    → V. Performance Mensurável, Jobs Assíncronos e Progresso em Tempo Real
      (+ definição de "cálculo pesado" com limite de 200 ms; + exceção para cálculos leves;
       + regra de hot loops NumPy/Numba; + WebSocket; + cancelamento ≤ 1 s; + benchmark
       automatizado obrigatório por feature de cálculo)

Seções modificadas:
  - Fluxo de Desenvolvimento e Quality Gates: gate 3 menciona benchmark automatizado; novo
    gate 7 (sem cálculo pesado no ciclo HTTP, sem Python puro em hot loops).

Seções adicionadas: nenhuma. Seções removidas: nenhuma.

Templates dependentes: não modificados por este comando (leem a constituição em tempo de execução).
  - .specify/templates/plan-template.md  — Constitution Check deve verificar o novo Princípio V
  - .specify/templates/tasks-template.md — tarefas de benchmark por feature de cálculo

Artefatos de features afetados (revisar):
  - specs/002-postflop-solver/plan.md: `GET /solves/{id}/nodes` calcula EV/equity na requisição
    (orçamento de até 2 s no flop) → viola V; deve virar job assíncrono ou ter teto ≤ 200 ms.
  - specs/001-range-equity-calculator/spec.md: assume cálculo local; com V, a equity
    (range vs range, Monte Carlo) roda como job no servidor com progresso via WebSocket.
  - specs/002-postflop-solver/spec.md: edge case de "fechar a aplicação" e premissa de pausa
    "apenas na sessão atual" refletem execução no cliente.

TODOs adiados: nenhum.
-->

# Constituição do Projeto GTO — Estudo de Poker GTO (Texas Hold'em No-Limit)

## Core Principles

### I. Corretude Matemática Primeiro (INEGOCIÁVEL)

Todo algoritmo de equity e de solução (CFR, CFR+, DCFR ou variantes) MUST ser validado contra
resultados conhecidos antes de ser considerado pronto.

- O solver MUST convergir para o equilíbrio de Nash conhecido do **Kuhn Poker** (valor do jogo
  para o primeiro jogador = −1/18 ≈ −0,0556 fichas por mão; família de estratégias de equilíbrio
  parametrizada por α ∈ [0, 1/3]).
- O solver MUST reproduzir os valores de referência do **Leduc Hold'em** publicados na literatura
  (valor do jogo para o primeiro jogador ≈ −0,0856), e atingir explotabilidade abaixo do limite
  definido na seção "Referências de Validação".
- O cálculo de equity MUST bater com tabelas pré-flop conhecidas dentro de uma tolerância
  explícita (ex.: AA vs KK ≈ 81,9%; AKs vs QQ ≈ 46%; 22 vs AKo ≈ 52%), por enumeração exata
  sempre que viável.
- Nenhum resultado numérico exibido ao usuário pode vir de código cujo caminho de cálculo não
  esteja coberto por um teste de referência.

**Racional**: uma ferramenta de estudo que ensina estratégia errada é pior do que nenhuma.
Jogos pequenos com solução conhecida são o único oráculo confiável para o solver.

### II. Explotabilidade como Métrica Oficial

A explotabilidade é a métrica oficial de qualidade de qualquer solução.

- Todo solver MUST calcular e reportar a explotabilidade (via best response exata) em
  **% do pote** — e, para jogos de referência, também em mbb/g ou fichas por mão.
- A explotabilidade MUST ser exibida ao usuário junto com toda solução e atualizada durante a
  execução.
- Todo teste de solver MUST declarar um limite máximo de explotabilidade aceitável e falhar se
  ele não for atingido dentro do número de iterações ou do orçamento de tempo definido.
- Comparações entre algoritmos ou configurações MUST usar explotabilidade, não apenas número de
  iterações ou tempo.

**Racional**: "convergiu" não é verificável sem uma métrica; a explotabilidade é a medida
objetiva da distância ao equilíbrio.

### III. Motor de Cálculo Isolado da UI

O núcleo (avaliador de mãos, cálculo de equity, parser de ranges, árvore de jogo, solver) MUST
ser uma biblioteca independente.

- O motor MUST NOT importar nenhum framework web, biblioteca de UI, API do DOM ou estado global
  de interface.
- O motor MUST ser executável e testável integralmente sem interface (testes unitários e
  scripts de linha de comando/benchmark).
- A UI consome o motor exclusivamente através de uma API pública documentada, com tipos de
  entrada e saída serializáveis.
- Dependências fluem somente da UI para o motor, nunca o contrário.

**Racional**: isolar o motor permite validá-lo matematicamente, medir sua performance e
executá-lo fora da thread principal sem acoplamento com a interface.

### IV. Test-First (INEGOCIÁVEL)

Os testes do motor MUST ser escritos antes da implementação, seguindo o ciclo
Red → Green → Refactor.

- Um teste novo MUST falhar antes de a implementação correspondente ser escrita.
- O avaliador de mãos MUST ter testes exaustivos (ex.: todas as 2.598.960 mãos de 5 cartas
  classificadas nas 7.462 classes de força distintas, com a contagem correta por categoria) ou
  property-based tests cobrindo invariantes (ordenação total, independência de ordem e naipe
  quando aplicável, melhor mão de 5 entre 7 cartas).
- Parsers de notação de range MUST ter testes de ida e volta (texto → combos → texto canônico).
- Bugs encontrados no motor MUST ganhar um teste de regressão antes da correção.

**Racional**: em código numérico, erros são silenciosos; só testes escritos a partir da
especificação, antes do código, evitam que a implementação "ensine" o resultado ao teste.

### V. Performance Mensurável, Jobs Assíncronos e Progresso em Tempo Real

- **Cálculo pesado** é todo cálculo cujo orçamento declarado passa de 200 ms no hardware de
  referência, ou cujo custo cresce com a entrada sem um teto fixo (ex.: equity range vs range,
  Monte Carlo, solves, best response, EV/equity de nós de flop/turn).
- Cálculos pesados MUST rodar como **jobs assíncronos no servidor**, fora do processo que atende
  as requisições, e MUST NOT executar dentro do ciclo de requisição HTTP. O endpoint HTTP apenas
  valida a entrada, cria o job e responde de imediato com o identificador e o estado do job.
- Cálculos leves (≤ 200 ms com teto fixo, ex.: parsing de range, contagem de combos, leitura de
  uma solução já calculada) MAY rodar na requisição, desde que tenham benchmark que comprove o
  limite.
- Hot loops do motor MUST usar operações vetorizadas NumPy ou kernels Numba compilados; laços em
  Python puro sobre combos, boards, iterações de solver ou amostras são proibidos. Código Python
  puro fica restrito a orquestração fora dos hot loops.
- A UI MUST receber progresso em tempo real via **WebSocket** (iteração ou amostras,
  explotabilidade ou margem de erro corrente, tempo decorrido), pelo menos uma vez por segundo,
  e todo job MUST poder ser cancelado; o cancelamento é cooperativo e efetivo em ≤ 1 s.
- A UI MUST NOT bloquear enquanto um job roda.
- Toda feature de cálculo MUST declarar na spec um orçamento de tempo explícito, com o hardware de
  referência, e MUST ter **benchmark automatizado** que verifique esse orçamento; regressões acima
  do orçamento bloqueiam o merge.

**Racional**: solvers e equities de range são caros e de duração imprevisível; mantê-los fora
do ciclo HTTP preserva a responsividade da API, permite cancelar e escalar a execução, e o
progresso em tempo real dá ao usuário visibilidade. Kernels compilados são a única forma de
atingir os orçamentos em Python, e benchmarks dão números, não impressões, para decidir
otimizações.

### VI. Determinismo e Reprodutibilidade

- Com a mesma entrada, a mesma seed e a mesma versão do motor, o resultado MUST ser idêntico.
- Toda aleatoriedade do motor (Monte Carlo, amostragem em MCCFR etc.) MUST vir de um PRNG
  semeado e injetado; o uso de fontes não semeadas (ex.: `Math.random`, relógio) no motor é
  proibido.
- Paralelismo MUST NOT alterar o resultado (redução em ordem determinística).
- Soluções MUST ser exportáveis e importáveis num formato versionado que inclua: versão do
  formato, versão do motor, parâmetros do jogo/árvore, seed, algoritmo, número de iterações,
  explotabilidade final e estratégias. Importar e reexportar MUST produzir conteúdo equivalente.

**Racional**: reprodutibilidade é pré-requisito para depurar, comparar algoritmos e confiar
em resultados salvos para estudo.

### VII. Simplicidade

- Cada dependência externa MUST ser justificada no plano da feature (o que ela resolve e por
  que não implementar internamente); o motor SHOULD ter zero dependências de runtime.
- Nenhuma funcionalidade, opção de configuração ou abstração fora da spec da feature corrente
  pode ser implementada (YAGNI).
- Otimizações MUST ser motivadas por um benchmark que viola um orçamento (Princípio V).

**Racional**: menos código e menos dependências significam menos superfície para erros
numéricos e builds mais reprodutíveis.

### VIII. Interface em Português do Brasil com Notação Padrão de Poker

- Todo texto visível ao usuário MUST estar em português do Brasil.
- Mãos e ranges MUST usar a notação padrão de poker: cartas `A K Q J T 9 … 2`, naipes
  `s h d c`, mãos como `AKs`, `T9o`, `QQ`, e ranges como `22+`, `A2s+`, `KTo+`, `76s-54s`,
  `AA,KK,AKs`.
- Termos técnicos consagrados (pote, equity, range, flop, turn, river, check, bet, raise,
  fold, all-in, GTO, EV) MAY permanecer na forma usual do jargão de poker.
- Números MUST seguir a formatação pt-BR na interface (vírgula decimal, ex.: 81,9%); formatos
  de exportação usam formato neutro de máquina.

**Racional**: o público é brasileiro, e a notação padrão permite colar ranges de outras
ferramentas e materiais de estudo sem conversão.

## Referências de Validação e Limites de Qualidade

- O repositório MUST manter um conjunto versionado de casos de referência do motor:
  - Kuhn Poker: valor do jogo −1/18 e verificação de que a estratégia obtida pertence à família
    de equilíbrios conhecida.
  - Leduc Hold'em: valor do jogo de referência e limite de explotabilidade.
  - Equities pré-flop mão vs mão tabeladas (incluindo AA vs KK ≈ 81,9%) e casos de range vs range.
  - Contagens do avaliador de mãos por categoria (ex.: 40 straight flushes, 624 quadras, 3.744
    full houses em 5 cartas).
- Cada caso MUST declarar sua tolerância numérica e a fonte do valor de referência.
- Limites de explotabilidade MUST ser definidos nos testes e na spec da feature; um limite só
  pode ser afrouxado por emenda registrada na spec, com justificativa.

## Fluxo de Desenvolvimento e Quality Gates

- Toda feature parte de uma spec (`/speckit-specify`) e de um plano cujo "Constitution Check"
  verifica explicitamente os oito princípios.
- Gates obrigatórios antes do merge:
  1. Testes do motor escritos primeiro e passando, incluindo os casos de referência.
  2. Explotabilidade dentro do limite declarado para toda feature de solver.
  3. Benchmarks automatizados dentro do orçamento de tempo declarado.
  4. Teste de determinismo (mesma entrada + seed → mesma saída) e de ida e volta de
     exportação/importação quando aplicável.
  5. Motor sem import de código de UI (verificado por lint ou regra de dependências).
  6. Textos de interface em pt-BR e notação de poker validada pelo parser de ranges.
  7. Nenhum cálculo pesado no ciclo de requisição HTTP e nenhum laço Python puro em hot loops
     do motor (verificado em revisão e por benchmark).
- Revisões MUST rejeitar dependências ou funcionalidades não justificadas pela spec.

## Governance

- Esta constituição prevalece sobre quaisquer outras práticas, guias ou preferências do projeto.
- Emendas MUST ser feitas por meio de `/speckit-constitution`, com Sync Impact Report,
  justificativa e plano de migração quando afetarem código ou testes existentes.
- Versionamento semântico da constituição:
  - MAJOR: remoção ou redefinição incompatível de princípio ou regra de governança.
  - MINOR: novo princípio ou seção, ou expansão material de orientação.
  - PATCH: esclarecimentos, redação e correções sem mudança semântica.
- Toda revisão de plano, tarefas e código MUST verificar conformidade; qualquer violação MUST
  ser registrada na tabela de complexidade do plano com justificativa e alternativa mais simples
  rejeitada.

**Version**: 2.0.0 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-12
