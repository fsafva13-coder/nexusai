"""Ecosystem: regrowing food, predators that hunt isolated creatures (safety in numbers)."""
from __future__ import annotations

import random
from typing import Dict, Tuple

from ..constants import CONTEST_COST, cheb, clamp
from .base import Environment, GatherResult

PREDATOR_DAMAGE = 14
MAX_FOOD = 14


class EcosystemEnvironment(Environment):
    name = "ecosystem"

    def __init__(self, rng: random.Random, grid: int = 12):
        super().__init__(rng, grid)
        self.food = []
        self.predators = []
        self._fid = 0
        self._pid = 0
        self.eaten = 0
        self.hits = 0
        self.repelled = 0
        self._positions: Dict[str, Tuple[int, int]] = {}
        for _ in range(12):
            self._spawn_food()
        for _ in range(2):
            self._spawn_predator()

    def _spawn_food(self) -> None:
        self._fid += 1
        x, y = self.random_cell()
        self.food.append({"id": f"F{self._fid}", "x": x, "y": y, "value": self.rng.randint(14, 30)})

    def _spawn_predator(self) -> dict:
        self._pid += 1
        x, y = self.random_cell(margin=2)
        predator = {"id": f"P{self._pid}", "x": x, "y": y, "cool": 0}
        self.predators.append(predator)
        return predator

    # --- dynamics -----------------------------------------------------------------
    def update(self, tick, positions):
        self.tick = tick
        self._positions = dict(positions)
        if tick % 3 == 0 and len(self.food) < MAX_FOOD:
            self._spawn_food()
        if tick % 2 == 0:
            for p in self.predators:
                if p["cool"] > 0:
                    p["cool"] -= 1
                    continue
                self._move_predator(p)

    def _isolated(self, aid: str) -> bool:
        x, y = self._positions[aid]
        return not any(
            other != aid and cheb(x, y, ox, oy) <= 1 for other, (ox, oy) in self._positions.items()
        )

    def _move_predator(self, p: dict) -> None:
        prey = [(cheb(p["x"], p["y"], x, y), aid, (x, y))
                for aid, (x, y) in self._positions.items() if self._isolated(aid)]
        prey = [item for item in prey if item[0] <= 6]
        if prey:
            _, _, (tx, ty) = min(prey)
            dx, dy = tx - p["x"], ty - p["y"]
        else:
            dx, dy = self.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])
        if abs(dx) >= abs(dy) and dx != 0:
            p["x"] = clamp(p["x"] + (1 if dx > 0 else -1))
        elif dy != 0:
            p["y"] = clamp(p["y"] + (1 if dy > 0 else -1))

    # --- queries ----------------------------------------------------------------------
    def nodes(self):
        return [{"id": f["id"], "x": f["x"], "y": f["y"], "kind": "food", "value": f["value"], "needs": 1}
                for f in self.food]

    def threats(self):
        return [{"type": "predator", "id": p["id"], "x": p["x"], "y": p["y"]} for p in self.predators]

    def resolve_gathers(self, gatherers):
        out: Dict[str, GatherResult] = {}
        by_tile = {(f["x"], f["y"]): f for f in self.food}
        for tile, ids in self.group_by_tile(gatherers).items():
            food = by_tile.get(tile)
            if food is None:
                for aid in ids:
                    out[aid] = GatherResult(-2, "no food here", False)
                continue
            winner = self.pick_winner(ids)
            for aid in ids:
                if aid == winner:
                    out[aid] = GatherResult(food["value"], f"ate {food['id']}", True)
                else:
                    out[aid] = GatherResult(-CONTEST_COST, "lost the scuffle for food", False)
            self.food.remove(food)
            self.eaten += 1
        return out

    def hazard_damage(self, positions):
        out: Dict[str, Tuple[int, str]] = {}
        for p in self.predators:
            if p["cool"] > 0:
                continue
            for aid, (x, y) in sorted(positions.items()):
                if cheb(p["x"], p["y"], x, y) > 1:
                    continue
                herded = any(o != aid and cheb(x, y, ox, oy) <= 1 for o, (ox, oy) in positions.items())
                if herded:
                    self.repelled += 1
                    p["cool"] = 1
                    break
                out[aid] = (PREDATOR_DAMAGE, f"mauled by {p['id']}")
                self.hits += 1
                p["cool"] = 2
                break
        return out

    def crisis(self):
        p = self._spawn_predator()
        text = f"Predator {p['id']} enters the territory."
        self.emit(text)
        return text

    def render(self):
        return {
            "food": [{"id": f["id"], "x": f["x"], "y": f["y"], "value": f["value"]} for f in self.food],
            "predators": [{"id": p["id"], "x": p["x"], "y": p["y"]} for p in self.predators],
        }

    def score(self):
        return {"eaten": self.eaten, "attacks": self.hits, "repelled": self.repelled}
