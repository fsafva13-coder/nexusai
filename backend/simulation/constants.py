"""Shared constants and small helpers for the NexusAI simulation."""
from __future__ import annotations

from typing import Iterable, List, Optional

# --- world --------------------------------------------------------------
GRID_SIZE = 12
MAX_AGENTS = 8
START_RESOURCES = 100
RESOURCE_CAP = 150
METABOLISM = 2            # resources burned every tick
VIEW_RADIUS = 3           # Chebyshev radius an agent can perceive
INTERACT_RANGE = 2        # help / trade range
STEAL_RANGE = 1

# --- social mechanics (the "game" the agents play) ------------------------
HELP_AMOUNT = 12          # altruistic transfer (zero-sum, costs the giver)
HELP_MIN_KEEP = 20        # a giver never drops below this by helping
TRADE_BONUS = 6           # each side gains this ONLY if both trade with each other
STEAL_AMOUNT = 12
STEAL_LOSS = 0.2          # share of stolen goods destroyed in the scuffle
CONTEST_COST = 3          # price the loser of a contested node pays (hawk-dove)

PERSONALITIES = ("cooperative", "competitive", "neutral")
PERSONA_TEXT = {
    "cooperative": "Prioritises group survival: shares freely, trades readily, sticks with others.",
    "competitive": "Maximises its own resources: exploits weaker neighbours when it pays, trades rarely.",
    "neutral": "Pragmatic tit-for-tat: reciprocates help and trade, retaliates against thieves.",
}

# Intents are what the (slow) planner chooses; a (fast) controller executes them.
INTENTS = ("seek", "help", "trade", "steal", "follow", "explore", "rest")
AGENT_INTENTS = ("help", "trade", "steal", "follow")
INTENT_TTL = {"seek": 8, "help": 3, "trade": 3, "steal": 2, "follow": 4, "explore": 4, "rest": 2}

SCENARIOS = ("disaster", "market", "ecosystem")

SCENARIO_INFO = {
    "disaster": {
        "label": "Disaster Response",
        "description": (
            "Fire spreads across a city block. Rescue survivors before they burn. "
            "Heavy survivors need TWO rescuers at the same moment (a coordination game)."
        ),
        "gather": "rescue",
        "crisis": "Ignite new fire",
    },
    "market": {
        "label": "Market Trading",
        "description": (
            "Four assets drift and shock. Deals pay off according to the asset's trend, "
            "so crashing assets are traps. Mutual trades create value; contested deals are hawk-dove."
        ),
        "gather": "execute deal",
        "crisis": "Trigger market crash",
    },
    "ecosystem": {
        "label": "Ecosystem",
        "description": (
            "Forage for regrowing food while predators hunt isolated creatures. "
            "Staying in a group repels predators, so herding is a survival strategy."
        ),
        "gather": "forage",
        "crisis": "Release a predator",
    },
}

START_POSITIONS = [(1, 1), (10, 1), (1, 10), (10, 10), (5, 1), (5, 10), (1, 5), (10, 5)]


def _cycle(n: int, pattern: Iterable[str]) -> List[str]:
    pattern = list(pattern)
    return [pattern[i % len(pattern)] for i in range(n)]


PRESETS = {
    "balanced": {
        "label": "Balanced mix",
        "build": lambda n: _cycle(n, ["cooperative", "competitive", "neutral"]),
    },
    "all_cooperative": {
        "label": "All cooperative",
        "build": lambda n: ["cooperative"] * n,
    },
    "all_competitive": {
        "label": "All competitive",
        "build": lambda n: ["competitive"] * n,
    },
    "wolf_among_sheep": {
        "label": "One wolf among cooperators",
        "build": lambda n: ["competitive"] + ["cooperative"] * (n - 1),
    },
    "tit_for_tat_vs_wolves": {
        "label": "Tit-for-tat vs competitors",
        "build": lambda n: _cycle(n, ["neutral", "competitive"]),
    },
}


def build_personalities(
    n: int, preset: Optional[str] = None, explicit: Optional[List[str]] = None
) -> List[str]:
    """Resolve the list of personalities for *n* agents."""
    if explicit:
        cleaned = [p if p in PERSONALITIES else "neutral" for p in explicit]
        return [cleaned[i % len(cleaned)] for i in range(n)]
    entry = PRESETS.get(preset or "balanced") or PRESETS["balanced"]
    return entry["build"](n)


def cheb(ax: int, ay: int, bx: int, by: int) -> int:
    """Chebyshev distance (grid distance where diagonals cost 1)."""
    return max(abs(ax - bx), abs(ay - by))


def clamp(v: int, lo: int = 0, hi: int = GRID_SIZE - 1) -> int:
    return max(lo, min(hi, v))
