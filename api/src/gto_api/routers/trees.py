"""POST /trees/estimate — estimativa analítica (cálculo leve, ≤ 200 ms com benchmark — R3)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from gto_engine.cards import blocked_mask
from gto_engine.game.config import Street, TreeConfig
from gto_engine.game.estimate import TreeEstimate as EngineEstimate
from gto_engine.game.estimate import estimate_tree
from gto_engine.game.tree import Spot

from gto_api.errors import fmt_num
from gto_api.schemas.solves import Problem, SpotWithTree
from gto_api.schemas.trees import TreeEstimate

router = APIRouter(prefix="/api/v1", tags=["trees"])
GIB = 1024**3


def suggestions(spot: Spot, cfg: TreeConfig, est: EngineEstimate, max_bytes: int) -> list[str]:
    if est.estimated_bytes <= max_bytes:
        return []
    out: list[str] = []
    n_bets = max(len(v) for m in cfg.bet_sizes.values() for v in m.values())
    n_raises = max(len(v) for m in cfg.raise_sizes.values() for v in m.values())
    if n_bets > 1 or n_raises > 1:
        out.append(
            f"Use menos tamanhos de aposta por street (hoje: até {n_bets} de bet "
            f"e {n_raises} de raise)."
        )
    else:
        out.append(
            "Use menos tamanhos de aposta (por exemplo, só nas streets que você quer estudar)."
        )
    if cfg.max_raises_per_street > 1:
        out.append(f"Reduza o limite de raises por street (hoje: {cfg.max_raises_per_street}).")
    else:
        out.append("Mantenha o limite de raises por street em 1 ou 0.")
    blocked = blocked_mask(spot.board)
    combos = [int(((r.weights > 0) & ~blocked).sum()) for r in (spot.oop_range, spot.ip_range)]
    out.append(f"Reduza os ranges (hoje: {combos[0]} combos OOP e {combos[1]} IP).")
    if spot.street == Street.FLOP:
        out.append("Ou resolva a partir do turn, que exige bem menos memória.")
    out.append(
        f"Memória estimada: {fmt_num(est.estimated_bytes / GIB)} GiB; "
        f"limite: {fmt_num(max_bytes / GIB)} GiB."
    )
    return out


@router.post(
    "/trees/estimate",
    operation_id="estimateTree",
    response_model=TreeEstimate,
    responses={422: {"model": Problem}},
)
def estimate(req: SpotWithTree, request: Request) -> TreeEstimate:
    max_bytes = request.app.state.settings.max_solve_memory_bytes
    spot = req.spot.to_engine()
    cfg = req.tree.to_engine()
    est = estimate_tree(spot, cfg)
    return TreeEstimate(
        decision_nodes=est.decision_nodes,
        chance_nodes=est.chance_nodes,
        terminal_nodes=est.terminal_nodes,
        estimated_bytes=est.estimated_bytes,
        estimated_solution_bytes=est.estimated_solution_bytes,
        max_bytes=max_bytes,
        within_limit=est.estimated_bytes <= max_bytes,
        isomorphism_factor=est.isomorphism_factor,
        suggestions=suggestions(spot, cfg, est, max_bytes),
    )
