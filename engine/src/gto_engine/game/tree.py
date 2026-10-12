"""Spot e árvore de jogo vetorizada (nós de decisão × mãos privadas)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import numpy as np

from gto_engine.cards import N_CARDS, blocked_mask, card_str
from gto_engine.game.config import Street
from gto_engine.ranges import Range


class InvalidSpotError(ValueError):
    """Spot inválido (mensagem em pt-BR)."""


class InvalidPathError(ValueError):
    """Caminho de nó inexistente na árvore (mensagem em pt-BR)."""


MAX_BB = 10_000.0


@dataclass(frozen=True)
class Spot:
    oop_range: Range
    ip_range: Range
    board: tuple[int, ...]
    pot: float
    effective_stack: float

    def __post_init__(self) -> None:
        board = tuple(int(c) for c in self.board)
        object.__setattr__(self, "board", board)
        if not (0 < self.pot <= MAX_BB):
            raise InvalidSpotError("O pote deve ser maior que 0 e no máximo 10.000 bb.")
        if not (0 <= self.effective_stack <= MAX_BB):
            raise InvalidSpotError("O stack efetivo deve estar entre 0 e 10.000 bb.")
        if len(board) not in (3, 4, 5):
            raise InvalidSpotError("O board deve ter 3 (flop), 4 (turn) ou 5 (river) cartas.")
        if len(set(board)) != len(board) or any(not 0 <= c < N_CARDS for c in board):
            raise InvalidSpotError(
                "O board tem carta repetida ou inválida: "
                + " ".join(card_str(c) for c in board if 0 <= c < N_CARDS)
            )
        blocked = blocked_mask(board)
        for name, r in (("OOP", self.oop_range), ("IP", self.ip_range)):
            if float(np.where(blocked, 0.0, r.weights).sum()) <= 0:
                raise InvalidSpotError(
                    f"O range {name} não tem combos possíveis depois dos bloqueios do board."
                )

    @property
    def street(self) -> Street:
        return {3: Street.FLOP, 4: Street.TURN, 5: Street.RIVER}[len(self.board)]


@dataclass(frozen=True)
class Action:
    kind: str  # check | bet | call | raise | fold | allin | (chance: "card")
    id: str
    amount: float
    pot_fraction: float | None
    label: str


NODE_DECISION, NODE_CHANCE, NODE_FOLD, NODE_SHOWDOWN = 0, 1, 2, 3
_KIND = {
    NODE_DECISION: "decision",
    NODE_CHANCE: "chance",
    NODE_FOLD: "fold",
    NODE_SHOWDOWN: "showdown",
}
PLAYERS = ("oop", "ip")


@dataclass
class _Node:
    kind: int
    player: int = -1  # decisão: quem age; fold: quem desistiu
    inv: tuple[float, float] = (0.0, 0.0)  # investido no spot (todas as streets)
    actions: list[Action] = field(default_factory=list)
    children: list[int] = field(default_factory=list)
    board_id: int = -1  # showdown: índice do board final
    chance_card: int = -1  # carta revelada ao chegar neste nó (-1 se nenhuma)
    chance_factor: float = 0.0  # nós de chance: 1 / nº de cartas possíveis dado as mãos
    boards: tuple[int, ...] = ()  # decisão: boards finais possíveis (para a equity do nó)


class TreeAssembler:
    """Monta a árvore nó a nó (usado pelo builder NL e pelos jogos de validação)."""

    def __init__(self) -> None:
        self.nodes: list[_Node] = []

    def add(self, node: _Node) -> int:
        self.nodes.append(node)
        return len(self.nodes) - 1

    def link(self, parent: int, action: Action, child: int) -> None:
        self.nodes[parent].actions.append(action)
        self.nodes[parent].children.append(child)


@dataclass
class Players:
    """Mãos privadas dos dois jogadores (combos do hold'em ou cartas nos jogos de validação)."""

    hands: tuple[np.ndarray, np.ndarray]  # identificadores (ex.: índice do combo 0..1325)
    hand_cards: tuple[np.ndarray, np.ndarray]  # (n_p, k) cartas de cada mão
    weights: tuple[np.ndarray, np.ndarray]  # pesos iniciais (range)
    n_cards: int  # tamanho do baralho


class GameTree:
    def __init__(
        self,
        assembler: TreeAssembler,
        players: Players,
        pot: float,
        boards: list[tuple[int, ...]],
        strengths: tuple[np.ndarray, np.ndarray],
        street: Street = Street.RIVER,
        hand_label: Any = None,
    ) -> None:
        self._nodes = assembler.nodes
        self.players = players
        self.pot = float(pot)
        self.boards = boards
        self.street = street
        self._hand_label = hand_label
        self.effective_stack = 0.0
        self.root = 0
        n = len(self._nodes)
        self.node_type = np.array([nd.kind for nd in self._nodes], dtype=np.int64)
        self.node_player = np.array([nd.player for nd in self._nodes], dtype=np.int64)
        self.child_start = np.zeros(n, dtype=np.int64)
        self.child_count = np.zeros(n, dtype=np.int64)
        kids: list[int] = []
        for i, nd in enumerate(self._nodes):
            self.child_start[i] = len(kids)
            self.child_count[i] = len(nd.children)
            kids += nd.children
        self.children_arr = np.array(kids, dtype=np.int64)
        self.inv = np.array([nd.inv for nd in self._nodes], dtype=np.float64).reshape(n, 2)
        self.board_id = np.array([nd.board_id for nd in self._nodes], dtype=np.int64)
        self.chance_card = np.array([nd.chance_card for nd in self._nodes], dtype=np.int64)
        self.chance_factor = np.array([nd.chance_factor for nd in self._nodes], dtype=np.float64)
        # layout das decisões
        self.dec_index = -np.ones(n, dtype=np.int64)
        offs: list[int] = []
        coffs: list[int] = []
        nodes: list[int] = []
        o = co = 0
        for i, nd in enumerate(self._nodes):
            if nd.kind == NODE_DECISION:
                self.dec_index[i] = len(nodes)
                nodes.append(i)
                offs.append(o)
                coffs.append(co)
                nh = len(players.hands[nd.player])
                o += len(nd.children) * nh
                co += nh
        self.dec_node = np.array(nodes, dtype=np.int64)
        bstart: list[int] = []
        bflat: list[int] = []
        for i in nodes:
            bstart.append(len(bflat))
            bflat += list(self._nodes[i].boards) or [0]
        self.dec_board_start = np.array([*bstart, len(bflat)], dtype=np.int64)
        self.dec_boards = np.array(bflat, dtype=np.int64)
        # tamanho da subárvore (para fatiar a finalização em blocos)
        size = np.ones(n, dtype=np.int64)
        for i in range(n - 1, -1, -1):
            for c in self._nodes[i].children:
                size[i] += size[c]
        self.subtree_size = size
        self.dec_offset = np.array([*offs, o], dtype=np.int64)
        self.dec_combo_offset = np.array([*coffs, co], dtype=np.int64)
        self.strategy_size = o
        self.combo_size = co
        self.strengths = strengths  # (n_boards, n_p) int32 por jogador; -1 = bloqueado
        self.orders = tuple(
            np.argsort(s, axis=1, kind="stable").astype(np.int64) for s in strengths
        )

    # ---- consulta ----
    @property
    def n_nodes(self) -> int:
        return len(self._nodes)

    @property
    def n_decision_nodes(self) -> int:
        return len(self.dec_node)

    def n_hands(self, player: str | int) -> int:
        p = PLAYERS.index(player) if isinstance(player, str) else player
        return len(self.players.hands[p])

    def decision_shapes(self) -> list[tuple[int, int]]:
        return [(len(self._nodes[i].children), self._nodes[i].player) for i in self.dec_node]

    def node_kind(self, node: int) -> str:
        return _KIND[self._nodes[node].kind]

    def player(self, node: int) -> str:
        return PLAYERS[self._nodes[node].player]

    def player_index(self, node: int) -> int:
        return self._nodes[node].player

    def actions(self, node: int) -> list[Action]:
        return list(self._nodes[node].actions)

    def children(self, node: int) -> list[int]:
        return list(self._nodes[node].children)

    def investments(self, node: int) -> tuple[float, float]:
        a, b = self._nodes[node].inv
        return float(a), float(b)

    def pot_at(self, node: int) -> float:
        a, b = self._nodes[node].inv
        return float(self.pot + a + b)

    def child(self, node: int, action_id: str) -> int:
        nd = self._nodes[node]
        for a, c in zip(nd.actions, nd.children, strict=True):
            if a.id == action_id:
                return c
        raise InvalidPathError(f"A ação '{action_id}' não existe neste nó.")

    def node_at(self, path: Sequence[str]) -> int:
        n = self.root
        for step in path:
            if self._nodes[n].kind in (NODE_FOLD, NODE_SHOWDOWN):
                raise InvalidPathError(f"O caminho continua depois de um nó terminal ('{step}').")
            n = self.child(n, step)
        return n

    def path_to(self, node: int) -> list[str]:
        parent = {
            c: (i, a.id)
            for i, nd in enumerate(self._nodes)
            for a, c in zip(nd.actions, nd.children, strict=True)
        }
        out: list[str] = []
        while node != self.root:
            node, aid = parent[node]
            out.append(aid)
        return out[::-1]

    def strategy_slice(self, node: int) -> slice:
        d = int(self.dec_index[node])
        if d < 0:
            raise InvalidPathError("O nó não é de decisão.")
        return slice(int(self.dec_offset[d]), int(self.dec_offset[d + 1]))

    def combo_slice(self, node: int) -> slice:
        d = int(self.dec_index[node])
        return slice(int(self.dec_combo_offset[d]), int(self.dec_combo_offset[d + 1]))

    def hand_label(self, player: int, i: int) -> str:
        if self._hand_label is not None:
            return str(self._hand_label(player, i))
        return str(int(self.players.hands[player][i]))

    @cached_property
    def kernel(self) -> Any:
        from gto_engine.solver.arrays import kernel_tree

        return kernel_tree(self)
