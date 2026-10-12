# Casos de referência do motor

Exigido pela constituição (seção "Referências de Validação"): cada caso declara valor, fonte e
tolerância. Os testes citam a linha correspondente no docstring.

| Caso | Valor | Fonte | Tolerância | Teste |
|------|-------|-------|------------|-------|
| Kuhn: valor do jogo (1º jogador) | −1/18 | H. W. Kuhn, "A Simplified Two-Person Poker", *Contributions to the Theory of Games* I, 1950 (solução analítica) | ±0,001 | `test_kuhn.py` |
| Kuhn: família de equilíbrio | J aposta com α ∈ [0, 1/3], K com 3α, Q nunca abre | idem | ±0,01 nas frequências | `test_kuhn.py` |
| Leduc: valor do jogo (1º jogador) | −0,085606424078 | M. Lanctot et al., "A Unified Game-Theoretic Approach to Multiagent Reinforcement Learning", NeurIPS 2017 (arXiv:1711.00832), equilíbrio exato por LP na forma sequencial | ±0,005 | `test_leduc.py` |
| Avaliador: contagens de 5 cartas | 2.598.960 mãos, 7.462 classes; 40 / 624 / 3.744 / 5.108 / 10.200 / 54.912 / 123.552 / 1.098.240 / 1.302.540 | combinatória padrão (C(52,5) e contagens clássicas das categorias) | exato | `unit/test_evaluator_exhaustive.py` |
| Avaliador: 7 cartas | ordem idêntica | oráculo independente `phevaluator` | exato | `property/test_evaluator_vs_phevaluator.py` |

## Regras do Leduc (iguais às da fonte)

Baralho J, J, Q, Q, K, K; ante 1 por jogador; uma carta privada por jogador; 1ª rodada de apostas
com aposta fixa 2; carta pública; 2ª rodada com aposta fixa 4; no máximo 2 apostas (bet + raise)
por rodada; o 1º jogador age primeiro nas duas rodadas. No showdown, par com a carta pública
vence; senão vence a maior carta; empate divide o pote.

## Convenção de valores

O motor mede utilidades como "fichas recebidas do pote menos fichas investidas no spot", com o
pote inicial `P` (antes) como dinheiro morto; logo `u₁ + u₂ = P`. O valor do jogo usual (lucro
líquido) é `u − P/2` quando os antes são iguais. Explotabilidade: `(BR₁ + BR₂ − P) / 2`, em % de
`P` (research R6).

## Equity (feature 001, research R10)

| Caso | Valor | Fonte | Tolerância | Teste |
|------|-------|-------|------------|-------|
| AA vs KK pré-flop (todos os combos) | 81,95% / 18,05% | enumeração exata, conferida pelo oráculo independente `phevaluator` (força bruta) | ±0,1 pp (SC-001) | `test_equity_reference.py` |
| Mão vs mão e mão vs range em todas as streets (~20 confrontos) | força bruta com `phevaluator` | oráculo independente | ±1e-9 | `test_equity_reference.py` |
| Equity por combo (range vs range e multiway pequeno) | força bruta com `phevaluator` | oráculo independente | ±1e-9 | `test_equity_reference.py` |
| Contagens de combos (`22+, A2s+, KTo+` = 162; `AA` com um ás morto = 3) | combinatória | — | exato | `unit/test_range_notation.py`, `api/.../test_ranges_api.py` |
