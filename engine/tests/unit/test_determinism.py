"""T018 — determinismo (Princípio VI): mesma entrada + parâmetros + iterações ⇒ bytes idênticos."""

import numba
import pytest

from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams
from gto_engine.toy_games.leduc import leduc_tree


@pytest.mark.parametrize("algorithm", ["dcfr", "cfr_plus", "linear_cfr"])
def test_bytes_identicos(algorithm: str) -> None:
    outs = []
    for threads in (1, min(4, numba.config.NUMBA_NUM_THREADS)):
        numba.set_num_threads(threads)
        for _ in range(2):
            r = solve(
                leduc_tree(),
                SolveParams(algorithm=algorithm, max_iterations=200, target_exploitability_pct=0.0),
            )  # type: ignore[arg-type]
            outs.append(r.strategy.tobytes())
    numba.set_num_threads(numba.config.NUMBA_NUM_THREADS)
    assert all(o == outs[0] for o in outs)
