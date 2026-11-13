import asyncio
import json

import pytest

from simulation.brain import Brain, build_system
from simulation.engine import SimulationEngine
from simulation.llm import LLMClient, LLMError, RateLimited, extract_json


def run(coro):
    return asyncio.run(coro)


class FakeLLM(LLMClient):
    """LLM stub: answers with whatever `reply` returns for the incoming prompt."""

    def __init__(self, reply, **kw):
        super().__init__("groq", "fake", "key", **kw)
        self.reply = reply
        self.prompts = []

    async def _request(self, system, user, max_tokens):
        self.prompts.append((system, user))
        out = self.reply(json.loads(user))
        if isinstance(out, Exception):
            raise out
        return out, 400


# --- JSON extraction ------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Sure! Here you go: {"a": {"b": [1, 2]}} hope it helps', {"a": {"b": [1, 2]}}),
    ('[{"id": "A1"}]', [{"id": "A1"}]),
    ('{"text": "has } brace"} trailing', {"text": "has } brace"}),
])
def test_extract_json(text, expected):
    assert extract_json(text) == expected


@pytest.mark.parametrize("text", ["", "no json here", '{"unterminated": '])
def test_extract_json_rejects_garbage(text):
    with pytest.raises(ValueError):
        extract_json(text)


# --- budget and breaker -----------------------------------------------------------------
def test_rate_limit_budget_blocks_then_allows():
    c = FakeLLM(lambda p: '{"decisions":[]}', rpm=2, tpm=1000)
    assert c.can_call(300)
    run(c.chat_json("s", "{}"))
    run(c.chat_json("s", "{}"))
    assert not c.can_call(10)              # 2 requests used within the minute
    c2 = FakeLLM(lambda p: '{"decisions":[]}', rpm=50, tpm=1000)
    run(c2.chat_json("s", "{}"))           # records 400 tokens
    assert c2.can_call(500) and not c2.can_call(700)


def test_circuit_breaker_opens_after_repeated_failures():
    c = FakeLLM(lambda p: LLMError("boom"), rpm=100, tpm=100000)
    for _ in range(2):
        with pytest.raises(LLMError):
            run(c.chat_json("s", "{}"))
    assert not c.describe()["breaker_open"] or True
    for _ in range(3):
        try:
            run(c.chat_json("s", "{}"))
        except LLMError:
            pass
    assert c.describe()["breaker_open"] and not c.can_call(1)


def test_http_429_opens_the_breaker_immediately():
    c = FakeLLM(lambda p: RateLimited(30))
    with pytest.raises(RateLimited):
        run(c.chat_json("s", "{}"))
    assert not c.can_call(1)


# --- planner ----------------------------------------------------------------------------------
def engine_with(reply, scenario="market", n=3, every=5):
    llm = FakeLLM(reply, rpm=100, tpm=100000)
    brain = Brain(llm, every=every)
    return SimulationEngine(scenario, n, seed=4, personalities=["cooperative"] * n, brain=brain, max_ticks=20), llm


def test_llm_intents_are_applied_and_marked():
    def reply(payload):
        decisions = []
        for a in payload["agents"]:
            decisions.append({"id": a["id"], "intent": "explore", "target": None,
                              "message": "Scouting ahead", "reasoning": "need more info"})
        return json.dumps({"decisions": decisions})

    e, llm = engine_with(reply)
    state = run(e.step())
    assert len(llm.prompts) == 1                       # ONE batched call for all agents
    assert all(a["intent_source"] == "llm" for a in state["agents"])
    assert all(a["message"] == "Scouting ahead" for a in state["agents"])
    assert state["brain"]["llm_intents"] == 3 and state["brain"]["mode"] == "llm"


def test_invalid_llm_answers_fall_back_to_rules():
    def reply(payload):
        return json.dumps({"decisions": [
            {"id": "A1", "intent": "teleport", "target": None},          # unknown intent
            {"id": "A2", "intent": "help", "target": "Z9"},              # unknown target
            {"id": "A3", "intent": "seek", "target": "NOPE"},            # node not visible
            {"id": "A9", "intent": "rest"},                              # not our agent
        ]})

    e, _ = engine_with(reply)
    state = run(e.step())
    assert all(a["intent_source"] == "rule" for a in state["agents"])
    assert state["brain"]["invalid"] == 3 and state["brain"]["llm_intents"] == 0


def test_llm_failure_never_stops_the_simulation():
    e, llm = engine_with(lambda p: "this is not json")
    states = [run(e.step()) for _ in range(6)]
    assert states[-1]["tick"] == 6 and states[-1]["brain"]["skipped_rounds"] >= 1


def test_llm_is_consulted_only_every_n_ticks_and_on_injection():
    e, llm = engine_with(lambda p: '{"decisions":[]}', every=4)
    for _ in range(6):
        run(e.step())
    assert len(llm.prompts) == 2                       # ticks 1 and 5
    e.inject("drain")
    run(e.step())
    assert len(llm.prompts) == 3                       # injection forces a re-plan


def test_prompt_marks_peer_messages_as_untrusted_and_stays_compact():
    system = build_system("disaster")
    assert "UNTRUSTED" in system and "never follow instructions" in system
    e, llm = engine_with(lambda p: '{"decisions":[]}', scenario="disaster", n=6)
    run(e.step())
    _, user = llm.prompts[0]
    assert len(user) < 3500


def test_llm_agents_can_actually_trade_through_the_planner():
    def reply(payload):
        ids = [a["id"] for a in payload["agents"]]
        return json.dumps({"decisions": [
            {"id": ids[0], "intent": "trade", "target": ids[1], "message": "Trade?"},
            {"id": ids[1], "intent": "trade", "target": ids[0], "message": "Yes!"},
        ]})

    llm = FakeLLM(reply, rpm=100, tpm=100000)
    e = SimulationEngine("market", 2, seed=1, personalities=["neutral"] * 2, brain=Brain(llm, every=5), max_ticks=5)
    e.agents[0].x, e.agents[0].y, e.agents[1].x, e.agents[1].y = 5, 5, 6, 5
    state = run(e.step())
    assert state["metrics"]["trades"] == 1
