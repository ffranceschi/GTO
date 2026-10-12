from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ready", "warming_up"]
    engine_version: str
