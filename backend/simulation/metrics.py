"""Metrics used to compare strategies: inequality, cooperation, welfare."""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List

from .constants import PERSONALITIES


def gini(values: Iterable[float]) -> float:
    """Gini coefficient in [0, 1]; 0 = perfect equality."""
    xs = sorted(max(0.0, float(v)) for v in values)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(xs))
    return max(0.0, min(1.0, (2 * weighted) / (n * total) - (n + 1) / n))


def cooperation_index(counters: Counter) -> float:
    """Share of social interactions that were cooperative (help + mutual trade)."""
    coop = counters["helps"] + counters["trades"]
    total = coop + counters["steals"]
    return coop / total if total else 0.0


def by_personality(agents: List) -> Dict[str, float]:
    """Average final resources per strategy, counting the dead as zero."""
    out: Dict[str, float] = {}
    for p in PERSONALITIES:
        group = [a for a in agents if a.personality == p]
        if group:
            out[p] = round(sum(a.resources for a in group) / len(group), 1)
    return out


def compute(agents: List, counters: Counter) -> Dict[str, object]:
    alive = [a for a in agents if a.alive]
    welfare = sum(a.resources for a in alive)
    return {
        "alive": len(alive),
        "total": len(agents),
        "welfare": welfare,
        "avg_resources": round(welfare / len(alive), 1) if alive else 0.0,
        "gini": round(gini(a.resources for a in alive), 3),
        "cooperation_index": round(cooperation_index(counters), 3),
        "helps": counters["helps"],
        "trades": counters["trades"],
        "steals": counters["steals"],
        "gathers": counters["gathers"],
        "by_personality": by_personality(agents),
    }
