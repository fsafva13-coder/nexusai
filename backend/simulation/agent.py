"""Agent state: position, resources, trust ledger, current intent."""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from .constants import PERSONALITIES, RESOURCE_CAP, START_RESOURCES


@dataclass
class Intent:
    """A short-lived goal chosen by the planner (LLM) or the rule policy."""

    kind: str
    target: Optional[str] = None
    ttl: int = 4
    source: str = "rule"            # "llm" | "rule"
    reason: str = ""
    message: str = ""
    pos: Optional[Tuple[int, int]] = None   # remembered position of a seek target


STAT_KEYS = (
    "gathered", "helps_given", "helps_received",
    "trades", "steals_done", "steals_suffered",
)


class Agent:
    def __init__(self, agent_id: str, personality: str, x: int, y: int, rng: random.Random):
        if personality not in PERSONALITIES:
            personality = "neutral"
        self.id = agent_id
        self.personality = personality
        self.x = x
        self.y = y
        self.resources = START_RESOURCES
        self.alive = True
        self.intent: Optional[Intent] = None
        self.trust: Dict[str, float] = {}
        self.memory: Deque[str] = deque(maxlen=6)
        self.stats: Dict[str, int] = {k: 0 for k in STAT_KEYS}
        self.heading = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.last: Dict[str, object] = {}

    # --- trust ledger ----------------------------------------------------
    def adjust_trust(self, other_id: str, delta: float) -> None:
        value = self.trust.get(other_id, 0.0) + delta
        self.trust[other_id] = max(-1.0, min(1.0, value))

    def decay_trust(self, rate: float = 0.02) -> None:
        for key in list(self.trust):
            self.trust[key] *= 1.0 - rate
            if abs(self.trust[key]) < 0.01:
                del self.trust[key]

    def remember(self, text: str) -> None:
        self.memory.append(text)

    def clamp_resources(self) -> None:
        self.resources = min(RESOURCE_CAP, self.resources)

    # --- serialisation -----------------------------------------------------
    def top_trust(self, k: int = 4) -> Dict[str, float]:
        items = sorted(self.trust.items(), key=lambda kv: -abs(kv[1]))[:k]
        return {key: round(val, 2) for key, val in items}

    def public(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            "id": self.id,
            "personality": self.personality,
            "x": self.x,
            "y": self.y,
            "resources": self.resources,
            "alive": self.alive,
            "intent": self.intent.kind if self.intent else None,
            "intent_target": self.intent.target if self.intent else None,
            "intent_source": self.intent.source if self.intent else None,
            "trust": self.top_trust(),
            "stats": dict(self.stats),
            "memory": list(self.memory),
        }
        data.update(self.last)
        return data


def init_dict(agent: Agent) -> List[object]:  # pragma: no cover - tiny helper
    return [agent.id, agent.personality, agent.x, agent.y]
