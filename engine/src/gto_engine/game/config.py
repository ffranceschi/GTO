"""Configuração da árvore de apostas (FR-004 a FR-008, data-model TreeConfig)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class Street(StrEnum):
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class Position(StrEnum):
    OOP = "oop"
    IP = "ip"


class InvalidTreeConfigError(ValueError):
    """Configuração de árvore inválida (mensagem em pt-BR)."""


Sizes = Mapping[Street, Mapping[Position, tuple[float, ...]]]


def _freeze(sizes: Mapping[Street, Mapping[Position, tuple[float, ...]]]) -> Sizes:
    return MappingProxyType(
        {
            Street(s): MappingProxyType({Position(p): tuple(v) for p, v in m.items()})
            for s, m in sizes.items()
        }
    )


def _check_sizes(sizes: Sizes, what: str) -> None:
    for st in Street:
        for pos in Position:
            vals = sizes.get(st, {}).get(pos, ())
            if len(vals) > 5:
                raise InvalidTreeConfigError(
                    f"No máximo 5 tamanhos de {what} por lista ({st}, {pos.upper()})."
                )
            for v in vals:
                if not (0 < v <= 10):
                    raise InvalidTreeConfigError(
                        f"Tamanho de {what} inválido: {v:g} ({st}, {pos.upper()}). "
                        "Use frações do pote em (0, 10]."
                    )


@dataclass(frozen=True)
class TreeConfig:
    bet_sizes: Sizes
    raise_sizes: Sizes
    max_raises_per_street: int = 3
    allin_threshold: float = 0.67
    add_allin_action: bool = False
    allow_donk: bool = False
    name: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bet_sizes", _freeze(self.bet_sizes))
        object.__setattr__(self, "raise_sizes", _freeze(self.raise_sizes))
        _check_sizes(self.bet_sizes, "bet")
        _check_sizes(self.raise_sizes, "raise")
        if not (0 <= self.max_raises_per_street <= 6):
            raise InvalidTreeConfigError("O limite de raises por street deve estar entre 0 e 6.")
        if not (0 < self.allin_threshold <= 1):
            raise InvalidTreeConfigError("O all-in threshold deve estar em (0, 1].")
        if self.name is not None and not (1 <= len(self.name) <= 60):
            raise InvalidTreeConfigError("O nome da configuração deve ter de 1 a 60 caracteres.")

    @classmethod
    def uniform(
        cls,
        bets: tuple[float, ...] = (0.33, 0.75),
        raises: tuple[float, ...] = (1.0,),
        max_raises: int = 3,
        threshold: float = 0.67,
        add_allin: bool = False,
        donk: bool = False,
        name: str | None = None,
    ) -> TreeConfig:
        """Mesmos tamanhos em todas as streets e posições."""
        b = {st: {pos: tuple(bets) for pos in Position} for st in Street}
        r = {st: {pos: tuple(raises) for pos in Position} for st in Street}
        return cls(b, r, max_raises, threshold, add_allin, donk, name)

    def to_dict(self) -> dict[str, object]:
        return {
            "bet_sizes": {
                s.value: {p.value: list(v) for p, v in m.items()} for s, m in self.bet_sizes.items()
            },
            "raise_sizes": {
                s.value: {p.value: list(v) for p, v in m.items()}
                for s, m in self.raise_sizes.items()
            },
            "max_raises_per_street": self.max_raises_per_street,
            "allin_threshold": self.allin_threshold,
            "add_allin_action": self.add_allin_action,
            "allow_donk": self.allow_donk,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, object], name: str | None = None) -> TreeConfig:
        def sizes(raw: object) -> dict[Street, dict[Position, tuple[float, ...]]]:
            out: dict[Street, dict[Position, tuple[float, ...]]] = {}
            assert isinstance(raw, Mapping)
            for s, m in raw.items():
                out[Street(s)] = {Position(p): tuple(float(x) for x in v) for p, v in m.items()}
            return out

        return cls(
            sizes(d["bet_sizes"]),
            sizes(d["raise_sizes"]),
            int(d.get("max_raises_per_street", 3)),  # type: ignore[call-overload]
            float(d.get("allin_threshold", 0.67)),  # type: ignore[arg-type]
            bool(d.get("add_allin_action", False)),
            bool(d.get("allow_donk", False)),
            name,
        )


def default_tree_config() -> TreeConfig:
    """Padrão (FR-010): bets 33% e 75%, raise 100%, 3 raises, threshold 0,67, sem donk/all-in."""
    return TreeConfig.uniform(name="Padrão")
