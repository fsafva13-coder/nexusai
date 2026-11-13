"""Emergent coalition detection.

Every cooperative interaction strengthens an (undirected) alliance edge; weights
decay each tick, so alliances only persist while agents keep cooperating.
Theft strengthens a rivalry edge and weakens the alliance between the pair.
Coalitions are the connected components of edges above a threshold, with
hysteresis so groups do not flicker. Union-find does the grouping.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, FrozenSet, List, Tuple

COLORS = {
    "cooperative": "#8fd3b0",
    "competitive": "#ef7f95",
    "neutral": "#9db7f5",
    "mixed": "#d9b779",
}

Pair = FrozenSet[str]


class CoalitionTracker:
    def __init__(self, decay: float = 0.9, threshold: float = 1.4, hysteresis: float = 0.6):
        self.decay = decay
        self.threshold = threshold
        self.hysteresis = hysteresis
        self.alliance: Dict[Pair, float] = defaultdict(float)
        self.rivalry: Dict[Pair, float] = defaultdict(float)
        self._active_pairs: set = set()
        self._groups: Dict[Tuple[str, ...], int] = {}   # members -> tick first seen
        self.formed_total = 0

    # --- update -------------------------------------------------------------------
    def update(self, tick: int, interactions: List[dict], agents: List) -> Tuple[dict, List[dict]]:
        for table in (self.alliance, self.rivalry):
            for key in list(table):
                table[key] *= self.decay
                if table[key] < 0.05:
                    del table[key]

        for it in interactions:
            pair = frozenset((it["from"], it["to"]))
            if len(pair) != 2:
                continue
            if it["type"] in ("help", "trade"):
                self.alliance[pair] += 1.0
            elif it["type"] == "steal":
                self.rivalry[pair] += 1.0
                if pair in self.alliance:
                    self.alliance[pair] *= 0.3

        alive = {a.id: a for a in agents if a.alive}
        active = set()
        for pair, weight in self.alliance.items():
            if not pair <= alive.keys():
                continue
            limit = self.threshold * (self.hysteresis if pair in self._active_pairs else 1.0)
            if weight >= limit:
                active.add(pair)
        self._active_pairs = active

        groups = self._components(alive, active)
        events = self._diff(tick, groups)
        return self._serialise(groups, alive), events

    # --- grouping -----------------------------------------------------------------------
    @staticmethod
    def _components(alive: Dict[str, object], pairs: set) -> List[List[str]]:
        parent = {aid: aid for aid in alive}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for pair in pairs:
            a, b = tuple(pair)
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        buckets: Dict[str, List[str]] = defaultdict(list)
        for aid in alive:
            buckets[find(aid)].append(aid)
        return [sorted(members) for members in buckets.values() if len(members) > 1]

    def _diff(self, tick: int, groups: List[List[str]]) -> List[dict]:
        current = {tuple(g) for g in groups}
        previous = set(self._groups)
        events: List[dict] = []
        for key in sorted(current - previous):
            overlap = any(set(key) & set(old) for old in previous)
            verb = "reshaped into" if overlap else "formed"
            if not overlap:
                self.formed_total += 1
            events.append({"tick": tick, "type": "coalition",
                           "text": f"Coalition {verb}: {' + '.join(key)}", "agents": list(key)})
            self._groups[key] = tick
        for key in sorted(previous - current):
            del self._groups[key]
            if not any(set(key) & set(new) for new in current):
                events.append({"tick": tick, "type": "coalition",
                               "text": f"Coalition dissolved: {' + '.join(key)}", "agents": list(key)})
        return events

    def _serialise(self, groups: List[List[str]], alive: Dict[str, object]) -> dict:
        out = []
        for members in groups:
            counts = Counter(alive[m].personality for m in members)
            top, n = counts.most_common(1)[0]
            label = top if n / len(members) >= 0.6 else "mixed"
            inner = [self.alliance[frozenset((a, b))]
                     for i, a in enumerate(members) for b in members[i + 1:]
                     if frozenset((a, b)) in self._active_pairs]
            out.append({
                "id": "+".join(members),
                "members": members,
                "size": len(members),
                "dominant_personality": label,
                "color": COLORS[label],
                "cohesion": round(sum(inner) / len(inner), 2) if inner else 0.0,
                "since": self._groups.get(tuple(members), 0),
            })
        edges = [{"a": min(p), "b": max(p), "w": round(w, 2), "kind": "alliance"}
                 for p, w in self.alliance.items() if w >= 0.5 and p <= alive.keys()]
        edges += [{"a": min(p), "b": max(p), "w": round(w, 2), "kind": "rivalry"}
                  for p, w in self.rivalry.items() if w >= 0.8 and p <= alive.keys()]
        return {"groups": out, "edges": edges, "total": len(out)}
