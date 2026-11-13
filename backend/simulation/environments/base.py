"""Environment interface shared by all three scenarios."""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..constants import GRID_SIZE


@dataclass
class GatherResult:
    delta: int
    label: str
    success: bool
    finished: bool = True      # False => the agent's seek intent should continue


class Environment:
    name = "base"

    def __init__(self, rng: random.Random, grid: int = GRID_SIZE):
        self.rng = rng
        self.grid = grid
        self.tick = 0
        self._events: List[str] = []

    # --- world dynamics ------------------------------------------------------
    def update(self, tick: int, positions: Dict[str, Tuple[int, int]]) -> None:
        self.tick = tick

    def nodes(self) -> List[dict]:
        """Gatherable things: dicts with id, x, y, kind, value, needs (and optional est)."""
        return []

    def threats(self) -> List[dict]:
        return []

    def extras(self) -> Optional[dict]:
        return None

    def resolve_gathers(self, gatherers: Dict[str, Tuple[int, int]]) -> Dict[str, GatherResult]:
        return {}

    def hazard_damage(self, positions: Dict[str, Tuple[int, int]]) -> Dict[str, Tuple[int, str]]:
        return {}

    def crisis(self) -> str:
        return "Nothing happens."

    def render(self) -> dict:
        return {}

    def score(self) -> dict:
        return {}

    # --- helpers ----------------------------------------------------------------
    def emit(self, text: str) -> None:
        self._events.append(text)

    def drain_events(self) -> List[str]:
        out, self._events = self._events, []
        return out

    def random_cell(self, margin: int = 0) -> Tuple[int, int]:
        lo, hi = margin, self.grid - 1 - margin
        return self.rng.randint(lo, hi), self.rng.randint(lo, hi)

    @staticmethod
    def group_by_tile(gatherers: Dict[str, Tuple[int, int]]) -> Dict[Tuple[int, int], List[str]]:
        tiles: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        for agent_id, pos in sorted(gatherers.items()):
            tiles[pos].append(agent_id)
        return tiles

    def pick_winner(self, ids: List[str]) -> str:
        """Hawk-dove style tie-break for contested nodes: uniform random winner."""
        return self.rng.choice(sorted(ids))
