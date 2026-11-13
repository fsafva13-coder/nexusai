"""Rule-based policy + low-level controller.

Two layers cooperate (a "dual-process" design):

* ``choose_intent``   - slow deliberation. The LLM planner replaces this when
  it is available; otherwise these personality rules pick the intent.
* ``next_action``     - fast controller. Converts the current intent into one
  primitive action per tick and applies reflexes (flee fire, huddle when a
  predator is near) that never wait for the LLM.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from .agent import Agent, Intent
from .constants import (
    AGENT_INTENTS, GRID_SIZE, INTENT_TTL, INTERACT_RANGE, STEAL_RANGE, VIEW_RADIUS, cheb,
)

DIRS = {"move_north": (0, -1), "move_south": (0, 1), "move_east": (1, 0), "move_west": (-1, 0)}
MOVE_BY_DELTA = {v: k for k, v in DIRS.items()}

MESSAGES = {
    "seek": {
        "cooperative": ["Heading to {t}; join me if you can.", "I'll take {t}, shout if you need help."],
        "competitive": ["{t} is mine.", "Moving on {t}. Stay clear."],
        "neutral": ["Going for {t}.", "{t} looks worth it."],
    },
    "help": {
        "cooperative": ["{t}, take this, you need it more.", "Hold on {t}, sharing with you."],
        "competitive": ["{t}, consider this a loan.", "A little investment in you, {t}."],
        "neutral": ["{t}, you helped before; returning the favour.", "Here, {t}."],
    },
    "trade": {
        "cooperative": ["{t}, trade with me? We both come out ahead.", "Fair swap, {t}?"],
        "competitive": ["{t}, a trade, if you can keep up.", "Deal, {t}?"],
        "neutral": ["{t}, mutual trade?", "I'll trade if you will, {t}."],
    },
    "steal": {
        "cooperative": ["{t}, I'm sorry, I'm desperate.", "Forgive me, {t}."],
        "competitive": ["Hand it over, {t}.", "Nothing personal, {t}."],
        "neutral": ["That's for last time, {t}.", "We're even now, {t}."],
    },
    "follow": {
        "cooperative": ["Staying close to {t}; safer together.", "Sticking with you, {t}."],
        "competitive": ["Tailing {t}.", "I'll walk with {t} for now."],
        "neutral": ["Following {t} for safety.", "Moving with {t}."],
    },
    "explore": {
        "cooperative": ["Scouting for the group.", "Looking around for anyone in need."],
        "competitive": ["Hunting for opportunities.", "Nothing here. Moving."],
        "neutral": ["Exploring.", "Checking the area."],
    },
    "rest": {
        "cooperative": ["Catching my breath.", "Holding position."],
        "competitive": ["Waiting for my moment.", "Watching."],
        "neutral": ["Holding.", "Standing by."],
    },
}


def make_intent(kind: str, rng: random.Random, target: Optional[str] = None,
                pos=None, reason: str = "", personality: str = "neutral") -> Intent:
    pool = MESSAGES.get(kind, {}).get(personality) or [""]
    text = rng.choice(pool).format(t=target or "")
    return Intent(kind=kind, target=target, ttl=INTENT_TTL[kind], source="rule",
                  reason=reason, message=text, pos=pos)


# ---------------------------------------------------------------------------------
# movement helpers
# ---------------------------------------------------------------------------------
def step_toward(x: int, y: int, tx: int, ty: int, rng: random.Random) -> str:
    dx, dy = tx - x, ty - y
    if dx == 0 and dy == 0:
        return "wait"
    if abs(dx) > abs(dy) or (abs(dx) == abs(dy) and dx != 0 and rng.random() < 0.5):
        return "move_east" if dx > 0 else "move_west"
    return "move_south" if dy > 0 else "move_north"


def step_away(x: int, y: int, tx: int, ty: int, rng: random.Random) -> str:
    options = []
    for name, (dx, dy) in DIRS.items():
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
            options.append(((nx - tx) ** 2 + (ny - ty) ** 2 + rng.random() * 0.1, name))
    return max(options)[1] if options else "wait"


# ---------------------------------------------------------------------------------
# deliberation
# ---------------------------------------------------------------------------------
def best_node(agent: Agent, obs: dict) -> Optional[dict]:
    others_seek = {a["target"] for a in obs["agents"] if a["intent"] == "seek" and a["target"]}
    best, best_score = None, 0.0
    for n in obs["nodes"]:
        score = n.get("est", n["value"]) / (1 + n["dist"])
        if n.get("needs", 1) > 1:
            if n["id"] in others_seek:
                score *= 1.6                                   # a partner is already there
            else:
                score *= 0.7 if agent.personality == "cooperative" else 0.35
        elif n["id"] in others_seek and agent.personality == "cooperative":
            score *= 0.8                                       # avoid contesting
        if n.get("danger"):
            score *= 0.8 if agent.personality == "cooperative" else 0.3
        if score > best_score:
            best, best_score = n, score
    return best


def choose_intent(agent: Agent, obs: dict, rng: random.Random, scenario: str) -> Intent:
    me = obs["me"]
    res = me["resources"]
    P = agent.personality
    near = obs["agents"]
    desperate = res < 35

    def mk(kind, target=None, pos=None, reason=""):
        return make_intent(kind, rng, target, pos, reason, P)

    # 1. answer trade offers (this is how mutual trade emerges)
    offers = [a for a in near if a["intent"] == "trade" and a["target"] == me["id"]]
    if offers:
        o = max(offers, key=lambda a: a["trust"])
        if P == "cooperative":
            accept = 0.95
        elif P == "neutral":
            accept = 0.8 if o["trust"] > -0.3 else 0.1
        else:
            accept = 0.4 if o["trust"] > -0.3 else 0.0
        if rng.random() < accept:
            return mk("trade", o["id"], reason="accepting a trade offer")

    # 2. social behaviour by personality
    if P == "cooperative":
        needy = [a for a in near if a["resources"] < 40 and a["dist"] <= 3]
        if needy and res > 55:
            t = min(needy, key=lambda a: a["resources"])
            return mk("help", t["id"], reason="neighbour is running low")
        partners = [a for a in near if a["trust"] >= -0.2 and a["dist"] <= 3]
        if partners and rng.random() < 0.35:
            return mk("trade", min(partners, key=lambda a: a["dist"])["id"], reason="mutual gain")
    elif P == "neutral":
        allies = [a for a in near if a["trust"] >= 0.25 and a["dist"] <= 3]
        needy = [a for a in allies if a["resources"] < 45]
        if needy and res > 60:
            return mk("help", min(needy, key=lambda a: a["resources"])["id"], reason="returning a favour")
        if allies and rng.random() < 0.3:
            return mk("trade", max(allies, key=lambda a: a["trust"])["id"], reason="trusted partner")
        enemies = [a for a in near if a["trust"] <= -0.4 and a["dist"] <= 2 and a["resources"] > 25]
        if enemies and rng.random() < 0.6:
            return mk("steal", max(enemies, key=lambda a: a["resources"])["id"], reason="retaliation")
    else:  # competitive
        prey = [a for a in near if a["dist"] <= 2 and a["resources"] > max(40, res * 0.9)]
        if prey and (desperate or rng.random() < 0.45):
            return mk("steal", max(prey, key=lambda a: a["resources"])["id"], reason="easy gain")
        partners = [a for a in near if a["trust"] > 0.2 and a["dist"] <= 3]
        if partners and rng.random() < 0.2:
            return mk("trade", partners[0]["id"], reason="profitable partner")

    # 3. resources
    node = best_node(agent, obs)
    if node:
        return mk("seek", node["id"], pos=(node["x"], node["y"]), reason="best payoff nearby")

    # 4. no resource in view
    if scenario == "ecosystem" and near and P != "competitive":
        return mk("follow", min(near, key=lambda a: a["dist"])["id"], reason="safety in numbers")
    return mk("explore", reason="nothing in view")


def intent_valid(agent: Agent, it: Intent, obs: dict) -> bool:
    if it.kind in ("explore", "rest"):
        return True
    me = obs["me"]
    if it.kind == "seek":
        if it.pos is None:
            return False
        if any(n["id"] == it.target for n in obs["nodes"]):
            return True
        return cheb(me["x"], me["y"], it.pos[0], it.pos[1]) > VIEW_RADIUS   # out of sight: assume it is still there
    if it.kind in AGENT_INTENTS:
        return any(a["id"] == it.target for a in obs["agents"])
    return False


# ---------------------------------------------------------------------------------
# fast controller
# ---------------------------------------------------------------------------------
def _reflex(agent: Agent, obs: dict, rng: random.Random) -> Optional[str]:
    me = obs["me"]
    x, y = me["x"], me["y"]
    fires = [t for t in obs["threats"] if t["type"] == "fire" and t["dist"] <= t["radius"]]
    if fires and (me["resources"] < 50 or agent.personality != "cooperative"):
        f = min(fires, key=lambda t: t["dist"])
        return step_away(x, y, f["x"], f["y"], rng)
    preds = [t for t in obs["threats"] if t["type"] == "predator" and t["dist"] <= 2]
    if preds and not any(a["dist"] <= 1 for a in obs["agents"]):
        if obs["agents"] and agent.personality != "competitive":
            buddy = min(obs["agents"], key=lambda a: a["dist"])
            return step_toward(x, y, buddy["x"], buddy["y"], rng)        # huddle
        p = min(preds, key=lambda t: t["dist"])
        return step_away(x, y, p["x"], p["y"], rng)
    return None


def next_action(agent: Agent, obs: dict, rng: random.Random) -> Dict[str, Optional[str]]:
    me = obs["me"]
    x, y = me["x"], me["y"]
    reflex = _reflex(agent, obs, rng)
    if reflex:
        return {"action": reflex, "target": None, "source": "reflex"}

    it = agent.intent
    if it is None:
        return {"action": "wait", "target": None, "source": "rule"}
    src = it.source

    if it.kind == "seek":
        tx, ty = it.pos
        if (x, y) == (tx, ty):
            return {"action": "gather", "target": it.target, "source": src}
        return {"action": step_toward(x, y, tx, ty, rng), "target": it.target, "source": src}

    if it.kind in AGENT_INTENTS:
        other = next(a for a in obs["agents"] if a["id"] == it.target)
        if it.kind == "follow":
            if other["dist"] > 1:
                return {"action": step_toward(x, y, other["x"], other["y"], rng), "target": it.target, "source": src}
            return {"action": "wait", "target": it.target, "source": src}
        reach = STEAL_RANGE if it.kind == "steal" else INTERACT_RANGE
        if other["dist"] <= reach:
            return {"action": it.kind, "target": it.target, "source": src}
        return {"action": step_toward(x, y, other["x"], other["y"], rng), "target": it.target, "source": src}

    if it.kind == "explore":
        hx, hy = agent.heading
        nx, ny = x + hx, y + hy
        if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE) or rng.random() < 0.2:
            options: List = [d for d in DIRS.values()
                             if 0 <= x + d[0] < GRID_SIZE and 0 <= y + d[1] < GRID_SIZE]
            agent.heading = rng.choice(options)
            hx, hy = agent.heading
        return {"action": MOVE_BY_DELTA[(hx, hy)], "target": None, "source": src}

    return {"action": "wait", "target": None, "source": src}
