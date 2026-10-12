# Feature Specification: Biblioteca de Ranges Pré-Flop e Modo de Treino

**Feature Branch**: `003-preflop-ranges-trainer` (diretório de spec; o projeto ainda não usa git)

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Quero uma biblioteca de ranges pré-flop por posição (6-max e HU, 100bb) para RFI, vs open, 3-bet e 4-bet, além de um modo de treino. No treino, o app sorteia um spot e uma mão, o usuário escolhe a ação, e o app compara com a frequência GTO e pontua o erro em EV perdido. Mostrar o histórico de acertos e os leaks por categoria de spot."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar os ranges pré-flop por spot (Priority: P1)

O jogador escolhe o formato (6-max ou HU, 100 bb), o tipo de spot (RFI, vs open, vs 3-bet,
vs 4-bet) e as posições envolvidas (ex.: "BB vs open do BTN") e vê o range GTO daquele spot na
grade 13x13, com cada célula dividida em cores pela frequência de cada ação (fold, call, raise com
o tamanho, all-in), as frequências agregadas e, ao selecionar uma mão, a frequência e o EV de cada
ação.

**Why this priority**: é a base de dados de que o treino depende e já tem valor sozinha como
material de consulta.

**Independent Test**: abrir "6-max, RFI, UTG" e conferir que a grade, o % de mãos abertas e as
frequências por mão batem com os dados de origem; navegar para "CO vs 3-bet do BTN".

**Acceptance Scenarios**:

1. **Given** a biblioteca carregada, **When** o jogador escolhe 6-max › RFI › CO, **Then** vê a grade
   do CO com as frequências de raise e fold por mão, o tamanho do open em bb e o % total de combos
   que abrem.
2. **Given** um spot exibido, **When** o jogador seleciona `A5s`, **Then** vê a frequência e o EV
   (em bb) de cada ação disponível, por combo quando houver diferença entre naipes.
3. **Given** o spot "vs open", **When** o jogador escolhe o herói (ex.: BB) e o agressor (ex.: BTN),
   **Then** só são oferecidas combinações de posições válidas (o agressor age antes do herói).
4. **Given** um spot exibido, **When** o jogador clica em "Abrir no editor", **Then** o range de uma
   ação escolhida (ex.: "3-bet") é carregado no editor de range e na calculadora de equity da
   feature 001.
5. **Given** o formato HU, **Then** os spots disponíveis são SB (botão) RFI, BB vs open, SB vs
   3-bet e BB vs 4-bet.

---

### User Story 2 - Treinar decisões pré-flop (Priority: P2)

O jogador inicia uma sessão de treino escolhendo formato, tipos de spot e posições. O app sorteia
um spot e uma mão, mostra a situação (posição, ações anteriores, tamanhos, pote) e as ações
possíveis. O jogador escolhe uma ação e recebe na hora o veredito: frequência GTO de cada ação para
aquela mão, EV de cada ação, EV perdido pela escolha e a classificação do erro.

**Why this priority**: é o objetivo de estudo ativo da feature; depende da biblioteca (P1).

**Independent Test**: treinar 20 mãos em "6-max, RFI" e conferir, para cada uma, que o EV perdido
exibido é igual a EV(melhor ação) − EV(ação escolhida) segundo os dados da biblioteca.

**Acceptance Scenarios**:

1. **Given** uma sessão de treino iniciada, **When** o app apresenta a mão, **Then** mostra as
   cartas com naipes, a posição do herói, as ações até ele (ex.: "UTG fold, HJ raise 2,5 bb, CO
   fold"), o pote e as ações disponíveis com os tamanhos.
2. **Given** a mão `KTo` no BTN em RFI, onde GTO abre 100%, **When** o jogador escolhe fold,
   **Then** o app mostra raise 100% / fold 0%, o EV de cada ação, o EV perdido (> 0) e classifica
   como erro.
3. **Given** uma mão de estratégia mista (ex.: raise 55% / fold 45%), **When** o jogador escolhe
   qualquer uma das ações com frequência relevante, **Then** o app classifica como correta, mostra
   o EV perdido (próximo de zero) e explica que a mão é mista.
4. **Given** o veredito exibido, **When** o jogador avança, **Then** o próximo spot aparece em menos
   de 0,5 s.
5. **Given** o veredito exibido, **When** o jogador pede "ver range", **Then** vê a grade completa do
   spot com a mão sorteada destacada.
6. **Given** filtros de treino, **When** o jogador ativa "somente mãos de decisão", **Then** o app
   deixa de sortear mãos cuja ação GTO é fold puro com EV de fold claramente superior (mãos
   triviais).

---

### User Story 3 - Histórico de acertos e leaks (Priority: P3)

O jogador vê o histórico das sessões de treino: mãos jogadas, % de acerto, EV perdido total e
médio, e os leaks agrupados por categoria de spot, posição e grupo de mão, com acesso às mãos em
que mais perdeu EV.

**Why this priority**: transforma o treino em diagnóstico; depende do treino (P2).

**Independent Test**: jogar uma sessão errando de propósito todos os spots "vs 3-bet" e conferir
que essa categoria aparece no topo dos leaks, com o EV perdido somado corretamente.

**Acceptance Scenarios**:

1. **Given** sessões de treino concluídas, **When** o jogador abre o histórico, **Then** vê, por
   sessão e no total, mãos jogadas, % de acerto, EV perdido total e EV perdido médio por mão.
2. **Given** o histórico, **When** o jogador abre "Leaks", **Then** vê as categorias de spot
   (tipo de spot × posição do herói × posição do adversário) ordenadas por EV perdido médio, com
   número de mãos e % de acerto de cada uma.
3. **Given** a lista de leaks, **When** o jogador filtra por grupo de mão (pares, suited broadways,
   suited connectors, Ax suited, offsuit broadways, outras), **Then** vê os leaks desse grupo.
4. **Given** uma categoria de leak, **When** o jogador a seleciona, **Then** vê as mãos em que mais
   perdeu EV e pode iniciar um treino focado só naquela categoria.
5. **Given** categorias com menos de 10 mãos jogadas, **Then** elas aparecem marcadas como "amostra
   pequena".
6. **Given** o histórico, **When** o jogador apaga o histórico e confirma, **Then** todos os dados de
   treino são removidos.

---

### Edge Cases

- **Spot sem dados** na biblioteca (ex.: uma combinação de posições não coberta): não é oferecido
  no treino nem na consulta, e a cobertura de spots ausentes aparece na tela da biblioteca.
- **Frequências que não somam 100%** ou EVs ausentes nos dados de origem: o spot é rejeitado na
  carga e o problema é informado.
- **Mãos fora do range que chega ao spot** (ex.: em "vs 3-bet", uma mão que o herói não abriria):
  nunca são sorteadas, pois a situação seria impossível sob a estratégia GTO.
- **Filtros de treino sem nenhum spot** disponível: o treino não inicia e o jogador é avisado.
- **Sessão interrompida** (fechar a aplicação no meio): as mãos já respondidas permanecem no
  histórico.
- **Empate de EV** entre ações (estratégias mistas): nenhuma das ações com frequência relevante é
  marcada como erro.
- **Diferença entre combos da mesma célula** (ex.: `A5s` com naipe que bloqueia): o veredito usa a
  frequência e o EV do combo sorteado, não da célula.

## Requirements *(mandatory)*

### Functional Requirements

**Biblioteca de ranges**

- **FR-001**: A biblioteca MUST cobrir, para os formatos 6-max e HU com stacks de 100 bb, os tipos
  de spot RFI, vs open, vs 3-bet e vs 4-bet, para todas as combinações válidas de posições em que
  os jogadores não envolvidos deram fold.
- **FR-002**: Cada spot MUST conter, para cada um dos 1326 combos que chegam ao spot, a frequência
  de cada ação disponível e o EV (em bb) de cada ação.
- **FR-003**: A origem dos dados da biblioteca MUST ser [NEEDS CLARIFICATION: de onde vêm os ranges
  e os EVs GTO? Ver Pergunta 1 — solver próprio, importação de arquivos de terceiros ou ranges
  montados manualmente.]
- **FR-004**: Ao carregar os dados, o sistema MUST validar cada spot (frequências por combo somando
  100% ±0,1 pp, EV presente para cada ação, tamanhos de aposta coerentes com as ações anteriores) e
  rejeitar spots inválidos com explicação.
- **FR-005**: O sistema MUST exibir cada spot numa grade 13x13 com células divididas em cores
  proporcionais às frequências das ações, legenda fixa de cores por ação e frequências agregadas
  (% de combos por ação).
- **FR-006**: Ao selecionar uma mão, o sistema MUST exibir frequência e EV de cada ação, por combo.
- **FR-007**: O jogador MUST poder enviar o range de uma ação de qualquer spot para o editor de
  range e a calculadora de equity da feature 001.

**Treino**

- **FR-008**: O jogador MUST poder configurar a sessão de treino filtrando formato, tipos de spot,
  posição do herói e posição do adversário, e a opção "somente mãos de decisão".
- **FR-009**: O sistema MUST sortear o spot uniformemente entre os spots filtrados e o combo
  segundo a probabilidade de o herói ter aquele combo naquele spot (combos que chegam ao spot,
  ponderados pela frequência com que chegam).
- **FR-010**: O sistema MUST apresentar a situação completa: cartas do herói com naipe, posição,
  sequência de ações anteriores com tamanhos, pote, stack efetivo e as ações disponíveis.
- **FR-011**: Após a escolha, o sistema MUST exibir a frequência GTO e o EV de cada ação para o
  combo sorteado, o EV perdido, definido como EV(ação de maior EV) − EV(ação escolhida), em bb, e
  a classificação da escolha.
- **FR-012**: A escolha MUST ser classificada como: **Correta** se a frequência GTO da ação for de
  pelo menos 10% ou se o EV perdido for no máximo 0,05 bb; **Imprecisa** se o EV perdido estiver
  entre 0,05 bb e 0,5 bb; **Erro** acima de 0,5 bb.
- **FR-013**: A sorte de cada sessão MUST ser reproduzível: a mesma semente e os mesmos filtros
  produzem a mesma sequência de spots e mãos.
- **FR-014**: O próximo spot MUST aparecer em menos de 0,5 s após o jogador avançar.

**Histórico e leaks**

- **FR-015**: Cada resposta MUST ser registrada com data, spot, combo, ação escolhida,
  frequências e EVs GTO, EV perdido e classificação.
- **FR-016**: O sistema MUST exibir, por sessão e no total, mãos jogadas, % de acerto (Correta),
  EV perdido total e EV perdido médio por mão.
- **FR-017**: O sistema MUST agrupar os leaks por categoria de spot (tipo de spot × posição do
  herói × posição do adversário) e por grupo de mão, ordenados por EV perdido médio, sinalizando
  categorias com menos de 10 mãos.
- **FR-018**: O jogador MUST poder iniciar um treino focado numa categoria de leak.
- **FR-019**: O histórico MUST persistir entre sessões no mesmo dispositivo e poder ser apagado
  pelo jogador, com confirmação.

**Idioma**

- **FR-020**: Toda a interface MUST estar em português do Brasil, com posições (UTG, HJ, CO, BTN,
  SB, BB), ações e mãos na notação padrão de poker e números no formato pt-BR.

### Key Entities

- **Formato**: 6-max ou HU, com stack efetivo de 100 bb.
- **Spot pré-flop**: formato, tipo (RFI, vs open, vs 3-bet, vs 4-bet), posição do herói, posição do
  adversário, sequência de ações anteriores com tamanhos, ações disponíveis.
- **Estratégia do spot**: para cada combo que chega ao spot, frequência e EV de cada ação.
- **Sessão de treino**: filtros, semente, data, lista de respostas.
- **Resposta de treino**: spot, combo, ação escolhida, frequências e EVs GTO, EV perdido,
  classificação.
- **Categoria de leak**: agrupamento de respostas por tipo de spot, posições e grupo de mão, com
  métricas agregadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos spots válidos para 6-max e HU nos quatro tipos de spot estão disponíveis
  (ou explicitamente listados como ausentes) e passam na validação de dados.
- **SC-002**: Para 100% das respostas de um conjunto de teste, o EV perdido e a classificação
  exibidos coincidem com o cálculo manual a partir dos dados da biblioteca.
- **SC-003**: Em 10.000 sorteios, a distribuição de combos sorteados num spot não difere
  significativamente (teste estatístico a 99%) da distribuição esperada de combos que chegam ao
  spot.
- **SC-004**: Qualquer spot da biblioteca é exibido em menos de 0,5 s, e o próximo spot de treino
  aparece em menos de 0,5 s.
- **SC-005**: Um jogador consegue iniciar uma sessão de treino em menos de 3 cliques a partir da
  tela inicial e responder uma mão em menos de 10 s em média.
- **SC-006**: Uma sessão de 50 mãos com erros induzidos numa única categoria mostra essa categoria
  em primeiro lugar nos leaks.
- **SC-007**: O histórico é recuperado integralmente depois de fechar e reabrir a aplicação em 100%
  dos testes.

## Assumptions

- Spots consideram apenas linhas em que todos os outros jogadores deram fold (sem cold-call,
  squeeze ou potes multiway); essas linhas ficam fora do escopo.
- Tamanhos de aposta (open, 3-bet, 4-bet) são os definidos pelos dados de origem de cada spot; o
  usuário não configura sizings nesta feature.
- Jogo cash, sem ante, com rake conforme os dados de origem (a origem informa o rake usado).
- "vs 4-bet" inclui as respostas fold, call e 5-bet all-in; spots depois de um 5-bet ficam fora
  do escopo.
- Uso individual, sem contas; histórico e biblioteca armazenados localmente no dispositivo.
- Os limites de classificação (10% de frequência, 0,05 bb e 0,5 bb) são padrões ajustáveis em
  versões futuras; nesta feature são fixos.
- Grupos de mão para leaks: pares, Ax suited, suited broadways, suited connectors/gappers, outras
  suited, offsuit broadways, outras offsuit.
