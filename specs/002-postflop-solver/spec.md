# Feature Specification: Solver GTO Postflop Heads-Up

**Feature Branch**: `002-postflop-solver` (diretório de spec; o projeto ainda não usa git)

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Quero calcular a estratégia GTO aproximada de um spot postflop heads-up. Entrada: ranges de OOP e IP (reutilizando a feature 001), board (flop, turn ou river), pote, stack efetivo e árvore de apostas configurável (tamanhos de bet e raise em % do pote, limite de raises por street, all-in threshold). O solver itera até atingir a explotabilidade alvo (ex.: 0,5% do pote) ou um limite de tempo, mostrando iterações, explotabilidade e tempo decorrido, com opção de pausar ou parar. Saída: frequência de cada ação por mão e agregada no range, navegável nó a nó pela árvore, com grade colorida por ação, EV por mão e equity. Permitir exportar e importar a solução. Critérios: river spot com 2 tamanhos de bet abaixo de 1% de explotabilidade em menos de 30 s em notebook comum; o solver reproduz o equilíbrio conhecido do Kuhn Poker nos testes."

## Clarifications

### Session 2026-10-12

- Q: Quais devem ser o limite de memória e a cobertura de streets do solver? → A: Definido no
  `/speckit.plan` (research R3), a pedido do usuário: 4 GiB por solve (configurável), river e
  turn com a árvore padrão, flop só com árvores reduzidas que caibam no limite. Confirmado pelo
  usuário: turn < 60 s; flop reduzido < 10 min.
- Q: O app terá login com várias contas ou será de uso pessoal? → A: Uso pessoal: um único
  usuário, servidor local (localhost ou Docker na própria máquina), sem login nem contas.
- Q: Quantos solves o servidor deve rodar ao mesmo tempo? → A: 1 solve por vez; os demais ficam
  numa fila com posição visível e podem ser cancelados.
- Q: Por quanto tempo as soluções concluídas ficam armazenadas? → A: São apagadas
  automaticamente após N dias sem uso (padrão 30, configurável), exceto as marcadas como
  "fixadas".
- Q: Rake, ICM e potes multiway ficam fora desta feature? → A: Sim, tudo fora: sem rake, sem ICM,
  apenas heads-up.
- Q: Qual deve ser o tempo-limite padrão do solve? → A: Por street do board: river 60 s, turn
  120 s, flop 15 min (editável), com folga sobre os orçamentos de SC-001/SC-004.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolver um spot de river (Priority: P1)

O jogador define os ranges de OOP e IP (com o editor e os ranges salvos da feature 001), um board
de 5 cartas, o pote, o stack efetivo e a árvore de apostas, e inicia o solver. Durante a execução
vê iterações, explotabilidade e tempo decorrido, e pode pausar, retomar ou parar. Ao final vê a
estratégia do nó raiz: frequência de cada ação agregada no range e por mão, numa grade colorida
por ação.

**Why this priority**: o river é o menor spot real de poker (sem cartas futuras), cabe no
orçamento de tempo e já entrega o valor central da ferramenta: ver a estratégia de equilíbrio.

**Independent Test**: resolver o spot de referência de river com 2 tamanhos de bet e conferir que
a explotabilidade final fica abaixo de 1% do pote em menos de 30 s e que as frequências de cada
mão somam 100%.

**Acceptance Scenarios**:

1. **Given** ranges OOP e IP, board de river, pote 10 bb, stack 50 bb e bets de 50% e 100% do
   pote, **When** o jogador inicia o solver com alvo de 0,5% do pote, **Then** o solver para ao
   atingir explotabilidade ≤ 0,5% do pote ou ao atingir o limite de tempo, e informa qual condição
   encerrou a execução.
2. **Given** o solver em execução, **When** o jogador observa a tela, **Then** iterações,
   explotabilidade corrente (% do pote) e tempo decorrido são atualizados pelo menos uma vez por
   segundo e a interface continua respondendo.
3. **Given** o solver em execução, **When** o jogador pausa e depois retoma, **Then** o solver
   continua de onde parou, sem perder iterações.
4. **Given** o solver em execução, **When** o jogador para, **Then** a estratégia mais recente fica
   disponível para análise, com sua explotabilidade exata naquele momento.
5. **Given** um spot resolvido, **When** o jogador olha o nó raiz, **Then** vê a frequência
   agregada de cada ação (ex.: check 62%, bet 50% 23%, bet 100% 15%) e a grade 13x13 com cada
   célula dividida em cores proporcionais às frequências das ações.
6. **Given** um spot resolvido, **When** o jogador seleciona uma célula (ex.: `AKs`), **Then** vê
   a frequência de cada ação, o EV e a equity de cada combo dessa célula.

---

### User Story 2 - Navegar pela árvore de decisão (Priority: P2)

O jogador percorre a árvore nó a nó escolhendo ações (ex.: OOP check → IP bet 100% → OOP ?) e, nos
spots de flop e turn, escolhendo as cartas que saem. Em cada nó vê a estratégia do jogador da vez,
os ranges que chegam ao nó, EV e equity por mão.

**Why this priority**: sem navegação só se estuda a primeira decisão; depende da P1.

**Independent Test**: resolver o spot de referência, navegar até OOP check → IP bet → OOP decisão
e conferir que o range exibido de OOP é o range que deu check, ponderado pela frequência de check
de cada combo.

**Acceptance Scenarios**:

1. **Given** um spot resolvido, **When** o jogador escolhe uma ação no nó atual, **Then** a tela
   passa ao nó seguinte e mostra o caminho percorrido (ex.: "Check › Bet 100% (10 bb)").
2. **Given** um nó qualquer, **When** o jogador clica num passo anterior do caminho, **Then** volta
   àquele nó.
3. **Given** um nó de transição de street num spot de flop ou turn, **When** o jogador escolhe a
   carta que sai, **Then** vê a estratégia do nó seguinte para aquela carta; cartas bloqueadas pelo
   board não podem ser escolhidas.
4. **Given** um nó qualquer, **Then** o jogador vê o pote e os stacks naquele ponto, os ranges dos
   dois jogadores que chegam ao nó (combos e grade) e o EV e equity de cada mão do jogador da vez.
5. **Given** um nó terminal (fold, showdown ou all-in chamado), **Then** a ferramenta indica o fim
   da linha e o resultado esperado de cada mão.

---

### User Story 3 - Configurar a árvore de apostas (Priority: P3)

O jogador configura, por street e por posição, os tamanhos de bet e de raise em % do pote, o
limite de raises por street, o all-in threshold e se OOP pode apostar primeiro numa street
seguinte a uma ação de IP (donk bet). Antes de resolver vê o tamanho da árvore e a estimativa de
memória.

**Why this priority**: a P1 pode começar com uma árvore padrão; configurar a árvore é o que
permite estudar sizings diferentes.

**Independent Test**: montar uma árvore com 1 tamanho de bet, 1 de raise e limite de 1 raise no
river, e conferir no navegador que cada nó tem exatamente as ações esperadas.

**Acceptance Scenarios**:

1. **Given** bets de 33% e 75% e raise de 100% no river, limite de 2 raises, **When** a árvore é
   gerada, **Then** o nó raiz de OOP oferece check, bet 33% e bet 75%, e depois de 2 raises só
   restam call e fold.
2. **Given** all-in threshold de 67%, **When** um tamanho de aposta usaria 67% ou mais do stack
   restante, **Then** essa aposta vira all-in e apostas duplicadas são unificadas.
3. **Given** um tamanho que excede o stack restante, **Then** ele vira all-in.
4. **Given** um raise configurado abaixo do raise mínimo, **Then** ele é ajustado para o raise
   mínimo.
5. **Given** uma árvore configurada, **When** o jogador pede a estimativa, **Then** vê o número de
   nós e a memória estimada; se exceder o limite suportado, o solver não inicia e explica como
   reduzir a árvore.
6. **Given** uma configuração de árvore, **When** o jogador a salva com um nome, **Then** pode
   reutilizá-la em outros spots.

---

### User Story 4 - Exportar e importar soluções (Priority: P4)

O jogador exporta uma solução para um arquivo e depois a importa (no mesmo ou em outro
dispositivo), vendo exatamente a mesma estratégia, sem rodar o solver de novo.

**Why this priority**: preserva soluções caras de calcular e permite compartilhá-las; não é
necessária para resolver e analisar um spot.

**Independent Test**: exportar uma solução, importá-la e conferir que todas as frequências, EVs e
a explotabilidade exibida são idênticas.

**Acceptance Scenarios**:

1. **Given** um spot resolvido, **When** o jogador exporta, **Then** recebe um arquivo com
   entradas do spot, configuração da árvore, algoritmo, semente, número de iterações,
   explotabilidade final e estratégias.
2. **Given** um arquivo exportado, **When** o jogador o importa, **Then** a solução é exibida e
   navegável com valores idênticos aos originais.
3. **Given** um arquivo corrompido, de outro tipo ou de versão de formato incompatível, **When** o
   jogador o importa, **Then** a importação é recusada com uma mensagem clara e nada é alterado.
4. **Given** uma solução importada, **When** o jogador recalcula a explotabilidade, **Then** obtém
   o mesmo valor registrado no arquivo.

---

### Edge Cases

- **Ranges sem combos** depois dos bloqueios do board: o solver não inicia e indica qual range.
- **Stack efetivo zero ou menor que a menor aposta**: a árvore se reduz a check/all-in conforme
  as regras; stack zero vai direto ao showdown (apenas equity, sem decisão).
- **Pote ou stack inválidos** (negativos, zero no pote, não numéricos): entrada rejeitada.
- **Board inválido** (cartas repetidas, menos de 3 ou mais de 5 cartas): entrada rejeitada.
- **Alvo de explotabilidade inalcançável no tempo-limite**: o solver para no limite e exibe a
  explotabilidade atingida, marcando que o alvo não foi alcançado.
- **Árvore grande demais** para a memória suportada: o solver não inicia; a estimativa aparece
  antes da execução.
- **Mão com frequência zero** de chegar a um nó: aparece como fora do range naquele nó, sem
  estratégia exibida como se fosse relevante.
- **Alteração das entradas** com uma solução carregada: a solução fica marcada como desatualizada
  e não é exibida como se valesse para as novas entradas.
- **Fechar ou recarregar a interface** durante a execução: o solve continua rodando no servidor;
  ao reabrir, a interface mostra o estado e o progresso atuais.
- **Reiniciar o servidor** durante a execução: solves em fila, rodando ou pausados são perdidos e
  aparecem como falhos; soluções já concluídas permanecem.
- **Novo solve com outro ativo**: o novo entra na fila e mostra sua posição; um solve **pausado**
  continua ocupando a vez, e a fila só avança quando ele for parado, cancelado ou concluído.
- **Solução prestes a expirar**: soluções com 7 dias ou menos até a exclusão automática aparecem
  destacadas na lista; solves em fila, rodando ou pausados nunca são apagados.
- **Tamanhos duplicados** (ex.: 100% e all-in resultando no mesmo valor): a ação aparece uma só vez.

## Requirements *(mandatory)*

### Functional Requirements

**Entradas do spot**

- **FR-001**: O jogador MUST poder definir os ranges de OOP e IP com o editor de range da feature
  001 (grade, texto, pesos) e carregar ranges salvos.
- **FR-002**: O jogador MUST informar o board (3, 4 ou 5 cartas), o pote inicial e o stack
  efetivo, em big blinds (bb), aceitando valores com até duas casas decimais.
- **FR-003**: O sistema MUST validar as entradas antes de resolver e explicar cada problema.

**Árvore de apostas**

- **FR-004**: O jogador MUST poder configurar, para cada street e para cada posição, uma lista de
  tamanhos de bet em % do pote e uma lista de tamanhos de raise em % do pote (pote considerado após
  o call).
- **FR-005**: O jogador MUST poder definir o limite de raises por street; atingido o limite, as
  únicas respostas a uma aposta são call e fold.
- **FR-006**: O jogador MUST poder definir o all-in threshold: toda aposta ou raise que use pelo
  menos esse % do stack restante vira all-in. Tamanhos que excedem o stack também viram all-in.
- **FR-007**: O jogador MUST poder habilitar ou não o all-in como ação adicional e as donk bets
  (OOP apostando primeiro numa street depois de IP ter tomado a iniciativa).
- **FR-008**: Raises abaixo do raise mínimo das regras de No-Limit MUST ser ajustados ao mínimo, e
  ações que resultem em valores idênticos MUST ser unificadas.
- **FR-009**: Antes de resolver, o sistema MUST exibir o número de nós de decisão e a memória
  estimada, e MUST impedir a execução quando exceder o limite suportado.
- **FR-010**: O jogador MUST poder salvar e carregar configurações de árvore nomeadas; MUST haver
  uma configuração padrão pronta para uso.

**Execução do solver**

- **FR-011**: O solver MUST calcular uma estratégia de equilíbrio aproximada para o jogo de duas
  pessoas definido pelas entradas, sem agrupar mãos ou cartas em abstrações (estratégia por combo
  e por carta de turn/river).
- **FR-012**: O jogador MUST definir a explotabilidade alvo (padrão 0,5% do pote) e o limite de
  tempo (padrão conforme a street do spot: river 60 s, turn 120 s, flop 15 min; editável); o
  solver MUST parar ao atingir o primeiro dos dois e informar qual foi.
- **FR-013**: A explotabilidade MUST ser calculada exatamente (melhor resposta contra a estratégia
  atual) e reportada em % do pote inicial, definida como a média dos ganhos que cada jogador
  obteria jogando a melhor resposta contra a estratégia do adversário.
- **FR-014**: Durante a execução o sistema MUST exibir iterações, explotabilidade mais recente e
  tempo decorrido, atualizados pelo menos uma vez por segundo, sem travar a interface.
- **FR-015**: O jogador MUST poder pausar, retomar e parar; ao parar, a estratégia atual MUST
  ficar disponível com sua explotabilidade exata.
- **FR-016**: Com as mesmas entradas, a mesma configuração, a mesma semente e o mesmo número de
  iterações, o solver MUST produzir exatamente a mesma estratégia.
- **FR-017**: O sistema MUST exibir, durante e depois da execução, um gráfico da explotabilidade
  ao longo das iterações.
- **FR-027**: O sistema MUST executar no máximo 1 solve por vez. Solves criados enquanto outro
  está ativo (rodando ou pausado) MUST entrar numa fila por ordem de criação, exibindo a posição
  de cada um; o jogador MUST poder cancelar qualquer solve da fila. Ao terminar, parar ou
  cancelar o solve ativo, o próximo da fila MUST iniciar automaticamente.

**Saída e navegação**

- **FR-018**: Para cada nó de decisão, o sistema MUST exibir a frequência agregada de cada ação no
  range do jogador da vez (em % dos combos, ponderados pelos pesos e pela chance de chegar ao nó)
  e o número de combos de cada ação.
- **FR-019**: O sistema MUST exibir a grade 13x13 do jogador da vez com cada célula dividida em
  cores proporcionais às frequências das ações; cada ação MUST ter cor fixa e legenda.
- **FR-020**: Para cada mão (célula) e cada combo, o sistema MUST exibir frequência de cada ação,
  EV (em bb) e equity contra o range do adversário que chega ao nó.
- **FR-021**: O jogador MUST poder navegar pela árvore escolhendo ações e, em transições de
  street, a carta que sai; o caminho percorrido MUST ficar visível e clicável.
- **FR-022**: Em cada nó, o sistema MUST exibir pote, stacks e os ranges dos dois jogadores que
  chegam ao nó.
- **FR-023**: Os nomes das ações MUST seguir o jargão de poker (check, bet, call, raise, fold,
  all-in) com o tamanho em % do pote e em bb (ex.: "Bet 75% (7,5 bb)").

**Exportação e importação**

- **FR-024**: O jogador MUST poder exportar a solução para um arquivo versionado contendo versão do
  formato, versão do motor, entradas do spot, árvore, algoritmo, semente, iterações,
  explotabilidade final e estratégias.
- **FR-025**: O jogador MUST poder importar um arquivo exportado e navegar a solução com valores
  idênticos aos originais; arquivos inválidos ou incompatíveis MUST ser recusados com mensagem
  clara.

**Armazenamento das soluções**

- **FR-028**: Soluções concluídas, paradas ou importadas MUST ficar armazenadas no servidor e ser
  apagadas automaticamente quando ficarem N dias sem uso (padrão 30 dias, configurável por quem
  opera o servidor). "Uso" é abrir a solução, navegar por ela ou exportá-la.
- **FR-029**: O jogador MUST poder fixar e desafixar uma solução; soluções fixadas nunca são
  apagadas automaticamente.
- **FR-030**: A lista de soluções MUST mostrar, para cada uma, o tamanho em disco, a data do
  último uso, se está fixada e quantos dias faltam para a exclusão automática; e MUST mostrar o
  total ocupado. O jogador MUST poder excluir qualquer solução manualmente, com confirmação.

**Validação matemática**

- **FR-026**: O mesmo motor de solução MUST ser validado contra o Kuhn Poker (valor do jogo −1/18
  para o primeiro jogador e estratégia dentro da família de equilíbrios conhecida) e contra o Leduc
  Hold'em (valor de referência da literatura), conforme a constituição.

### Key Entities

- **Spot**: ranges de OOP e IP, board, pote inicial, stack efetivo.
- **Configuração de árvore**: tamanhos de bet e raise por street e posição, limite de raises,
  all-in threshold, opções de all-in e donk bet; pode ter nome.
- **Árvore de jogo**: nós de decisão (jogador da vez, ações possíveis), nós de carta (turn/river)
  e nós terminais (fold, showdown).
- **Execução do solver**: alvo de explotabilidade, limite de tempo, semente, estado (na fila,
  rodando, pausado, parando, finalizando, concluído, parado, cancelado, falhou, expirado),
  posição na fila, iterações, histórico de explotabilidade, motivo de parada.
- **Solução**: estratégia (frequência de cada ação por combo em cada nó de decisão), EV e equity
  por combo, explotabilidade final, metadados de reprodução, tamanho em disco, data do último
  uso e marcação de fixada.
- **Arquivo de solução**: representação exportável e versionada de uma solução.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O spot de referência de river (2 tamanhos de bet por jogador, 1 tamanho de raise,
  ranges de referência definidos no plano, research R9) atinge explotabilidade abaixo de 1% do pote em menos de
  30 s num notebook comum (hardware de referência fixado no plano).
- **SC-002**: Nos testes, o solver reproduz o equilíbrio do Kuhn Poker: valor do jogo −1/18 com
  tolerância de ±0,001 e explotabilidade abaixo de 0,1% do pote.
- **SC-003**: Nos testes, o solver atinge no Leduc Hold'em o valor de referência da literatura
  (−0,085606424078 para o primeiro jogador, calculado por programação linear na forma sequencial
  por Lanctot et al., 2017) com tolerância de ±0,005 e explotabilidade abaixo de 0,1% do pote.
- **SC-004**: Com limite padrão de 4 GiB de memória estimada por solve (configurável), spots de
  turn com a árvore padrão atingem < 1% do pote em menos de 60 s; spots de flop são aceitos
  apenas com árvores que caibam no limite (ex.: 1 tamanho de bet e 1 de raise) e atingem < 1% do
  pote em menos de 10 min; árvores acima do limite são recusadas antes de iniciar.
- **SC-005**: Em 100% dos nós de toda solução, as frequências das ações de cada combo somam 100%
  (±0,01 pp) e a média do EV ponderada pelos combos é consistente com o EV agregado do nó.
- **SC-006**: Exportar e importar uma solução reproduz 100% das frequências, EVs e a
  explotabilidade sem diferença.
- **SC-007**: Rodar duas vezes o mesmo spot com a mesma semente e o mesmo número de iterações
  produz estratégias idênticas.
- **SC-008**: Durante a execução, a interface responde a cliques e o progresso é atualizado pelo
  menos uma vez por segundo; pausar ou parar tem efeito em menos de 1 s.
- **SC-009**: Um jogador que já conhece a feature 001 consegue configurar e iniciar o spot de
  referência de river em menos de 2 minutos.

## Assumptions

- Fora do escopo (confirmado): rake, ICM e potes multiway. O jogo é heads-up, sem rake, sem
  antes e sem ICM; pote e stacks em big blinds.
- Aplicação de uso pessoal: um único usuário opera o servidor localmente (localhost ou Docker
  na própria máquina); não há login, contas, isolamento de dados por usuário nem cotas por
  usuário. Expor o serviço na rede está fora do escopo.
- Apenas heads-up postflop; o spot começa no início de uma street com OOP agindo primeiro.
- "Notebook comum" (hardware de referência dos orçamentos) é um notebook de uso geral de 2022 ou
  mais recente com 8 núcleos e 16 GB de RAM, execução nativa (ex.: MacBook Air M2); o plano
  fixa a máquina exata dos benchmarks.
- Raises são expressos em % do pote após o call (convenção usual de solvers); bets em % do pote
  atual.
- Configuração padrão da árvore: bets de 33% e 75%, raise de 100%, limite de 3 raises por street,
  all-in threshold de 67%, donk bets desabilitadas.
- Solves rodam como jobs no servidor (constituição v2.0.0, Princípio V). Pausar e retomar valem
  enquanto o servidor estiver no ar; uma execução não sobrevive a reiniciar o servidor.
- A explotabilidade é exibida em % do pote inicial do spot.
- Como a parada por tempo varia entre máquinas, a reprodutibilidade (FR-016) é garantida para um
  mesmo número de iterações, que fica registrado na solução.
- Node locking, comparação entre soluções, relatórios agregados por textura de flop e solver
  pré-flop estão fora do escopo.
- O arquivo de solução de spots de flop pode ser grande; compressão é detalhe do plano.
