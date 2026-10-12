"""T004 — validação de EquityRequest (FR-013 a FR-015, edge cases)."""

from __future__ import annotations

import pytest

from gto_engine.cards import parse_card
from gto_engine.equity.request import EquityRequest, InvalidEquityRequestError
from gto_engine.ranges import parse_range


def req(*ranges: str, board: str = "", **kw: object) -> EquityRequest:
    return EquityRequest(
        tuple(parse_range(r) for r in ranges),
        tuple(parse_card(c) for c in board.split()),
        **kw,  # type: ignore[arg-type]
    )


def test_validos() -> None:
    req("AA", "KK")
    req("AA", "KK", "QQ", "JJ", "TT", "99")
    for b in ("", "Ks 7d 2c", "Ks 7d 2c Jh", "Ks 7d 2c Jh 3s"):
        req("AA", "KK", board=b)
    req("AA", "KK", target_margin_pp=0.05, time_limit_s=3600)


@pytest.mark.parametrize(
    ("args", "kwargs", "trecho"),
    [
        (("AA",), {}, "2 a 6"),
        (("AA", "KK", "QQ", "JJ", "TT", "99", "88"), {}, "2 a 6"),
        (("AA", "KK"), {"board": "Ks 7d"}, "board"),
        (("AA", "KK"), {"board": "Ks Ks 2c"}, "repetid"),
        (("AA", "KK"), {"target_margin_pp": 0.01}, "margem"),
        (("AA", "KK"), {"target_margin_pp": 2.0}, "margem"),
        (("AA", "KK"), {"time_limit_s": 0}, "tempo"),
        (("AA", "KK"), {"method": "rapido"}, "método"),
        (("AhKh", "AhQd"), {}, "Ah"),  # carta duplicada entre mãos específicas
        (("AhKh", "QQ"), {"board": "Kh 7d 2c"}, "Kh"),  # mão específica x board
        (("AA", "KK"), {"board": "As Ah Ad 8d 2c"}, "Participante 1"),  # sem combos
        (("22, 33", "22, 33"), {"board": "2s 2h 2d 2c 3s"}, "confronto"),
        (("AhAd", "AsAc", "AA"), {}, "Participante 3"),  # bloqueado pelas mãos dos outros
    ],
)
def test_invalidos_pt_br(args: tuple[str, ...], kwargs: dict[str, object], trecho: str) -> None:
    with pytest.raises(InvalidEquityRequestError) as exc:
        req(*args, **kwargs)  # type: ignore[arg-type]
    assert trecho in str(exc.value)


def test_mao_especifica_bloqueia_os_outros() -> None:
    r = req("AhKh", "AA, KK")
    w = r.participant_weights(1)
    assert w.sum() == pytest.approx(3 + 3)  # AA perde os combos com Ah; KK perde os com Kh
