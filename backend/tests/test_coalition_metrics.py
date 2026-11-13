import random
from collections import Counter

from simulation.agent import Agent
from simulation.coalition_detector import CoalitionTracker
from simulation.metrics import by_personality, cooperation_index, gini


def agents(*kinds):
    return [Agent(f"A{i + 1}", k, i, 0, random.Random(0)) for i, k in enumerate(kinds)]


def helps(a, b):
    return {"type": "help", "from": a, "to": b, "amount": 12}


def test_gini_extremes():
    assert gini([10, 10, 10, 10]) == 0
    assert gini([0, 0, 0, 100]) == 0.75
    assert gini([]) == 0 and gini([0, 0]) == 0


def test_cooperation_index():
    assert cooperation_index(Counter()) == 0
    assert cooperation_index(Counter(helps=3, trades=1, steals=4)) == 0.5


def test_by_personality_counts_dead_as_zero():
    group = agents("cooperative", "cooperative", "competitive")
    group[0].resources, group[1].resources, group[2].resources = 80, 0, 50
    group[1].alive = False
    assert by_personality(group) == {"cooperative": 40.0, "competitive": 50.0}


def test_coalition_forms_after_repeated_cooperation_and_labels_itself():
    t = CoalitionTracker()
    ag = agents("cooperative", "cooperative", "competitive")
    state, events = t.update(1, [helps("A1", "A2")], ag)
    assert state["total"] == 0                          # a single interaction is not an alliance
    state, events = t.update(2, [helps("A2", "A1")], ag)
    assert state["total"] == 1
    group = state["groups"][0]
    assert group["members"] == ["A1", "A2"] and group["dominant_personality"] == "cooperative"
    assert any("formed" in e["text"] for e in events)


def test_coalition_decays_without_interaction():
    t = CoalitionTracker()
    ag = agents("neutral", "neutral")
    for tick in (1, 2, 3):
        t.update(tick, [helps("A1", "A2")], ag)
    assert t.update(4, [], ag)[0]["total"] == 1
    last_events = []
    for tick in range(5, 30):
        state, ev = t.update(tick, [], ag)
        last_events += ev
    assert state["total"] == 0 and any("dissolved" in e["text"] for e in last_events)


def test_theft_breaks_an_alliance_and_creates_a_rivalry():
    t = CoalitionTracker()
    ag = agents("neutral", "neutral")
    for tick in (1, 2, 3):
        t.update(tick, [helps("A1", "A2")], ag)
    state, _ = t.update(4, [{"type": "steal", "from": "A1", "to": "A2", "amount": 10}], ag)
    assert state["total"] == 0
    assert any(e["kind"] == "rivalry" for e in state["edges"])


def test_dead_agents_leave_coalitions_and_mixed_groups_are_labelled():
    t = CoalitionTracker()
    ag = agents("cooperative", "competitive")
    for tick in (1, 2, 3):
        state, _ = t.update(tick, [helps("A1", "A2")], ag)
    assert state["groups"][0]["dominant_personality"] == "mixed"
    ag[1].alive = False
    assert t.update(4, [], ag)[0]["total"] == 0
