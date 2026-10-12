# Feature Specification: Editor de Ranges e Calculadora de Equity

**Feature Branch**: `001-range-equity-calculator` (diretório de spec; o projeto ainda não usa git)

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Quero uma ferramenta onde o jogador monta ranges de mãos e calcula equity entre elas. Editor de range em grade 13x13 (pares na diagonal, suited acima e offsuit abaixo), com clique, arrasto, peso parcial por combo e notação textual com conversão nos dois sentidos. Mostrar combos e % do total (1326), descontando bloqueios do board e de mãos conhecidas. Calcular equity de 2 a 6 ranges ou mãos em qualquer street, com board parcial ou completo; enumeração exata quando viável e Monte Carlo com margem de erro quando não. Exibir equity, win/tie e distribuição de equity por mão. Salvar e carregar ranges nomeados. Critérios: AA vs KK ≈ 81,9% / 18,1%; range vs range heads-up no flop em menos de 2 s."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Calcular equity entre mãos e ranges digitados (Priority: P1)

O jogador informa de 2 a 6 participantes, cada um como uma mão específica (ex.: `AhKh`) ou um
range em notação textual (ex.: `22+, A2s+, KTo+`), opcionalmente informa o board (flop, turn ou
river) e pede o cálculo. A ferramenta mostra, para cada participante, a equity, o % de vitórias
e o % de empates, indicando se o resultado é exato ou estimado.

**Why this priority**: é o núcleo de valor da ferramenta e a base matemática de todas as features
futuras (o solver depende de um cálculo de equity correto). Funciona sem a grade visual.

**Independent Test**: digitar `AA` e `KK` sem board, calcular e conferir 81,9% / 18,1%; digitar
mãos com board completo e conferir o vencedor manualmente.

**Acceptance Scenarios**:

1. **Given** participante 1 = `AA` e participante 2 = `KK`, sem board, **When** o jogador calcula,
   **Then** a ferramenta exibe equity de 81,9% ± 0,1 pp para `AA` e 18,1% ± 0,1 pp para `KK`.
2. **Given** `AhKh` vs `QsQd` com board `Jh Th 2c 3s`, **When** o jogador calcula, **Then** o
   resultado é exato (todas as cartas de river enumeradas) e marcado como "Exato".
3. **Given** `AsAd` vs `KsKd` com board completo `2c 7h 9d Jc 3s`, **When** o jogador calcula,
   **Then** `AsAd` tem 100% de equity, 100% de vitórias e 0% de empates.
4. **Given** 6 ranges amplos sem board, **When** a enumeração exata não cabe no orçamento de tempo,
   **Then** a ferramenta usa simulação, exibe "Estimado" com a margem de erro de cada equity e
   permite continuar refinando ou parar.
5. **Given** um cálculo em andamento, **When** o jogador continua usando a interface, **Then** a
   interface responde normalmente, o progresso é atualizado pelo menos uma vez por segundo e o
   jogador pode cancelar.
6. **Given** um board e mãos com carta repetida (ex.: `AhKh` vs `AhQd`), **When** o jogador tenta
   calcular, **Then** a ferramenta impede o cálculo e indica qual carta está duplicada.

---

### User Story 2 - Montar ranges na grade 13x13 (Priority: P2)

O jogador monta um range visualmente numa grade 13x13 (pares na diagonal, suited acima, offsuit
abaixo), clicando ou arrastando sobre as células, definindo pesos parciais e, quando quiser,
escolhendo combos específicos de naipe dentro de uma célula. A notação textual e a grade ficam
sempre sincronizadas, e a ferramenta mostra o número de combos e o % do total de 1326 combos,
descontando bloqueios do board e das mãos conhecidas.

**Why this priority**: é a forma natural de estudar ranges; depende do modelo de range da P1, mas
entrega valor próprio (visualização e contagem de combos) mesmo sem calcular equity.

**Independent Test**: digitar `22+, A2s+, KTo+` e conferir que a grade marca as células certas e
mostra 162 combos (12,2%); depois editar a grade e conferir que o texto é atualizado.

**Acceptance Scenarios**:

1. **Given** uma grade vazia, **When** o jogador clica em `AKs`, **Then** a célula fica selecionada
   com peso 100%, a contagem passa a 4 combos (0,3%) e o texto passa a `AKs`.
2. **Given** uma grade vazia, **When** o jogador pressiona sobre uma célula não selecionada e
   arrasta sobre outras, **Then** todas as células percorridas são selecionadas; se a primeira
   célula estava selecionada, o arrasto remove a seleção.
3. **Given** o peso ativo definido em 50%, **When** o jogador seleciona `KQo`, **Then** a célula
   exibe visualmente o peso parcial, a contagem soma 6 combos e o texto contém `KQo:0.5`.
4. **Given** o texto `22+, A2s+, KTo+`, **When** o jogador confirma o texto, **Then** a grade marca
   exatamente essas células e a contagem mostra 162 combos (12,2%).
5. **Given** um range com `AA` e board `As 7d 2c`, **When** a contagem é exibida, **Then** `AA`
   conta 3 combos (não 6), refletindo o bloqueio.
6. **Given** o texto inválido `AKx, 33++`, **When** o jogador confirma, **Then** a ferramenta indica
   o trecho inválido e não altera a grade.
7. **Given** a célula `AKs`, **When** o jogador abre o detalhe da célula e desmarca `AsKs`,
   **Then** a célula conta 3 combos e o texto representa os combos restantes de forma
   específica (ex.: `AhKh, AdKd, AcKc`).

---

### User Story 3 - Ver a distribuição de equity dentro do range (Priority: P3)

Depois do cálculo, o jogador vê como a equity se distribui entre as mãos do seu range: a equity
de cada mão (célula da grade e combo específico) contra os demais participantes e um gráfico da
distribuição de equity do range.

**Why this priority**: transforma um número único em material de estudo (quais mãos do range são
fortes ou fracas naquele board), mas depende da P1.

**Independent Test**: calcular `QQ+, AKs` vs `JJ-99` num flop e conferir que cada mão do primeiro
range tem sua equity listada e que a média ponderada pelos combos é igual à equity total.

**Acceptance Scenarios**:

1. **Given** um cálculo concluído, **When** o jogador abre a distribuição de um participante,
   **Then** vê cada mão do range com número de combos, equity, win e tie, ordenável por equity.
2. **Given** a distribuição exibida, **When** o jogador olha a grade daquele participante,
   **Then** cada célula é colorida conforme sua equity média.
3. **Given** a distribuição exibida, **Then** a média das equities por mão, ponderada pelos combos
   e pesos, coincide com a equity total do participante (± 0,05 pp em cálculo exato).
4. **Given** a distribuição exibida, **Then** há um gráfico de equity (combos do range ordenados
   por equity) mostrando que fração do range tem pelo menos X% de equity.

---

### User Story 4 - Salvar e carregar ranges nomeados (Priority: P4)

O jogador salva um range com um nome (ex.: "BTN open 100bb"), lista seus ranges salvos, carrega
um deles em qualquer participante, renomeia, sobrescreve e exclui.

**Why this priority**: conveniência de estudo recorrente; o restante da ferramenta funciona sem
ela.

**Independent Test**: salvar um range com pesos parciais, recarregar a página, carregá-lo de volta
e conferir que grade, texto e contagem são idênticos.

**Acceptance Scenarios**:

1. **Given** um range montado, **When** o jogador salva como "BTN open 100bb", **Then** ele aparece
   na lista de ranges salvos e permanece disponível depois de fechar e reabrir a aplicação.
2. **Given** um range salvo, **When** o jogador o carrega no participante 2, **Then** a grade e o
   texto do participante 2 ficam idênticos ao range salvo, incluindo pesos.
3. **Given** já existe um range chamado "BTN open 100bb", **When** o jogador salva outro com o
   mesmo nome, **Then** a ferramenta pede confirmação para sobrescrever.
4. **Given** um range salvo, **When** o jogador o exclui e confirma, **Then** ele some da lista.

---

### Edge Cases

- **Carta duplicada** entre board e mãos específicas, ou entre duas mãos específicas: cálculo
  bloqueado com indicação da carta em conflito.
- **Range totalmente bloqueado** (ex.: range `AA` com board `As Ad 2c`): contagem 0 combos e o
  cálculo é bloqueado com a mensagem de que o participante não tem combos possíveis.
- **Combinação impossível entre ranges**: quando nenhuma combinação de mãos sem cartas repetidas
  existe entre todos os participantes, o cálculo informa que não há confronto possível.
- **Range vazio** ou **peso 0%** em todas as células: o participante é considerado vazio e o
  cálculo é bloqueado.
- **Board com quantidade inválida** de cartas (1, 2 ou mais de 5) ou carta repetida no board:
  entrada rejeitada.
- **Board completo (river)**: o resultado é sempre exato, sem enumeração de cartas futuras.
- **Empate entre 3 ou mais jogadores**: o pote é dividido igualmente entre os empatados para fins
  de equity.
- **Mão específica conhecida** de um participante bloqueia combos nos ranges dos demais, e a
  contagem exibida de cada range reflete isso.
- **Notação redundante ou sobreposta** (ex.: `AKs, AK, A2s+`): o texto é aceito e normalizado
  para a forma canônica; um mesmo combo não é contado duas vezes (prevalece o último peso
  informado).
- **Cancelamento** no meio de um cálculo: nenhum resultado parcial é apresentado como final; se a
  simulação foi interrompida, o resultado parcial aparece como "Estimado" com sua margem de erro.
- **Alteração das entradas durante um cálculo**: o cálculo em andamento é descartado e o
  resultado antigo não é exibido como se fosse das novas entradas.

## Requirements *(mandatory)*

### Functional Requirements

**Modelo e notação de ranges**

- **FR-001**: O sistema MUST representar um range como um peso entre 0% e 100% para cada um dos
  1326 combos de duas cartas.
- **FR-002**: O sistema MUST aceitar a notação textual padrão: pares (`QQ`), pares com `+`
  (`22+`), intervalos de pares (`55-22`), mãos suited/offsuit (`AKs`, `AKo`), mão sem sufixo
  (`AK` = suited + offsuit), sequências com `+` (`A2s+`, `KTo+`), intervalos com kicker variável
  (`K9s-K6s`), combos específicos (`AhKh`), pesos por item (`AKs:0.5` ou `AKs:50%`) e itens
  separados por vírgula.
- **FR-003**: O sistema MUST converter um range em texto canônico compacto (agrupando com `+` e
  intervalos sempre que possível) e a conversão MUST ser de ida e volta: texto → range → texto
  canônico → range produz o mesmo range.
- **FR-004**: O sistema MUST indicar erros de notação apontando o trecho inválido, sem alterar o
  range atual.

**Editor em grade**

- **FR-005**: O sistema MUST exibir uma grade 13x13 com as cartas na ordem A, K, Q, J, T, 9 … 2,
  pares na diagonal, mãos suited acima da diagonal e offsuit abaixo.
- **FR-006**: O jogador MUST poder selecionar e remover células por clique e por arrasto; o
  arrasto aplica a ação definida pela primeira célula (selecionar se ela estava vazia, remover se
  estava selecionada).
- **FR-007**: O jogador MUST poder definir um peso ativo (0%–100%, em passos de 1%) que é
  aplicado às células selecionadas, e a grade MUST mostrar visualmente o peso parcial de cada
  célula.
- **FR-008**: O jogador MUST poder abrir o detalhe de uma célula e definir o peso de cada combo
  de naipe individualmente (4 combos para suited, 6 para pares, 12 para offsuit).
- **FR-009**: Grade e texto MUST permanecer sincronizados: toda edição na grade atualiza o texto,
  e todo texto válido confirmado atualiza a grade.
- **FR-010**: O jogador MUST poder limpar o range e selecionar todas as mãos com uma ação.

**Contagem de combos e bloqueios**

- **FR-011**: O sistema MUST exibir, para cada range, o número de combos efetivos (soma dos pesos
  dos combos que não usam cartas do board nem cartas de mãos específicas de outros
  participantes) e esse número como % de 1326, com uma casa decimal.
- **FR-012**: A contagem MUST ser atualizada imediatamente a cada alteração de range, board ou
  mãos conhecidas.

**Cálculo de equity**

- **FR-013**: O jogador MUST poder configurar de 2 a 6 participantes, cada um com uma mão
  específica ou um range.
- **FR-014**: O jogador MUST poder informar board vazio (pré-flop), de 3 cartas (flop), 4 (turn)
  ou 5 (river).
- **FR-015**: O sistema MUST validar as entradas antes do cálculo (cartas duplicadas, board com
  tamanho inválido, participante sem combos possíveis) e explicar o problema.
- **FR-016**: O sistema MUST calcular por enumeração exata de todas as combinações válidas de mãos
  e cartas restantes do board sempre que o cálculo exato couber no orçamento de tempo da
  situação; caso contrário MUST usar simulação Monte Carlo.
- **FR-017**: O resultado MUST indicar se é "Exato" ou "Estimado"; resultados estimados MUST
  exibir a margem de erro (intervalo de confiança de 95%) de cada equity e o número de amostras.
- **FR-018**: A simulação MUST continuar refinando até a margem de erro de todos os participantes
  ficar em no máximo ±0,1 pp, até o jogador parar, ou até um limite de tempo configurável, o que
  ocorrer primeiro.
- **FR-019**: A equity de um participante MUST ser a fração média do pote ganha (vitórias contam
  1, empates entre k jogadores contam 1/k), ponderando os combos pelos seus pesos e excluindo
  combinações com cartas repetidas entre participantes.
- **FR-020**: O sistema MUST exibir, por participante: equity, % de vitórias e % de empates.
- **FR-021**: O cálculo MUST NOT travar a interface; MUST exibir progresso (percentual concluído
  ou amostras e margem de erro corrente) pelo menos uma vez por segundo e MUST poder ser
  cancelado.
- **FR-022**: Com as mesmas entradas e a mesma semente, a simulação MUST produzir exatamente o
  mesmo resultado; a semente usada MUST ser exibida e poder ser informada pelo jogador.

**Distribuição de equity**

- **FR-023**: Para cada participante com range, o sistema MUST exibir a equity, win e tie de cada
  mão (célula) e de cada combo específico, com o número de combos efetivos.
- **FR-024**: O sistema MUST colorir a grade do participante conforme a equity de cada célula e
  exibir um gráfico da distribuição de equity do range (combos ordenados por equity).

**Ranges nomeados**

- **FR-025**: O jogador MUST poder salvar o range de qualquer participante com um nome (1 a 60
  caracteres), listar, carregar em qualquer participante, renomear e excluir ranges salvos.
- **FR-026**: Ranges salvos MUST persistir entre sessões no mesmo dispositivo e preservar
  exatamente todos os pesos por combo.
- **FR-027**: Salvar com um nome existente MUST pedir confirmação antes de sobrescrever; excluir
  MUST pedir confirmação.

**Idioma e notação**

- **FR-028**: Todo texto da interface MUST estar em português do Brasil, com números no formato
  pt-BR (vírgula decimal) e cartas e mãos na notação padrão de poker (`A K Q J T 9 … 2`, naipes
  `s h d c`).

### Key Entities

- **Carta**: valor (A, K, Q, J, T, 9–2) e naipe (s, h, d, c); 52 cartas distintas.
- **Combo**: par específico de duas cartas distintas (ex.: `AhKh`); existem 1326.
- **Mão (classe)**: uma das 169 células da grade — par, suited ou offsuit (ex.: `AKs`), que agrupa
  6, 4 ou 12 combos.
- **Range**: atribuição de um peso (0–100%) a cada combo; tem uma representação textual canônica.
- **Range nomeado**: range salvo com nome e data de última alteração.
- **Board**: 0, 3, 4 ou 5 cartas comunitárias distintas.
- **Participante**: mão específica ou range; de 2 a 6 por cálculo.
- **Resultado de equity**: por participante, equity, win %, tie %, tipo (Exato/Estimado), margem
  de erro, número de amostras ou de combinações avaliadas, semente, e a distribuição por mão e
  por combo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `AA` vs `KK` pré-flop retorna 81,9% / 18,1% de equity (tolerância ±0,1 pp) em
  cálculo exato.
- **SC-002**: Um cálculo heads-up range vs range no flop, com ranges de até 100% das mãos cada,
  termina com resultado exato em menos de 2 s no hardware de referência.
- **SC-003**: Um cálculo mão vs mão em qualquer street retorna resultado exato em menos de 1 s.
- **SC-004**: O conjunto de referência de equities pré-flop conhecidas (mão vs mão e mão vs
  range) é reproduzido dentro de ±0,1 pp em 100% dos casos.
- **SC-005**: Em resultados estimados, o valor exato está dentro da margem de erro exibida em pelo
  menos 95% das execuções de um conjunto de casos de teste com resultado exato conhecido.
- **SC-006**: Para 100% dos ranges de um conjunto de teste (incluindo pesos parciais e combos
  específicos), a conversão texto → grade → texto preserva exatamente o range.
- **SC-007**: A contagem de combos coincide com a contagem manual em 100% dos casos de teste com
  bloqueios (ex.: `22+, A2s+, KTo+` = 162 combos = 12,2%; `AA` com um ás no board = 3 combos).
- **SC-008**: Durante qualquer cálculo, a interface continua respondendo a cliques e o progresso é
  atualizado pelo menos uma vez por segundo.
- **SC-009**: Um jogador consegue montar o range `22+, A2s+, KTo+` pela grade, sem digitar, em
  menos de 30 s.
- **SC-010**: Um range salvo é recuperado idêntico (mesmos combos e pesos) após fechar e reabrir a
  aplicação em 100% dos testes.

## Assumptions

- Aplicação de uso individual, sem contas de usuário nem sincronização entre dispositivos; ranges
  salvos ficam armazenados localmente no dispositivo do jogador.
- "Hardware de referência" para os orçamentos de tempo é um notebook de uso comum de 2022 ou mais
  recente; o plano técnico deve fixar a máquina exata usada nos benchmarks.
- O % exibido na contagem usa sempre 1326 como denominador, e o numerador já desconta os combos
  bloqueados (conforme o pedido "% do total de mãos (1326 combos), já descontando os bloqueios").
- Board parcial significa flop (3 cartas) ou turn (4 cartas); boards de 1 ou 2 cartas não são
  suportados.
- Cartas mortas avulsas (fora de board e mãos), ICM, EV em fichas e análise de categorias de mão
  (ex.: "% de top pair") estão fora do escopo desta feature.
- O valor de referência de AA vs KK (≈ 81,9%) considera todos os combos de cada par, sem
  bloqueios de naipe.
- O formato de peso `AKs:0.5` segue a convenção comum de ferramentas de poker, permitindo colar
  ranges de outras ferramentas.
- Exportação e importação de ranges entre dispositivos se dão pela notação textual (copiar e
  colar); um formato de arquivo dedicado fica fora desta feature.
