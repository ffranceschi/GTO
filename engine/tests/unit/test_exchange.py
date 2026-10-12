"""T084 — exportar/importar .npz (SC-006, Princípio VI)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from gto_engine.analysis.node_view import node_view
from gto_engine.cards import parse_card
from gto_engine.game.builder import build_tree
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.io import exchange
from gto_engine.io.exchange import Cancelled, export_npz, import_npz
from gto_engine.io.solution_dir import (
    ARRAYS,
    IncompatibleVersionError,
    SolutionFormatError,
    open_solution_dir,
    save_solution_dir,
    solution_from_result,
    spot_from_dict,
)
from gto_engine.ranges import parse_range
from gto_engine.solver.best_response import exploitability
from gto_engine.solver.dcfr import solve
from gto_engine.solver.params import SolveParams

TURN = tuple(parse_card(c) for c in ("Ks", "7d", "2c", "Jh"))


@pytest.fixture(scope="module")
def saved(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object]:
    spot = Spot(
        parse_range("AA, KK, 77, AK, KQs, QJs, T9s"), parse_range("QQ+, AK, KJ, 76s"), TURN, 10, 30
    )
    cfg = TreeConfig.uniform(bets=(0.75,), max_raises=1)
    tree = build_tree(spot, cfg)
    p = SolveParams(max_iterations=30, target_exploitability_pct=0.0)
    sol = solution_from_result(tree, spot, cfg, p, solve(tree, p))
    d = tmp_path_factory.mktemp("sol") / sol.meta.input_hash
    save_solution_dir(sol, d)
    return d, tree


class Ctl:
    def __init__(self, stop_after: int) -> None:
        self.calls = 0
        self.stop_after = stop_after

    def should_stop(self) -> bool:
        self.calls += 1
        return self.calls > self.stop_after

    def wait_if_paused(self) -> None:
        return None


def test_ida_e_volta_identica(saved, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    src, tree = saved
    out = tmp_path / "sol.npz"
    fracs: list[float] = []
    export_npz(src, out, on_progress=fracs.append)
    assert fracs[0] >= 0 and fracs[-1] == 1.0 and fracs == sorted(fracs)
    with np.load(out, allow_pickle=False) as z:  # legível pelo numpy
        assert set(ARRAYS) <= {k for k in z.files}
    dst = tmp_path / "importada"
    meta = import_npz(out, dst)
    a, b = open_solution_dir(src), open_solution_dir(dst)
    assert meta == a.meta == b.meta
    for name in ARRAYS:
        assert np.asarray(getattr(a, name)).tobytes() == np.asarray(getattr(b, name)).tobytes()
    assert node_view(tree, a, ["x", "b75"]) == node_view(tree, b, ["x", "b75"])
    # reexportar ⇒ conteúdo equivalente (Princípio VI)
    out2 = tmp_path / "sol2.npz"
    export_npz(dst, out2)
    with np.load(out, allow_pickle=False) as z1, np.load(out2, allow_pickle=False) as z2:
        for name in ARRAYS:
            np.testing.assert_array_equal(z1[name], z2[name])
        assert bytes(z1["meta.json"]) == bytes(z2["meta.json"])
    # explotabilidade recalculada = a registrada (spec US4 cenário 4)
    t2 = build_tree(spot_from_dict(b.meta.spot), TreeConfig.from_dict(b.meta.tree_config))
    assert exploitability(t2, np.asarray(b.strategy)) == pytest.approx(
        b.meta.final_exploitability_pct, abs=1e-9
    )


def test_arquivos_invalidos(saved, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    src, _ = saved
    bad = tmp_path / "x.npz"
    bad.write_bytes(b"isto nao e um zip")
    with pytest.raises(SolutionFormatError):
        import_npz(bad, tmp_path / "d1")
    out = tmp_path / "ok.npz"
    export_npz(src, out)
    # versão de formato incompatível
    alt = tmp_path / "v9.npz"
    with zipfile.ZipFile(out) as zin, zipfile.ZipFile(alt, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "meta.json.npy":
                arr = np.load(zin.open(item.filename), allow_pickle=False)
                meta = json.loads(bytes(arr))
                meta["format_version"] = "9.0"
                buf = tmp_path / "m.npy"
                np.save(buf, np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8))
                data = buf.read_bytes()
            zout.writestr(item, data)
    with pytest.raises(IncompatibleVersionError):
        import_npz(alt, tmp_path / "d2")
    # membro com pickle (dtype object) é recusado
    pick = tmp_path / "pickle.npz"
    np.savez(pick, strategy=np.array([{"a": 1}], dtype=object))
    with pytest.raises(SolutionFormatError):
        import_npz(pick, tmp_path / "d3")
    assert not (tmp_path / "d1").exists() and not (tmp_path / "d2").exists()


def test_cancelamento_sem_residuos(saved, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    src, _ = saved
    monkeypatch.setattr(exchange, "CHUNK_BYTES", 64)  # muitos blocos
    out = tmp_path / "c.npz"
    with pytest.raises(Cancelled):
        export_npz(src, out, control=Ctl(stop_after=3))
    assert not out.exists() and not list(tmp_path.glob("*.part"))
    ok = tmp_path / "ok.npz"
    export_npz(src, ok)
    dst = tmp_path / "dst"
    with pytest.raises(Cancelled):
        import_npz(ok, dst, control=Ctl(stop_after=3))
    assert not dst.exists() and not list(tmp_path.glob("dst*"))
