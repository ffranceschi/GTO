from __future__ import annotations

import json
from pathlib import Path

from gto_engine.cards import parse_card
from gto_engine.game.config import TreeConfig
from gto_engine.game.tree import Spot
from gto_engine.ranges import parse_range

FIXTURES = Path(__file__).parent / "fixtures"


def load_spot(name: str) -> tuple[Spot, TreeConfig]:
    """Carrega uma fixture no formato SpotWithTree do contrato (ranges em notação)."""
    d = json.loads((FIXTURES / name).read_text())
    s = d["spot"]
    spot = Spot(
        parse_range(s["oop_range"]["notation"]),
        parse_range(s["ip_range"]["notation"]),
        tuple(parse_card(c) for c in s["board"]),
        float(s["pot"]),
        float(s["effective_stack"]),
    )
    return spot, TreeConfig.from_dict(d["tree"])
