"""T017 — explotabilidade (research R6)."""

import numpy as np
import pytest

from gto_engine.solver.best_response import exploitability, game_value
from gto_engine.solver.strategy import set_node_strategy, uniform_strategy
from gto_engine.toy_games.kuhn import kuhn_tree

J, Q, K = 0, 1, 2


def _kuhn_equilibrio_alpha0():  # type: ignore[no-untyped-def]
    """Equilíbrio analítico de Kuhn com α = 0 (construído à mão)."""
    t = kuhn_tree()
    s = uniform_strategy(t)

    def put(path: list[str], probs: dict[str, list[float]]) -> None:
        n = t.node_at(path)
        ids = [a.id for a in t.actions(n)]
        m = np.array([probs[i] for i in ids])
        set_node_strategy(t, s, n, m)

    third = 1 / 3
    put([], {"x": [1, 1, 1], "b": [0, 0, 0]})  # P1 sempre check (α = 0)
    put(["x"], {"x": [1 - third, 1, 0], "b": [third, 0, 1]})  # P2 após check
    put(["b"], {"f": [1, 1 - third, 0], "c": [0, third, 1]})  # P2 contra bet
    put(["x", "b"], {"f": [1, 1 - third, 0], "c": [0, third, 1]})  # P1 após check-bet
    return t, s


def test_equilibrio_exato_tem_explotabilidade_zero() -> None:
    t, s = _kuhn_equilibrio_alpha0()
    # estratégias são armazenadas em float32 (1/3 não é exato): tolerância compatível
    assert exploitability(t, s) == pytest.approx(0.0, abs=1e-5)
    v1, _ = game_value(t, s)
    assert v1 - t.pot / 2 == pytest.approx(-1 / 18, abs=1e-6)


def test_uniforme_explotavel_e_nao_negativa() -> None:
    t = kuhn_tree()
    e = exploitability(t, uniform_strategy(t))
    assert e > 1.0  # muito explorável
    t2, s2 = _kuhn_equilibrio_alpha0()
    assert exploitability(t2, s2) >= -1e-12
