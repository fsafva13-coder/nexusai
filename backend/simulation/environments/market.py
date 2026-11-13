"""Market trading: drifting asset prices, trend-dependent deal payoffs, hawk-dove contests."""
from __future__ import annotations

import random
from typing import Dict

from ..constants import CONTEST_COST
from .base import Environment, GatherResult

ASSET_START = {
    "gold": (100.0, 0.6),
    "oil": (80.0, -0.4),
    "tech": (150.0, 0.9),
    "grain": (50.0, 0.0),
}
TARGET_DEALS = 8


def payoff_multiplier(trend: float) -> float:
    """Deal payoff multiplier: strong uptrends pay, strong downtrends are traps."""
    return max(-1.2, min(1.8, 0.35 + 0.6 * trend))


class MarketEnvironment(Environment):
    name = "market"

    def __init__(self, rng: random.Random, grid: int = 12):
        super().__init__(rng, grid)
        self.assets: Dict[str, dict] = {
            name: {"price": price, "trend": trend} for name, (price, trend) in ASSET_START.items()
        }
        self.deals = []
        self._did = 0
        self.executed = 0
        self.pnl = 0
        while len(self.deals) < TARGET_DEALS:
            self._spawn_deal()

    def _spawn_deal(self) -> None:
        self._did += 1
        x, y = self.random_cell()
        self.deals.append({
            "id": f"D{self._did}", "x": x, "y": y,
            "asset": self.rng.choice(list(self.assets)),
            "value": self.rng.randint(15, 35),
        })

    def update(self, tick, positions):
        self.tick = tick
        for asset in self.assets.values():
            asset["trend"] = max(-2.5, min(2.5, asset["trend"] * 0.9 + self.rng.gauss(0, 0.35)))
            drift = 1 + asset["trend"] * 0.01 + self.rng.gauss(0, 0.01)
            asset["price"] = max(10.0, asset["price"] * drift)
        if tick % 18 == 0:
            name = self.rng.choice(list(self.assets))
            shock = self.rng.choice([-1.8, -1.2, 1.2, 1.8])
            self.assets[name]["trend"] = max(-2.5, min(2.5, self.assets[name]["trend"] + shock))
            self.emit(f"Market shock: {name} {'surges' if shock > 0 else 'slumps'}.")
        if len(self.deals) < TARGET_DEALS and self.rng.random() < 0.6:
            self._spawn_deal()

    def _estimate(self, deal: dict) -> int:
        return round(deal["value"] * payoff_multiplier(self.assets[deal["asset"]]["trend"]))

    def nodes(self):
        return [
            {"id": d["id"], "x": d["x"], "y": d["y"], "kind": d["asset"],
             "value": d["value"], "needs": 1, "est": self._estimate(d)}
            for d in self.deals
        ]

    def extras(self):
        return {"assets": {k: {"price": round(v["price"], 1), "trend": round(v["trend"], 2)}
                           for k, v in self.assets.items()}}

    def resolve_gathers(self, gatherers):
        out: Dict[str, GatherResult] = {}
        by_tile = {(d["x"], d["y"]): d for d in self.deals}
        for tile, ids in self.group_by_tile(gatherers).items():
            deal = by_tile.get(tile)
            if deal is None:
                for aid in ids:
                    out[aid] = GatherResult(-2, "no deal here", False)
                continue
            winner = self.pick_winner(ids)
            mult = payoff_multiplier(self.assets[deal["asset"]]["trend"])
            payoff = round(deal["value"] * mult + self.rng.gauss(0, 3))
            for aid in ids:
                if aid == winner:
                    sign = "+" if payoff >= 0 else ""
                    out[aid] = GatherResult(payoff, f"{deal['asset']} deal {sign}{payoff}", payoff > 0)
                else:
                    out[aid] = GatherResult(-CONTEST_COST, "outbid on the deal", False)
            self.deals.remove(deal)
            self.executed += 1
            self.pnl += payoff
        return out

    def crisis(self):
        names = self.rng.sample(list(self.assets), 2)
        for name in names:
            self.assets[name]["trend"] = -2.5
            self.assets[name]["price"] = max(10.0, self.assets[name]["price"] * 0.8)
        text = f"Crash: {names[0]} and {names[1]} plunge."
        self.emit(text)
        return text

    def render(self):
        return {
            "assets": self.extras()["assets"],
            "deals": [
                {"id": d["id"], "x": d["x"], "y": d["y"], "asset": d["asset"], "est": self._estimate(d)}
                for d in self.deals
            ],
        }

    def score(self):
        index = sum(a["price"] for a in self.assets.values()) / len(self.assets)
        return {"deals": self.executed, "pnl": self.pnl, "index": round(index, 1)}
