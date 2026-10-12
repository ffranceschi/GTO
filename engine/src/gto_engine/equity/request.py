"""Entrada do cálculo de equity e sua validação (FR-013 a FR-015)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from gto_engine.cards import COMBO_CARDS, N_CARDS, blocked_mask, card_str, combo_conflicts
from gto_engine.ranges import Range

Method = Literal["auto", "exact", "monte_carlo"]
VALID_BOARD = (0, 3, 4, 5)


class InvalidEquityRequestError(ValueError):
    """Entrada de equity inválida (mensagem em pt-BR)."""


def _label(i: int) -> str:
    return f"Participante {i + 1}"


@dataclass(frozen=True)
class EquityRequest:
    participants: tuple[Range, ...]
    board: tuple[int, ...] = ()
    method: Method = "auto"
    target_margin_pp: float = 0.1
    time_limit_s: float = 60.0
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "board", tuple(int(c) for c in self.board))
        n = len(self.participants)
        if not 2 <= n <= 6:
            raise InvalidEquityRequestError("Informe de 2 a 6 participantes.")
        if len(self.board) not in VALID_BOARD:
            raise InvalidEquityRequestError(
                "O board deve ter 0, 3 (flop), 4 (turn) ou 5 (river) cartas."
            )
        if len(set(self.board)) != len(self.board) or any(not 0 <= c < N_CARDS for c in self.board):
            raise InvalidEquityRequestError("O board tem carta repetida ou inválida.")
        if self.method not in ("auto", "exact", "monte_carlo"):
            raise InvalidEquityRequestError(
                f"O método deve ser auto, exact ou monte_carlo (recebido: {self.method})."
            )
        if not 0.05 <= self.target_margin_pp <= 1.0:
            raise InvalidEquityRequestError(
                "A margem-alvo deve estar entre 0,05 e 1 ponto percentual."
            )
        if not 0 < self.time_limit_s <= 3600:
            raise InvalidEquityRequestError("O tempo-limite deve estar entre 0 e 3.600 segundos.")
        if not 0 <= self.seed < 2**64:
            raise InvalidEquityRequestError("A semente deve estar entre 0 e 2^64 − 1.")
        self._check_cards()

    # ---- validação ----
    def specific_hands(self) -> dict[int, tuple[int, int]]:
        """Participantes com mão específica (exatamente 1 combo com peso > 0)."""
        out: dict[int, tuple[int, int]] = {}
        for i, r in enumerate(self.participants):
            nz = np.flatnonzero(r.weights > 0)
            if len(nz) == 1:
                a, b = COMBO_CARDS[nz[0]]
                out[i] = (int(a), int(b))
        return out

    def _check_cards(self) -> None:
        specific = self.specific_hands()
        seen: dict[int, str] = {c: "board" for c in self.board}
        for i, cards in specific.items():
            for c in cards:
                if c in seen:
                    raise InvalidEquityRequestError(
                        f"Carta duplicada: {card_str(c)} aparece no {_label(i)} e em {seen[c]}."
                    )
                seen[c] = _label(i)
        for i in range(len(self.participants)):
            if self.participant_weights(i).sum() <= 0:
                raise InvalidEquityRequestError(
                    f"O {_label(i)} não tem combos possíveis depois dos bloqueios do board "
                    "e das mãos conhecidas."
                )
        if not self._has_compatible_tuple():
            raise InvalidEquityRequestError(
                "Não há confronto possível: nenhuma combinação de mãos sem cartas repetidas "
                "entre os participantes."
            )

    def dead_cards_for(self, i: int) -> list[int]:
        """Board + cartas das mãos específicas dos outros participantes."""
        dead = list(self.board)
        for j, cards in self.specific_hands().items():
            if j != i:
                dead += list(cards)
        return dead

    def participant_weights(self, i: int) -> np.ndarray:
        w = self.participants[i].weights
        return np.where(blocked_mask(self.dead_cards_for(i)), 0.0, w)

    def participant_combos(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        """(índices dos combos, pesos) com peso > 0 após bloqueios."""
        w = self.participant_weights(i)
        idx = np.flatnonzero(w > 0).astype(np.int64)
        return idx, w[idx]

    def _has_compatible_tuple(self) -> bool:
        conflict = combo_conflicts()
        sets = [self.participant_combos(i)[0] for i in range(len(self.participants))]
        order = sorted(range(len(sets)), key=lambda k: len(sets[k]))
        budget = [200_000]  # busca com poda; acima do orçamento assume que existe

        def dfs(level: int, chosen: list[int]) -> bool:
            if level == len(order):
                return True
            for c in sets[order[level]]:
                budget[0] -= 1
                if budget[0] < 0:
                    return True
                if any(conflict[c, x] for x in chosen):
                    continue
                if dfs(level + 1, [*chosen, int(c)]):
                    return True
            return False

        return dfs(0, [])
