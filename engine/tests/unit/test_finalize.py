"""T047 — finalização: EV e equity por combo (R3 item 3, R15; Princípio I)."""

from __future__ import annotations

import time

import numpy as np
import pytest
from phevaluator import evaluate_cards

from gto_engine.cards import COMBO_CARDS, card_str, parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range
from gto_engine.solver.best_response import game_value
from gto_engine.solver.dcfr import solve
from gto_engine.solver.finalize import SolveCancelled
from gto_engine.solver.params import SolveParams
from gto_engine.solver.strategy import node_strategy
from gto_engine.toy_games.kuhn import kuhn_tree
from gto_engine.toy_games.leduc import leduc_tree

BOARD = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh", "3s"))


def small_river():  # type: ignore[no-untyped-def]
    spot = Spot(
        parse_range("AA, KK, 77, AK, KQs, QJs, T9s"), parse_range("QQ+, AK, KJ, 76s"), BOARD, 10, 30
    )
    return build_tree(spot, TreeConfig.uniform(bets=(0.5, 1.0), raises=(1.0,), max_raises=2))


def root_ev(tree, r, player: int = 0) -> float:  # type: ignore[no-untyped-def]
    """EV agregado na raiz do jogador 0, ponderado por peso × reach compatível do oponente."""
    from gto_engine.solver.kernels import compat_sums

    T = tree.kernel
    sl = tree.combo_slice(tree.root)
    compat = compat_sums(T.w1, T.hc0, T.hc1, T.same0, T.n_cards, T.k)
    w = T.w0 * compat
    return float((w * r.ev[sl]).sum() / w.sum())


def test_estrategia_normalizada_e_ev_consistente() -> None:
    tree = small_river()
    r = solve(tree, SolveParams(max_iterations=200, target_exploitability_pct=0.0))
    for node in tree.dec_node:
        np.testing.assert_allclose(
            node_strategy(tree, r.strategy, int(node)).sum(axis=0), 1, atol=1e-4
        )
    v0, _ = game_value(tree, r.strategy)
    assert root_ev(tree, r) == pytest.approx(v0, abs=1e-3)


def _brute_equity(hand: int, opp_hands: np.ndarray, opp_reach: np.ndarray) -> float:
    h1, h2 = (card_str(int(c)) for c in COMBO_CARDS[hand])
    b = [card_str(c) for c in BOARD]
    num = den = 0.0
    mine = evaluate_cards(h1, h2, *b)
    for o, w in zip(opp_hands, opp_reach, strict=True):
        if w == 0 or set(COMBO_CARDS[o]) & set(COMBO_CARDS[hand]):
            continue
        theirs = evaluate_cards(*(card_str(int(c)) for c in COMBO_CARDS[o]), *b)
        num += w * (1.0 if mine < theirs else 0.5 if mine == theirs else 0.0)
        den += w
    return num / den


def test_equity_igual_forca_bruta_phevaluator() -> None:
    tree = small_river()
    r = solve(tree, SolveParams(max_iterations=100, target_exploitability_pct=0.0))
    # raiz (OOP): range do oponente que chega = range inicial do IP
    sl = tree.combo_slice(tree.root)
    for i, h in enumerate(tree.players.hands[0]):
        want = _brute_equity(int(h), tree.players.hands[1], tree.players.weights[1])
        assert r.equity[sl][i] == pytest.approx(want, abs=1e-6)
    # nó IP após check: o range de OOP que chega = peso × frequência de check
    n = tree.node_at(["x"])
    sig = node_strategy(tree, r.strategy, tree.root)
    reach_oop = tree.players.weights[0] * sig[0]
    sl = tree.combo_slice(n)
    for i, h in enumerate(tree.players.hands[1]):
        want = _brute_equity(int(h), tree.players.hands[0], reach_oop)
        assert r.equity[sl][i] == pytest.approx(want, abs=1e-6)


@pytest.mark.parametrize(
    ("make", "value", "tol", "iters"),
    [
        (kuhn_tree, -1 / 18, 0.001, 3000),
        (leduc_tree, -0.085606424078, 0.005, 4000),
    ],
)
def test_ev_de_referencia_kuhn_e_leduc(make, value: float, tol: float, iters: int) -> None:  # type: ignore[no-untyped-def]
    """REFERENCES.md: Kuhn 1950 e Lanctot et al. 2017 (EV ancorado no valor do jogo)."""
    tree = make()
    r = solve(tree, SolveParams(max_iterations=iters, target_exploitability_pct=0.0))
    assert root_ev(tree, r) - tree.pot / 2 == pytest.approx(value, abs=tol)


def test_pico_da_finalizacao_nao_passa_do_treino() -> None:
    tree = small_river()
    r = solve(tree, SolveParams(max_iterations=10, target_exploitability_pct=0.0))
    assert r.peak_finalize_bytes <= r.peak_train_bytes


class CancelDuringFinalize:
    def __init__(self) -> None:
        self.finalizing = False
        self.cancel_at: float | None = None

    def should_stop(self) -> bool:
        return self.finalizing

    def wait_if_paused(self) -> None:
        return None

    def is_cancelled(self) -> bool:
        return self.cancel_at is not None


def test_cancelar_na_finalizacao_e_fracao_crescente() -> None:
    from gto_engine.solver import finalize as fin

    tree = leduc_tree()
    fracs: list[float] = []
    ctl = CancelDuringFinalize()

    def prog(p) -> None:  # type: ignore[no-untyped-def]
        if p.phase == "finalizing":
            fracs.append(p.finalize_fraction)
            if p.finalize_fraction > 0 and ctl.cancel_at is None:
                ctl.cancel_at = time.perf_counter()

    old = fin.CHUNK_NODES
    fin.CHUNK_NODES = 5  # força vários blocos na árvore pequena
    try:
        r = solve(tree, SolveParams(max_iterations=50, target_exploitability_pct=0.0))
        assert r.ev is not None
        with pytest.raises(SolveCancelled):
            solve(
                tree,
                SolveParams(max_iterations=50, target_exploitability_pct=0.0),
                control=ctl,
                on_progress=prog,
            )
        assert ctl.cancel_at is not None and time.perf_counter() - ctl.cancel_at < 0.5
        fr2: list[float] = []
        solve(
            tree,
            SolveParams(max_iterations=20, target_exploitability_pct=0.0),
            on_progress=lambda p: (
                fr2.append(p.finalize_fraction) if p.phase == "finalizing" else None
            ),
        )
        assert fr2[0] == 0.0 and fr2[-1] == 1.0 and fr2 == sorted(fr2)
    finally:
        fin.CHUNK_NODES = old
    assert fracs and fracs[0] == 0.0  # o cancelamento veio depois do 1º bloco da finalização
