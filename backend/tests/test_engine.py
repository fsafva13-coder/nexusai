import asyncio

import pytest

from simulation.agent import Intent
from simulation.constants import GRID_SIZE, RESOURCE_CAP, SCENARIOS, TRADE_BONUS
from simulation.engine import SimulationEngine


def run(coro):
    return asyncio.run(coro)


async def run_full(engine):
    while not engine.finished:
        await engine.step()
    return engine.summary()


def duo(scenario="market", personalities=("neutral", "neutral")):
    """Two agents standing next to each other in the hazard-free market."""
    e = SimulationEngine(scenario, 2, seed=3, personalities=list(personalities), max_ticks=20)
    a1, a2 = e.agents
    a1.x, a1.y, a2.x, a2.y = 5, 5, 6, 5
    return e, a1, a2


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_invariants_hold_for_every_scenario(scenario):
    e = SimulationEngine(scenario, 6, seed=11, max_ticks=60)

    async def go():
        while not e.finished:
            state = await e.step()
            for a in state["agents"]:
                assert 0 <= a["resources"] <= RESOURCE_CAP
                assert 0 <= a["x"] < GRID_SIZE and 0 <= a["y"] < GRID_SIZE
                if not a["alive"]:
                    assert a["resources"] == 0
            m = state["metrics"]
            assert 0.0 <= m["gini"] <= 1.0
            assert 0.0 <= m["cooperation_index"] <= 1.0

    run(go())
    assert e.finished and e.end_reason in ("max_ticks", "extinction")


def test_same_seed_is_deterministic_and_different_seed_differs():
    a = run(run_full(SimulationEngine("ecosystem", 6, seed=5, max_ticks=50)))
    b = run(run_full(SimulationEngine("ecosystem", 6, seed=5, max_ticks=50)))
    c = run(run_full(SimulationEngine("ecosystem", 6, seed=6, max_ticks=50)))
    keys = ("welfare", "gini", "helps", "trades", "steals", "by_personality", "score")
    assert {k: a[k] for k in keys} == {k: b[k] for k in keys}
    assert {k: a[k] for k in keys} != {k: c[k] for k in keys}


def test_mutual_trade_is_positive_sum():
    e, a1, a2 = duo()
    a1.intent = Intent("trade", "A2", ttl=3)
    a2.intent = Intent("trade", "A1", ttl=3)
    run(e.step())
    # +bonus each, minus one tick of metabolism (2)
    assert a1.resources == a2.resources == 100 + TRADE_BONUS - 2
    assert e.counters["trades"] == 1
    assert a1.trust["A2"] > 0 and a2.trust["A1"] > 0


def test_unreciprocated_trade_gives_nothing_and_costs_trust():
    e, a1, a2 = duo()
    a1.intent = Intent("trade", "A2", ttl=3)
    a2.intent = Intent("rest", None, ttl=3)
    run(e.step())
    assert a1.resources == a2.resources == 98
    assert e.counters["trades"] == 0 and e.counters["offers"] == 1
    assert a1.trust["A2"] < 0


def test_help_is_a_zero_sum_transfer():
    e, a1, a2 = duo()
    a1.intent = Intent("help", "A2", ttl=3)
    a2.intent = Intent("rest", None, ttl=3)
    run(e.step())
    assert a1.resources == 100 - 12 - 2
    assert a2.resources == 100 + 12 - 2
    assert a2.trust["A1"] > a1.trust["A2"] > 0


def test_steal_destroys_value_and_destroys_trust():
    e, a1, a2 = duo()
    a1.intent = Intent("steal", "A2", ttl=2)
    a2.intent = Intent("rest", None, ttl=3)
    run(e.step())
    assert a2.resources == 100 - 12 - 2
    assert a1.resources == 100 + 9 - 2          # 20% of the loot is lost in the scuffle
    assert a2.trust["A1"] < -0.5
    assert e.counters["steals"] == 1


def test_witnesses_lose_trust_in_a_thief():
    e = SimulationEngine("market", 3, seed=3, personalities=["neutral"] * 3, max_ticks=10)
    a1, a2, a3 = e.agents
    a1.x, a1.y, a2.x, a2.y, a3.x, a3.y = 5, 5, 6, 5, 5, 6
    a1.intent = Intent("steal", "A2", ttl=2)
    a2.intent = Intent("rest", None, ttl=3)
    a3.intent = Intent("rest", None, ttl=3)
    run(e.step())
    assert a3.trust["A1"] < 0           # reputation damage from merely watching


def test_injection_effects():
    e = SimulationEngine("disaster", 4, seed=1, max_ticks=20)
    assert e.inject("drain") and all(a.resources == 80 for a in e.agents)
    assert e.inject("boost") and all(a.resources == 110 for a in e.agents)
    assert "ire" in e.inject("crisis")           # a new fire
    assert e.inject("bogus") is None
    state = run(e.step())
    assert any(ev["type"] == "inject" for ev in state["events"])


def test_disaster_heavy_survivor_needs_two_rescuers():
    e = SimulationEngine("disaster", 2, seed=2, personalities=["cooperative"] * 2, max_ticks=10)
    env = e.env
    env.fires.clear()
    env.survivors = [{"id": "S1", "x": 4, "y": 4, "needs": 2, "value": 30, "burn": 0,
                      "status": "waiting", "gone_at": None}]
    solo = env.resolve_gathers({"A1": (4, 4)})
    assert not solo["A1"].success and not solo["A1"].finished        # keep waiting for a partner
    both = env.resolve_gathers({"A1": (4, 4), "A2": (4, 4)})
    assert both["A1"].success and both["A2"].success and both["A1"].delta == 30
    assert env.rescued == 1


def test_predators_cannot_hurt_a_herd():
    e = SimulationEngine("ecosystem", 2, seed=2, max_ticks=10)
    env = e.env
    env.predators = [{"id": "P1", "x": 5, "y": 5, "cool": 0}]
    herd = env.hazard_damage({"A1": (5, 6), "A2": (6, 6)})
    assert herd == {} and env.repelled == 1
    env.predators = [{"id": "P1", "x": 5, "y": 5, "cool": 0}]
    alone = env.hazard_damage({"A1": (5, 6), "A2": (11, 11)})
    assert "A1" in alone and env.hits == 1


def test_market_traps_are_negative():
    e = SimulationEngine("market", 2, seed=2, max_ticks=10)
    env = e.env
    env.assets["oil"]["trend"] = -2.0
    env.assets["tech"]["trend"] = 2.0
    env.deals = [{"id": "D1", "x": 1, "y": 1, "asset": "oil", "value": 30},
                 {"id": "D2", "x": 2, "y": 2, "asset": "tech", "value": 30}]
    est = {n["id"]: n["est"] for n in env.nodes()}
    assert est["D1"] < 0 < est["D2"]


def test_extinction_ends_the_run():
    e = SimulationEngine("market", 2, seed=2, max_ticks=100)
    for a in e.agents:
        a.resources = 1
    state = run(e.step())
    assert state["finished"] and state["end_reason"] == "extinction"
    assert state["metrics"]["alive"] == 0
