"""Spot e árvore de jogo vetorizada (nós de decisão × mãos privadas)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import numpy as np

from gto_engine.cards import N_CARDS, blocked_mask, card_str, combo_conflicts
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
        w0 = np.where(blocked, 0.0, self.oop_range.weights)
        w1 = np.where(blocked, 0.0, self.ip_range.weights)
        i0, i1 = np.flatnonzero(w0), np.flatnonzero(w1)
        free = ~combo_conflicts()[np.ix_(i0, i1)]
        if float((w0[i0][:, None] * w1[i1][None, :] * free).sum()) <= 0:
            raise InvalidSpotError(
                "Não há confronto possível: todo combo OOP divide carta com todo combo IP."
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
    street: str = "river"
    iso: list[tuple[int, int]] = field(default_factory=list)  # filho de chance: [(carta y, k⁻¹)]


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


KIND_CODES = ("check", "bet", "call", "raise", "fold", "allin", "card")
STREET_CODES = ("flop", "turn", "river")
# arrays que descrevem a árvore (gravados como tree_<nome>.npy no diretório da solução — T101)
TREE_ARRAYS = (
    "node_type",
    "node_player",
    "child_start",
    "child_count",
    "children_arr",
    "inv",
    "board_id",
    "chance_card",
    "chance_factor",
    "node_street",
    "dec_index",
    "dec_node",
    "dec_offset",
    "dec_combo_offset",
    "dec_board_start",
    "dec_boards",
    "subtree_size",
    "iso_start",
    "iso_card",
    "iso_perm",
    "hand_perms0",
    "hand_perms1",
    "strengths0",
    "strengths1",
    "orders0",
    "orders1",
    "hands0",
    "hands1",
    "hand_cards0",
    "hand_cards1",
    "weights0",
    "weights1",
    "edge_kind",
    "edge_amount",
    "edge_frac",
    "edge_id",
    "edge_label",
)


class GameTree:
    """Árvore vetorizada, inteiramente em arrays (pode ser reaberta do disco via mmap)."""

    node_type: np.ndarray
    node_player: np.ndarray
    child_start: np.ndarray
    child_count: np.ndarray
    children_arr: np.ndarray
    inv: np.ndarray
    board_id: np.ndarray
    chance_card: np.ndarray
    chance_factor: np.ndarray
    node_street: np.ndarray
    dec_index: np.ndarray
    dec_node: np.ndarray
    dec_offset: np.ndarray
    dec_combo_offset: np.ndarray
    dec_board_start: np.ndarray
    dec_boards: np.ndarray
    subtree_size: np.ndarray
    iso_start: np.ndarray
    iso_card: np.ndarray
    iso_perm: np.ndarray
    hand_perms0: np.ndarray
    hand_perms1: np.ndarray
    strengths0: np.ndarray
    strengths1: np.ndarray
    orders0: np.ndarray
    orders1: np.ndarray
    hands0: np.ndarray
    hands1: np.ndarray
    hand_cards0: np.ndarray
    hand_cards1: np.ndarray
    weights0: np.ndarray
    weights1: np.ndarray
    edge_kind: np.ndarray
    edge_amount: np.ndarray
    edge_frac: np.ndarray
    edge_id: np.ndarray
    edge_label: np.ndarray

    def __init__(
        self,
        assembler: TreeAssembler,
        players: Players,
        pot: float,
        boards: list[tuple[int, ...]],
        strengths: tuple[np.ndarray, np.ndarray],
        street: Street = Street.RIVER,
        hand_label: Any = None,
        hand_perms: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> None:
        nodes = assembler.nodes
        n = len(nodes)
        a: dict[str, np.ndarray] = {}
        a["node_type"] = np.array([nd.kind for nd in nodes], dtype=np.int64)
        a["node_player"] = np.array([nd.player for nd in nodes], dtype=np.int64)
        a["child_count"] = np.array([len(nd.children) for nd in nodes], dtype=np.int64)
        a["child_start"] = np.concatenate([[0], np.cumsum(a["child_count"])[:-1]]).astype(np.int64)
        a["children_arr"] = np.array([c for nd in nodes for c in nd.children], dtype=np.int64)
        a["inv"] = np.array([nd.inv for nd in nodes], dtype=np.float64).reshape(n, 2)
        a["board_id"] = np.array([nd.board_id for nd in nodes], dtype=np.int64)
        a["chance_card"] = np.array([nd.chance_card for nd in nodes], dtype=np.int64)
        a["chance_factor"] = np.array([nd.chance_factor for nd in nodes], dtype=np.float64)
        a["node_street"] = np.array([STREET_CODES.index(nd.street) for nd in nodes], dtype=np.int8)
        dec_index = -np.ones(n, dtype=np.int64)
        offs: list[int] = []
        coffs: list[int] = []
        dec: list[int] = []
        o = co = 0
        for i, nd in enumerate(nodes):
            if nd.kind == NODE_DECISION:
                dec_index[i] = len(dec)
                dec.append(i)
                offs.append(o)
                coffs.append(co)
                nh = len(players.hands[nd.player])
                o += len(nd.children) * nh
                co += nh
        a["dec_index"] = dec_index
        a["dec_node"] = np.array(dec, dtype=np.int64)
        a["dec_offset"] = np.array([*offs, o], dtype=np.int64)
        a["dec_combo_offset"] = np.array([*coffs, co], dtype=np.int64)
        bstart: list[int] = []
        bflat: list[int] = []
        for i in dec:
            bstart.append(len(bflat))
            bflat += list(nodes[i].boards) or [0]
        a["dec_board_start"] = np.array([*bstart, len(bflat)], dtype=np.int64)
        a["dec_boards"] = np.array(bflat, dtype=np.int64)
        size = np.ones(n, dtype=np.int64)
        for i in range(n - 1, -1, -1):
            for c in nodes[i].children:
                size[i] += size[c]
        a["subtree_size"] = size
        istart: list[int] = []
        icard: list[int] = []
        iperm: list[int] = []
        for nd in nodes:
            istart.append(len(icard))
            for y, kinv in nd.iso:
                icard.append(y)
                iperm.append(kinv)
        a["iso_start"] = np.array([*istart, len(icard)], dtype=np.int64)
        a["iso_card"] = np.array(icard, dtype=np.int64)
        a["iso_perm"] = np.array(iperm, dtype=np.int64)
        if hand_perms is None:
            hand_perms = tuple(  # type: ignore[assignment]
                np.vstack(
                    [np.arange(len(h), dtype=np.int64)] + [np.full(len(h), -1, dtype=np.int64)] * 23
                )
                for h in players.hands
            )
        assert hand_perms is not None
        for p in (0, 1):
            a[f"hand_perms{p}"] = np.ascontiguousarray(hand_perms[p], dtype=np.int64)
            a[f"strengths{p}"] = np.ascontiguousarray(strengths[p], dtype=np.int32)
            a[f"orders{p}"] = np.argsort(strengths[p], axis=1, kind="stable").astype(np.int64)
            a[f"hands{p}"] = np.asarray(players.hands[p], dtype=np.int64)
            a[f"hand_cards{p}"] = np.ascontiguousarray(players.hand_cards[p], dtype=np.int64)
            a[f"weights{p}"] = np.asarray(players.weights[p], dtype=np.float64)
        strings: dict[str, int] = {}

        def sid(text: str) -> int:
            return strings.setdefault(text, len(strings))

        edges = [act for nd in nodes for act in nd.actions]
        a["edge_kind"] = np.array([KIND_CODES.index(e.kind) for e in edges], dtype=np.int8)
        a["edge_amount"] = np.array([e.amount for e in edges], dtype=np.float64)
        a["edge_frac"] = np.array(
            [np.nan if e.pot_fraction is None else e.pot_fraction for e in edges]
        )
        a["edge_id"] = np.array([sid(e.id) for e in edges], dtype=np.int32)
        a["edge_label"] = np.array([sid(e.label) for e in edges], dtype=np.int32)
        meta = {
            "pot": float(pot),
            "street": Street(street).value,
            "boards": [list(b) for b in boards],
            "n_cards": int(players.n_cards),
            "strings": list(strings),
            "effective_stack": 0.0,
            "initial_board": [],
            "group": [0],
        }
        self._load(a, meta)
        self._hand_label = hand_label

    @classmethod
    def from_arrays(cls, arrays: dict[str, np.ndarray], meta: dict[str, Any]) -> GameTree:
        tree = cls.__new__(cls)
        tree._load(arrays, meta)
        tree._hand_label = None
        return tree

    def _load(self, a: dict[str, np.ndarray], meta: dict[str, Any]) -> None:
        self._a = a
        for name in TREE_ARRAYS:
            setattr(self, name, a[name])
        self.players = Players(
            (a["hands0"], a["hands1"]),
            (a["hand_cards0"], a["hand_cards1"]),
            (a["weights0"], a["weights1"]),
            int(meta["n_cards"]),
        )
        self.hand_perms = (a["hand_perms0"], a["hand_perms1"])
        self.strengths = (a["strengths0"], a["strengths1"])
        self.orders = (a["orders0"], a["orders1"])
        self.pot = float(meta["pot"])
        self.street = Street(meta["street"])
        self.boards = [tuple(b) for b in meta["boards"]]
        self._strings: list[str] = list(meta["strings"])
        self.effective_stack = float(meta.get("effective_stack", 0.0))
        self.initial_board: tuple[int, ...] = tuple(meta.get("initial_board", []))
        self.group: list[int] = list(meta.get("group", [0]))
        self.strategy_size = int(a["dec_offset"][-1])
        self.combo_size = int(a["dec_combo_offset"][-1])
        self.root = 0

    def to_arrays(self) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        meta = {
            "pot": self.pot,
            "street": self.street.value,
            "boards": [list(b) for b in self.boards],
            "n_cards": int(self.players.n_cards),
            "strings": self._strings,
            "effective_stack": self.effective_stack,
            "initial_board": list(self.initial_board),
            "group": list(self.group),
        }
        return {name: self._a[name] for name in TREE_ARRAYS}, meta

    # ---- consulta ----
    @property
    def n_nodes(self) -> int:
        return int(self.node_type.shape[0])

    @property
    def n_decision_nodes(self) -> int:
        return int(self.dec_node.shape[0])

    def n_hands(self, player: str | int) -> int:
        p = PLAYERS.index(player) if isinstance(player, str) else player
        return len(self.players.hands[p])

    def decision_shapes(self) -> list[tuple[int, int]]:
        return [(int(self.child_count[i]), int(self.node_player[i])) for i in self.dec_node]

    def street_of(self, node: int) -> str:
        return STREET_CODES[int(self.node_street[node])]

    def iso_members(self, node: int) -> list[tuple[int, int]]:
        lo, hi = int(self.iso_start[node]), int(self.iso_start[node + 1])
        return [(int(self.iso_card[m]), int(self.iso_perm[m])) for m in range(lo, hi)]

    def node_kind(self, node: int) -> str:
        return _KIND[int(self.node_type[node])]

    def player(self, node: int) -> str:
        return PLAYERS[int(self.node_player[node])]

    def player_index(self, node: int) -> int:
        return int(self.node_player[node])

    def _edges(self, node: int) -> range:
        s = int(self.child_start[node])
        return range(s, s + int(self.child_count[node]))

    def actions(self, node: int) -> list[Action]:
        out = []
        for e in self._edges(node):
            frac = float(self.edge_frac[e])
            out.append(
                Action(
                    KIND_CODES[int(self.edge_kind[e])],
                    self._strings[int(self.edge_id[e])],
                    float(self.edge_amount[e]),
                    None if np.isnan(frac) else frac,
                    self._strings[int(self.edge_label[e])],
                )
            )
        return out

    def children(self, node: int) -> list[int]:
        return [int(self.children_arr[e]) for e in self._edges(node)]

    def investments(self, node: int) -> tuple[float, float]:
        return float(self.inv[node, 0]), float(self.inv[node, 1])

    def pot_at(self, node: int) -> float:
        return float(self.pot + self.inv[node, 0] + self.inv[node, 1])

    def child(self, node: int, action_id: str) -> int:
        for e in self._edges(node):
            if self._strings[int(self.edge_id[e])] == action_id:
                return int(self.children_arr[e])
        raise InvalidPathError(f"A ação '{action_id}' não existe neste nó.")

    def node_at(self, path: Sequence[str]) -> int:
        n = self.root
        for step in path:
            if int(self.node_type[n]) in (NODE_FOLD, NODE_SHOWDOWN):
                raise InvalidPathError(f"O caminho continua depois de um nó terminal ('{step}').")
            n = self.child(n, step)
        return n

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
