"""T011 — TreeConfig: padrão e validações do data-model."""

import pytest

from gto_engine.game.config import (
    InvalidTreeConfigError,
    Position,
    Street,
    TreeConfig,
    default_tree_config,
)


def test_padrao() -> None:
    c = default_tree_config()
    for st in Street:
        for pos in Position:
            assert c.bet_sizes[st][pos] == (0.33, 0.75)
            assert c.raise_sizes[st][pos] == (1.0,)
    assert c.max_raises_per_street == 3
    assert c.allin_threshold == 0.67
    assert c.add_allin_action is False
    assert c.allow_donk is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bets": (0.0,)},  # frações em (0, 10]
        {"bets": (10.5,)},
        {"bets": (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)},  # até 5 por lista
        {"raises": (-1.0,)},
        {"max_raises": 7},  # 0–6
        {"max_raises": -1},
        {"threshold": 0.0},  # (0, 1]
        {"threshold": 1.01},
        {"name": ""},  # 1–60 caracteres se presente
        {"name": "x" * 61},
    ],
)
def test_validacoes(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidTreeConfigError) as exc:
        TreeConfig.uniform(**kwargs)  # type: ignore[arg-type]
    assert str(exc.value)  # mensagem em pt-BR


def test_valores_validos_limites() -> None:
    TreeConfig.uniform(bets=(10.0,), raises=(0.01,), max_raises=0, threshold=1.0, name="x" * 60)
    TreeConfig.uniform(max_raises=6)
