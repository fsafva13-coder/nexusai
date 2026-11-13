"""Headless runs for research-style comparisons (no network, deterministic per seed)."""
from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional

from .constants import PERSONALITIES, PRESETS
from .engine import SimulationEngine


async def run_once(scenario: str, agents: int = 6, ticks: int = 80, seed: int = 0,
                   preset: Optional[str] = "balanced", personalities: Optional[List[str]] = None) -> dict:
    engine = SimulationEngine(scenario, agents, seed=seed, preset=preset,
                              personalities=personalities, max_ticks=ticks)
    while not engine.finished:
        await engine.step()
    return engine.summary()


def aggregate(rows: List[dict]) -> dict:
    keys = ["survivors", "welfare", "gini", "cooperation_index", "helps", "trades", "steals", "coalitions_formed"]
    out: Dict[str, object] = {k: round(mean(r[k] for r in rows), 2) for k in keys}
    out["by_personality"] = {}
    for p in PERSONALITIES:
        vals = [r["by_personality"][p] for r in rows if p in r["by_personality"]]
        if vals:
            out["by_personality"][p] = round(mean(vals), 1)
    score_keys = rows[0]["score"].keys() if rows else []
    out["score"] = {k: round(mean(r["score"][k] for r in rows), 1) for k in score_keys}
    out["total_agents"] = rows[0]["total_agents"] if rows else 0
    out["runs"] = len(rows)
    return out


async def run_batch(scenario: str, agents: int = 6, ticks: int = 80, seeds: int = 5,
                    preset: Optional[str] = "balanced") -> dict:
    rows = [await run_once(scenario, agents, ticks, seed, preset) for seed in range(seeds)]
    return aggregate(rows)


async def compare_presets(scenario: str, agents: int = 6, ticks: int = 80, seeds: int = 8) -> Dict[str, dict]:
    return {name: await run_batch(scenario, agents, ticks, seeds, name) for name in PRESETS}
