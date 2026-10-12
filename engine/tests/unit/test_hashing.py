"""T013 — input_hash canônico (Princípio VI)."""

import dataclasses

from gto_engine.cards import parse_card
from gto_engine.game.config import TreeConfig
from gto_engine.game.hashing import input_hash
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.params import SolveParams

B = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))
B_PERM = tuple(parse_card(c) for c in ("2c", "Ks", "7d", "Jh", "3s"))


def base() -> tuple[Spot, TreeConfig, SolveParams]:
    return (
        Spot(parse_range("22+, AKs"), parse_range("QQ+"), B, 10, 50),
        TreeConfig.uniform(bets=(0.5,)),
        SolveParams(),
    )


def test_formato() -> None:
    h = input_hash(*base())
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_ordem_do_flop_nao_importa() -> None:
    s, c, p = base()
    s2 = dataclasses.replace(s, board=B_PERM)
    assert input_hash(s, c, p) == input_hash(s2, c, p)


def test_qualquer_mudanca_altera() -> None:
    s, c, p = base()
    h = input_hash(s, c, p)
    w = s.oop_range.weights.copy()
    w[0] = 0.5
    variantes = [
        (dataclasses.replace(s, oop_range=type(s.oop_range)(w)), c, p),
        (dataclasses.replace(s, pot=11), c, p),
        (dataclasses.replace(s, effective_stack=51), c, p),
        (s, TreeConfig.uniform(bets=(0.75,)), p),
        (s, c, dataclasses.replace(p, algorithm="cfr_plus")),
        (s, c, dataclasses.replace(p, alpha=1.0)),
        (s, c, dataclasses.replace(p, seed=1)),
    ]
    for v in variantes:
        assert input_hash(*v) != h
    assert input_hash(s, c, p, engine_version="9.9.9") != h


def test_notacao_e_vetor_equivalentes() -> None:
    s, c, p = base()
    s2 = dataclasses.replace(s, oop_range=type(s.oop_range)(s.oop_range.weights.copy()))
    assert input_hash(s, c, p) == input_hash(s2, c, p)
