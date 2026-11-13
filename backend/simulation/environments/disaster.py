"""Disaster response: spreading fire, survivors, and a two-rescuer coordination game."""
from __future__ import annotations

import random
from typing import Dict, List, Tuple

from ..constants import CONTEST_COST, cheb
from .base import Environment, GatherResult

SOLO_VALUE = 34
TEAM_VALUE = 40        # per rescuer when a heavy survivor is lifted together
FIRE_DAMAGE = 5
BURN_LIMIT = 4         # ticks a survivor can stand in fire before being lost
MAX_FIRE_RADIUS = 2
MAX_FIRES = 3


class DisasterEnvironment(Environment):
    name = "disaster"

    def __init__(self, rng: random.Random, grid: int = 12):
        super().__init__(rng, grid)
        self.fires: List[dict] = [{"id": "F1", "x": grid // 2, "y": grid // 2, "radius": 1}]
        self.survivors: List[dict] = []
        self._sid = 0
        self._fid = 1
        self.rescued = 0
        self.lost = 0
        for _ in range(9):
            self._spawn_survivor()

    # --- internals ---------------------------------------------------------------
    def _in_fire(self, x: int, y: int) -> bool:
        return any(cheb(x, y, f["x"], f["y"]) <= f["radius"] for f in self.fires)

    def _waiting(self) -> List[dict]:
        return [s for s in self.survivors if s["status"] == "waiting"]

    def _spawn_survivor(self) -> None:
        for _ in range(30):
            x, y = self.random_cell()
            if not self._in_fire(x, y) and not any(
                s["x"] == x and s["y"] == y and s["status"] == "waiting" for s in self.survivors
            ):
                break
        needs = 2 if self.rng.random() < 0.3 else 1
        self._sid += 1
        self.survivors.append({
            "id": f"S{self._sid}", "x": x, "y": y, "needs": needs,
            "value": SOLO_VALUE if needs == 1 else TEAM_VALUE,
            "burn": 0, "status": "waiting", "gone_at": None,
        })

    # --- dynamics -------------------------------------------------------------------
    def update(self, tick, positions):
        self.tick = tick
        if tick % 14 == 0:
            for f in self.fires:
                f["radius"] = min(MAX_FIRE_RADIUS, f["radius"] + 1)
            if len(self.fires) < MAX_FIRES and self.rng.random() < 0.3:
                self._add_fire(1)
                self.emit("A new fire has broken out.")

        for s in self._waiting():
            if self._in_fire(s["x"], s["y"]):
                s["burn"] += 1
                if s["burn"] >= BURN_LIMIT:
                    s["status"], s["gone_at"] = "lost", tick
                    self.lost += 1
                    self.emit(f"Survivor {s['id']} was lost to the fire.")

        if tick % 4 == 0 and len(self._waiting()) < 8:
            self._spawn_survivor()
        # forget resolved survivors after a short display window
        self.survivors = [
            s for s in self.survivors
            if s["status"] == "waiting" or (s["gone_at"] is not None and tick - s["gone_at"] <= 3)
        ]

    def _add_fire(self, radius: int) -> dict:
        self._fid += 1
        x, y = self.random_cell()
        fire = {"id": f"F{self._fid}", "x": x, "y": y, "radius": radius}
        self.fires.append(fire)
        return fire

    # --- queries ----------------------------------------------------------------------
    def nodes(self):
        return [
            {"id": s["id"], "x": s["x"], "y": s["y"], "kind": "survivor",
             "value": s["value"], "needs": s["needs"]}
            for s in self._waiting()
        ]

    def threats(self):
        return [{"type": "fire", "id": f["id"], "x": f["x"], "y": f["y"], "radius": f["radius"]}
                for f in self.fires]

    def resolve_gathers(self, gatherers):
        out: Dict[str, GatherResult] = {}
        waiting = {(s["x"], s["y"]): s for s in self._waiting()}
        for tile, ids in self.group_by_tile(gatherers).items():
            survivor = waiting.get(tile)
            if survivor is None:
                for aid in ids:
                    out[aid] = GatherResult(-2, "nothing to rescue here", False)
                continue
            needs = survivor["needs"]
            if len(ids) >= needs:
                chosen = self.rng.sample(sorted(ids), needs)
                note = " (teamwork)" if needs == 2 else ""
                for aid in ids:
                    if aid in chosen:
                        out[aid] = GatherResult(survivor["value"], f"rescued {survivor['id']}{note}", True)
                    else:
                        out[aid] = GatherResult(-CONTEST_COST, f"too late for {survivor['id']}", False)
                survivor["status"], survivor["gone_at"] = "rescued", self.tick
                self.rescued += 1
            else:
                out[ids[0]] = GatherResult(-1, f"{survivor['id']} needs a second rescuer", False, finished=False)
        return out

    def hazard_damage(self, positions):
        out: Dict[str, Tuple[int, str]] = {}
        for aid, (x, y) in positions.items():
            if self._in_fire(x, y):
                out[aid] = (FIRE_DAMAGE, "burned by fire")
        return out

    def crisis(self):
        fire = self._add_fire(MAX_FIRE_RADIUS)
        text = f"Fire erupts near ({fire['x']},{fire['y']})."
        self.emit(text)
        return text

    def render(self):
        return {
            "fires": [dict(f) for f in self.fires],
            "survivors": [
                {"id": s["id"], "x": s["x"], "y": s["y"], "needs": s["needs"], "status": s["status"]}
                for s in self.survivors
            ],
        }

    def score(self):
        return {"rescued": self.rescued, "lost": self.lost, "waiting": len(self._waiting())}
