"""Tick-based simulation engine.

One tick:
  1. world dynamics (fire spreads, prices move, predators hunt)
  2. every agent observes its local surroundings (radius 3) and hears nearby messages
  3. intents are (re)assigned: LLM planner every N ticks, rule policy otherwise
  4. the fast controller turns each intent into one primitive action (with reflexes)
  5. actions resolve in phases: move -> mutual trade -> help -> steal -> gather -> hazards -> metabolism
     (randomised order inside a phase so no agent is structurally favoured)
  6. trust, coalitions and metrics update; a JSON-ready snapshot is returned
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Optional

from . import metrics as metrics_mod
from .agent import Agent
from .brain import Brain
from .coalition_detector import CoalitionTracker
from .constants import (
    GRID_SIZE, HELP_AMOUNT, HELP_MIN_KEEP, INTERACT_RANGE, MAX_AGENTS, METABOLISM, SCENARIOS,
    SCENARIO_INFO, START_POSITIONS, STEAL_AMOUNT, STEAL_LOSS, STEAL_RANGE, TRADE_BONUS,
    VIEW_RADIUS, build_personalities, cheb, clamp,
)
from .environments import ENVIRONMENTS
from .policy import DIRS, choose_intent, intent_valid, next_action

INJECTIONS = {
    "drain": "Resource drain: every agent loses 20.",
    "boost": "Supply drop: every agent gains 30.",
    "crisis": None,   # scenario specific, text comes from the environment
}


def _event(tick: int, kind: str, text: str, agents: Optional[List[str]] = None) -> dict:
    return {"tick": tick, "type": kind, "text": text, "agents": agents or []}


class SimulationEngine:
    def __init__(
        self,
        scenario: str = "disaster",
        num_agents: int = 6,
        seed: Optional[int] = None,
        personalities: Optional[List[str]] = None,
        preset: Optional[str] = None,
        brain: Optional[Brain] = None,
        max_ticks: int = 100,
    ):
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario '{scenario}'")
        self.scenario = scenario
        self.seed = seed if seed is not None else random.randrange(1_000_000)
        self.rng = random.Random(self.seed)
        self.env = ENVIRONMENTS[scenario](random.Random(self.seed + 1))
        n = max(2, min(MAX_AGENTS, int(num_agents)))
        kinds = build_personalities(n, preset, personalities)
        self.agents: List[Agent] = [
            Agent(f"A{i + 1}", kinds[i], *START_POSITIONS[i], rng=self.rng) for i in range(n)
        ]
        self.brain = brain or Brain(None)
        self.tracker = CoalitionTracker()
        self.max_ticks = max_ticks
        self.tick = 0
        self.finished = False
        self.end_reason: Optional[str] = None
        self.counters: Counter = Counter()
        self._said_prev: List[dict] = []
        self._pending: List[dict] = []
        self._force_round = False
        self.history: List[dict] = []   # compact per-tick series for the final summary

    # --- public helpers -------------------------------------------------------------------
    def init_payload(self) -> dict:
        return {
            "type": "init",
            "scenario": self.scenario,
            "scenario_label": SCENARIO_INFO[self.scenario]["label"],
            "seed": self.seed,
            "grid_size": GRID_SIZE,
            "max_ticks": self.max_ticks,
            "agents": [{"id": a.id, "personality": a.personality, "x": a.x, "y": a.y} for a in self.agents],
            "brain": self.brain.describe(),
        }

    def inject(self, kind: str) -> Optional[str]:
        """Apply a user-triggered shock. Agents re-plan on the next tick."""
        alive = [a for a in self.agents if a.alive]
        if kind == "drain":
            for a in alive:
                a.resources = max(1, a.resources - 20)
            text = INJECTIONS["drain"]
        elif kind == "boost":
            for a in alive:
                a.resources += 30
                a.clamp_resources()
            text = INJECTIONS["boost"]
        elif kind == "crisis":
            text = self.env.crisis()
            self.env.drain_events()   # avoid duplicating the text below
        else:
            return None
        self._pending.append(_event(self.tick, "inject", f"You injected: {text}"))
        self._force_round = True
        return text

    # --- observation ----------------------------------------------------------------------------
    def _observe(self, a: Agent, nodes_all: List[dict], threats_all: List[dict], extras) -> dict:
        r = VIEW_RADIUS
        fires = [t for t in threats_all if t["type"] == "fire"]
        nodes = []
        for n in nodes_all:
            d = cheb(a.x, a.y, n["x"], n["y"])
            if d <= r:
                item = dict(n)
                item["dist"] = d
                item["danger"] = any(cheb(n["x"], n["y"], f["x"], f["y"]) <= f["radius"] for f in fires)
                nodes.append(item)
        nodes.sort(key=lambda n: (n["dist"], n["id"]))

        agents = []
        for o in self.agents:
            if o.id == a.id or not o.alive:
                continue
            d = cheb(a.x, a.y, o.x, o.y)
            if d <= r:
                agents.append({
                    "id": o.id, "x": o.x, "y": o.y, "resources": o.resources,
                    "personality": o.personality, "dist": d,
                    "trust": round(a.trust.get(o.id, 0.0), 2),
                    "intent": o.intent.kind if o.intent else None,
                    "target": o.intent.target if o.intent else None,
                })
        agents.sort(key=lambda x: (x["dist"], x["id"]))

        threats = []
        for t in threats_all:
            d = cheb(a.x, a.y, t["x"], t["y"])
            reach = t.get("radius", 0) + r if t["type"] == "fire" else r + 1
            if d <= reach:
                item = dict(t)
                item["dist"] = d
                threats.append(item)

        heard = [{"from": m["from"], "text": m["text"]} for m in self._said_prev
                 if m["from"] != a.id and cheb(a.x, a.y, m["x"], m["y"]) <= r + 1][:3]
        return {
            "tick": self.tick,
            "me": {"id": a.id, "x": a.x, "y": a.y, "resources": a.resources, "personality": a.personality},
            "nodes": nodes, "agents": agents, "threats": threats, "heard": heard, "extras": extras,
        }

    # --- the tick ------------------------------------------------------------------------------------
    async def step(self) -> dict:
        self.tick += 1
        t = self.tick
        events: List[dict] = list(self._pending)
        self._pending = []

        alive = [a for a in self.agents if a.alive]
        self.env.update(t, {a.id: (a.x, a.y) for a in alive})
        events += [_event(t, "world", txt) for txt in self.env.drain_events()]

        nodes_all, threats_all, extras = self.env.nodes(), self.env.threats(), self.env.extras()
        obs = {a.id: self._observe(a, nodes_all, threats_all, extras) for a in alive}

        # ---- intents -------------------------------------------------------------------------------
        fresh = set()
        for a in alive:
            if a.intent and not intent_valid(a, a.intent, obs[a.id]):
                a.intent = None
        if self._force_round or self.brain.is_round(t):
            self._force_round = False
            plans = await self.brain.plan(alive, obs, self.scenario, t, extras)
            for aid, intent in plans.items():
                next(a for a in alive if a.id == aid).intent = intent
                fresh.add(aid)
        for a in alive:
            if a.intent is None:
                a.intent = choose_intent(a, obs[a.id], self.rng, self.scenario)
                fresh.add(a.id)
                self.brain.stats["fallback_intents"] += 1 if self.brain.use_llm else 0

        said: List[dict] = []
        spoken: Dict[str, str] = {}
        for a in alive:
            if a.id in fresh and a.intent.message and (a.intent.source == "llm" or self.rng.random() < 0.6):
                spoken[a.id] = a.intent.message
                said.append({"from": a.id, "x": a.x, "y": a.y, "text": a.intent.message})

        # ---- actions ---------------------------------------------------------------------------------------
        decisions = {a.id: next_action(a, obs[a.id], self.rng) for a in alive}
        by_id = {a.id: a for a in alive}
        before = {a.id: a.resources for a in alive}
        effects: Dict[str, List[str]] = {a.id: [] for a in alive}
        interactions: List[dict] = []
        done = set()                       # agents whose intent completed this tick
        order = list(alive)
        self.rng.shuffle(order)

        # 1. movement
        for a in alive:
            act = decisions[a.id]["action"]
            if act in DIRS:
                dx, dy = DIRS[act]
                a.x, a.y = clamp(a.x + dx), clamp(a.y + dy)

        # 2. trades: positive-sum only when BOTH sides propose to each other this tick
        offers = {aid: d["target"] for aid, d in decisions.items()
                  if d["action"] == "trade" and d["target"] in by_id}
        settled = set()
        for aid, bid in sorted(offers.items()):
            a, b = by_id[aid], by_id[bid]
            if cheb(a.x, a.y, b.x, b.y) > INTERACT_RANGE:
                continue
            if offers.get(bid) == aid:
                key = frozenset((aid, bid))
                if key in settled:
                    continue
                settled.add(key)
                for x, y in ((a, b), (b, a)):
                    x.resources += TRADE_BONUS
                    x.adjust_trust(y.id, 0.2)
                    x.stats["trades"] += 1
                    effects[x.id].append(f"mutual trade with {y.id} +{TRADE_BONUS}")
                    done.add(x.id)
                self.counters["trades"] += 1
                interactions.append({"type": "trade", "from": aid, "to": bid, "amount": TRADE_BONUS})
                events.append(_event(t, "trade", f"{aid} and {bid} traded (+{TRADE_BONUS} each)", [aid, bid]))
            else:
                a.adjust_trust(bid, -0.03)
                self.counters["offers"] += 1
                effects[aid].append(f"offer to {bid} unanswered")
                interactions.append({"type": "offer", "from": aid, "to": bid, "amount": 0})

        # 3. help (altruism: zero-sum transfer that costs the giver)
        for a in order:
            d = decisions[a.id]
            if d["action"] != "help":
                continue
            b = by_id.get(d["target"])
            if b is None or cheb(a.x, a.y, b.x, b.y) > INTERACT_RANGE:
                continue
            amount = min(HELP_AMOUNT, a.resources - HELP_MIN_KEEP)
            if amount <= 0:
                effects[a.id].append("wanted to help but had too little")
                done.add(a.id)
                continue
            a.resources -= amount
            b.resources += amount
            b.adjust_trust(a.id, 0.25)
            a.adjust_trust(b.id, 0.05)
            a.stats["helps_given"] += 1
            b.stats["helps_received"] += 1
            self.counters["helps"] += 1
            effects[a.id].append(f"gave {amount} to {b.id}")
            effects[b.id].append(f"received {amount} from {a.id}")
            interactions.append({"type": "help", "from": a.id, "to": b.id, "amount": amount})
            events.append(_event(t, "help", f"{a.id} gave {amount} to {b.id}", [a.id, b.id]))
            done.add(a.id)

        # 4. steal (conflict destroys part of the loot; witnesses lose trust in the thief)
        for a in order:
            d = decisions[a.id]
            if d["action"] != "steal":
                continue
            b = by_id.get(d["target"])
            if b is None or cheb(a.x, a.y, b.x, b.y) > STEAL_RANGE or b.resources <= 5:
                continue
            amount = min(max(3, int(b.resources * 0.2)), STEAL_AMOUNT, b.resources - 1)
            b.resources -= amount
            a.resources += int(amount * (1 - STEAL_LOSS))
            b.adjust_trust(a.id, -0.6)
            for w in alive:
                if w.id not in (a.id, b.id) and cheb(w.x, w.y, a.x, a.y) <= VIEW_RADIUS:
                    w.adjust_trust(a.id, -0.12)
            a.stats["steals_done"] += 1
            b.stats["steals_suffered"] += 1
            self.counters["steals"] += 1
            effects[a.id].append(f"stole {amount} from {b.id}")
            effects[b.id].append(f"robbed by {a.id} (-{amount})")
            interactions.append({"type": "steal", "from": a.id, "to": b.id, "amount": amount})
            events.append(_event(t, "steal", f"{a.id} stole {amount} from {b.id}", [a.id, b.id]))
            done.add(a.id)

        # 5. gather
        gatherers = {a.id: (a.x, a.y) for a in alive if decisions[a.id]["action"] == "gather"}
        for aid, res in self.env.resolve_gathers(gatherers).items():
            agent = by_id[aid]
            agent.resources += res.delta
            effects[aid].append(f"{res.label} ({res.delta:+d})")
            if res.success:
                agent.stats["gathered"] += 1
                self.counters["gathers"] += 1
            if res.finished:
                done.add(aid)

        # 6. hazards
        for aid, (amount, label) in self.env.hazard_damage({a.id: (a.x, a.y) for a in alive}).items():
            by_id[aid].resources -= amount
            effects[aid].append(f"{label} (-{amount})")
        events += [_event(t, "world", txt) for txt in self.env.drain_events()]

        # 7. metabolism, caps, deaths, trust decay, intent bookkeeping
        for a in alive:
            a.resources -= METABOLISM
            a.clamp_resources()
            if a.resources <= 0:
                a.resources, a.alive, a.intent = 0, False, None
                a.last = {"action": "dead", "target": None, "source": "rule", "effect": "collapsed",
                          "message": "", "reasoning": "", "delta": a.resources - before[a.id]}
                self.counters["deaths"] += 1
                events.append(_event(t, "death", f"{a.id} ran out of resources", [a.id]))
                continue
            a.decay_trust()
            if a.id in done:
                a.intent = None
            elif a.intent is not None:
                a.intent.ttl -= 1
                if a.intent.ttl <= 0:
                    a.intent = None
            d = decisions[a.id]
            summary = f"T{t} {d['action']}" + (f"→{d['target']}" if d["target"] else "")
            a.remember(summary + (f": {effects[a.id][0]}" if effects[a.id] else ""))
            a.last = {
                "action": d["action"], "target": d["target"], "source": d["source"],
                "effect": "; ".join(effects[a.id]),
                "message": spoken.get(a.id, ""),
                "reasoning": (a.intent.reason if a.intent else "") if a.id in spoken else "",
                "delta": a.resources - before[a.id],
            }

        self._said_prev = said

        # ---- coalitions, metrics, end conditions ----------------------------------------------------------
        living = [a for a in self.agents if a.alive]
        coalitions, coalition_events = self.tracker.update(t, interactions, self.agents)
        events += coalition_events
        metrics = metrics_mod.compute(self.agents, self.counters)
        self.history.append({"tick": t, "avg": metrics["avg_resources"], "alive": metrics["alive"]})

        if not living:
            self.finished, self.end_reason = True, "extinction"
        elif t >= self.max_ticks:
            self.finished, self.end_reason = True, "max_ticks"

        public_agents = []
        for a in self.agents:
            data = a.public()
            if not a.alive and "action" not in data:
                data.update({"action": "dead", "effect": "", "message": "", "reasoning": "", "delta": 0,
                             "target": None, "source": "rule"})
            elif not a.alive:
                data["action"] = "dead"
            public_agents.append(data)

        return {
            "type": "tick",
            "tick": t,
            "scenario": self.scenario,
            "agents": public_agents,
            "env": self.env.render(),
            "score": self.env.score(),
            "interactions": interactions,
            "events": events,
            "coalitions": coalitions,
            "metrics": metrics,
            "brain": self.brain.describe(),
            "finished": self.finished,
            "end_reason": self.end_reason,
        }

    # --- summary ---------------------------------------------------------------------------------------------
    def summary(self) -> dict:
        m = metrics_mod.compute(self.agents, self.counters)
        best = max(self.agents, key=lambda a: (a.alive, a.resources))
        return {
            "type": "complete",
            "reason": self.end_reason or "stopped",
            "ticks": self.tick,
            "seed": self.seed,
            "scenario": self.scenario,
            "survivors": m["alive"],
            "total_agents": m["total"],
            "welfare": m["welfare"],
            "gini": m["gini"],
            "cooperation_index": m["cooperation_index"],
            "helps": m["helps"],
            "trades": m["trades"],
            "steals": m["steals"],
            "by_personality": m["by_personality"],
            "score": self.env.score(),
            "coalitions_formed": self.tracker.formed_total,
            "top_agent": {"id": best.id, "personality": best.personality, "resources": best.resources},
            "brain": self.brain.describe(),
        }
