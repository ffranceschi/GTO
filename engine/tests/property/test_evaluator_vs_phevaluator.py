"""T009 — avaliador de 7 cartas contra o oráculo independente phevaluator (Princípio I)."""

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st
from phevaluator import evaluate_cards

from gto_engine.cards import card_str
from gto_engine.evaluator.kernels import eval5, eval7

sete_cartas = st.lists(st.integers(0, 51), min_size=7, max_size=7, unique=True)


def _ph(cards: list[int]) -> int:
    # phevaluator: menor = melhor
    return int(evaluate_cards(*[card_str(c) for c in cards]))


@settings(max_examples=3000, deadline=None)
@given(sete_cartas, sete_cartas)
def test_ordem_igual_ao_phevaluator(a: list[int], b: list[int]) -> None:
    ours = (eval7(*a) > eval7(*b)) - (eval7(*a) < eval7(*b))
    theirs = (_ph(a) < _ph(b)) - (_ph(a) > _ph(b))
    assert ours == theirs


@settings(max_examples=500, deadline=None)
@given(sete_cartas, st.randoms())
def test_independe_da_ordem(cards: list[int], rnd) -> None:  # type: ignore[no-untyped-def]
    perm = cards[:]
    rnd.shuffle(perm)
    assert eval7(*cards) == eval7(*perm)


@settings(max_examples=300, deadline=None)
@given(sete_cartas)
def test_sete_cartas_e_melhor_das_21(cards: list[int]) -> None:
    melhor = max(eval5(*c) for c in itertools.combinations(cards, 5))
    assert eval7(*cards) == melhor
