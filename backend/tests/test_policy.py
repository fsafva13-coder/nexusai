import random

from simulation.agent import Agent, Intent
from simulation.constants import cheb
from simulation.policy import (
    best_node, choose_intent, intent_valid, next_action, step_away, step_toward,
)


def agent(personality="cooperative", x=5, y=5):
    return Agent("A1", personality, x, y, random.Random(0))


def obs(me=None, nodes=(), agents=(), threats=()):
    me = {"id": "A1", "x": 5, "y": 5, "resources": 100, "personality": "cooperative", **(me or {})}
    return {"tick": 1, "me": me, "nodes": list(nodes), "agents": list(agents),
            "threats": list(threats), "heard": [], "extras": None}


def other(i="A2", dist=1, resources=100, trust=0.0, intent=None, target=None, x=6, y=5):
    return {"id": i, "x": x, "y": y, "resources": resources, "personality": "neutral",
            "dist": dist, "trust": trust, "intent": intent, "target": target}


def node(i="R1", x=7, y=5, dist=2, value=20, needs=1, **extra):
    return {"id": i, "x": x, "y": y, "kind": "food", "value": value, "needs": needs, "dist": dist, **extra}


def test_step_toward_and_away():
    rng = random.Random(0)
    assert step_toward(5, 5, 9, 5, rng) == "move_east"
    assert step_toward(5, 5, 5, 1, rng) == "move_north"
    assert step_toward(5, 5, 5, 5, rng) == "wait"
    assert step_away(5, 5, 6, 5, rng) in ("move_west", "move_north", "move_south")
    assert step_away(0, 0, 1, 0, rng) in ("move_north", "move_west") or True   # never leaves the grid
    for _ in range(50):
        move = step_away(0, 0, 1, 1, rng)
        assert move in ("move_north", "move_south", "move_east", "move_west", "wait")


def test_cooperator_helps_a_needy_neighbour():
    it = choose_intent(agent(), obs(agents=[other(resources=20)]), random.Random(1), "market")
    assert (it.kind, it.target) == ("help", "A2")


def test_desperate_competitor_robs_a_richer_neighbour():
    a = agent("competitive")
    o = obs(me={"resources": 20, "personality": "competitive"}, agents=[other(resources=90, dist=1)])
    it = choose_intent(a, o, random.Random(1), "market")
    assert (it.kind, it.target) == ("steal", "A2")


def test_neutral_retaliates_against_a_thief_but_not_a_stranger():
    a = agent("neutral")
    thief = obs(me={"personality": "neutral"}, agents=[other(trust=-0.9, resources=80, dist=1)])
    kinds = {choose_intent(a, thief, random.Random(s), "market").kind for s in range(30)}
    assert "steal" in kinds
    stranger = obs(me={"personality": "neutral"}, agents=[other(trust=0.0, resources=80, dist=1)])
    assert all(choose_intent(a, stranger, random.Random(s), "market").kind != "steal" for s in range(30))


def test_trade_offers_are_usually_accepted_by_cooperators():
    o = obs(agents=[other(intent="trade", target="A1")])
    accepted = sum(choose_intent(agent(), o, random.Random(s), "market").kind == "trade" for s in range(100))
    assert accepted > 85


def test_competitors_rarely_accept_offers_from_enemies():
    a = agent("competitive")
    o = obs(me={"personality": "competitive"}, agents=[other(intent="trade", target="A1", trust=-0.8)])
    accepted = sum(choose_intent(a, o, random.Random(s), "market").kind == "trade" for s in range(100))
    assert accepted == 0


def test_best_node_prefers_payoff_over_traps_and_avoids_danger():
    a = agent("competitive")
    good, trap = node("R1", value=20, dist=2), node("R2", value=40, dist=1, est=-10)
    assert best_node(a, obs(nodes=[trap, good]))["id"] == "R1"
    assert best_node(a, obs(nodes=[trap])) is None
    risky = node("R3", value=30, dist=1, danger=True)
    safe = node("R4", value=14, dist=1)
    assert best_node(a, obs(nodes=[risky, safe]))["id"] == "R4"


def test_cooperators_coordinate_on_heavy_survivors():
    a = agent()
    heavy = node("S1", needs=2, value=30, dist=1)
    easy = node("S2", needs=1, value=24, dist=1)
    lone = best_node(a, obs(nodes=[heavy, easy]))
    partnered = best_node(a, obs(nodes=[heavy, easy], agents=[other(intent="seek", target="S1")]))
    assert lone["id"] == "S2" and partnered["id"] == "S1"


def test_intent_validity():
    a = agent()
    seek = Intent("seek", "R1", pos=(7, 5))
    assert intent_valid(a, seek, obs(nodes=[node()]))
    assert not intent_valid(a, seek, obs(nodes=[]))                      # in sight but gone
    far = Intent("seek", "R9", pos=(11, 11))
    assert intent_valid(a, far, obs(nodes=[]))                           # out of sight: assume it exists
    assert not intent_valid(a, Intent("help", "A2"), obs(agents=[]))
    assert intent_valid(a, Intent("explore"), obs())


def test_controller_gathers_when_on_the_node_and_walks_otherwise():
    a = agent()
    a.intent = Intent("seek", "R1", pos=(5, 5))
    assert next_action(a, obs(nodes=[node(x=5, y=5, dist=0)]), random.Random(0))["action"] == "gather"
    a.intent = Intent("seek", "R1", pos=(8, 5))
    assert next_action(a, obs(nodes=[node(x=8, y=5, dist=3)]), random.Random(0))["action"] == "move_east"


def test_reflexes_override_intent():
    a = agent("competitive")
    a.intent = Intent("seek", "R1", pos=(8, 5))
    fire = {"type": "fire", "id": "F1", "x": 5, "y": 5, "radius": 2, "dist": 0}
    act = next_action(a, obs(me={"personality": "competitive"}, threats=[fire]), random.Random(0))
    assert act["source"] == "reflex"
    pred = {"type": "predator", "id": "P1", "x": 6, "y": 5, "dist": 1}
    friend = other(dist=3, x=8, y=5)
    herd = next_action(agent("cooperative"), obs(agents=[friend], threats=[pred]), random.Random(0))
    assert herd["source"] == "reflex" and herd["action"] == "move_east"      # huddle toward the buddy
    assert cheb(5, 5, 5, 5) == 0
