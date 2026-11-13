import os

os.environ["LLM_PROVIDER"] = "none"      # tests must never touch the network

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def recv_until(ws, wanted, limit=200):
    seen = []
    for _ in range(limit):
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == wanted:
            return msg, seen
    raise AssertionError(f"never received {wanted}; got {[m['type'] for m in seen][-5:]}")


def test_http_endpoints():
    assert client.get("/health").json()["status"] == "ok"
    cfg = client.get("/api/config").json()
    assert cfg["llm"]["available"] is False and "balanced" in {p["id"] for p in cfg["presets"]}
    assert set(cfg["scenarios"]) == {"disaster", "market", "ecosystem"}
    exp = client.get("/api/experiment", params={"scenario": "market", "ticks": 20, "seeds": 2}).json()
    assert exp["runs"] == 2 and "by_personality" in exp
    assert client.get("/api/experiment", params={"scenario": "nope"}).status_code == 400


def test_full_websocket_run():
    with client.websocket_connect("/ws/test-run") as ws:
        ws.send_json({"type": "start", "scenario": "market", "num_agents": 3,
                      "speed_ms": 0, "max_ticks": 12, "seed": 7})
        init = ws.receive_json()
        assert init["type"] == "init" and init["seed"] == 7 and len(init["agents"]) == 3
        done, seen = recv_until(ws, "complete")
        ticks = [m for m in seen if m["type"] == "tick"]
        assert [t["tick"] for t in ticks][:3] == [1, 2, 3]
        assert done["ticks"] <= 12 and done["scenario"] == "market"
        first = ticks[0]
        assert {"agents", "env", "coalitions", "metrics", "interactions", "events", "brain"} <= set(first)


def test_controls_pause_step_inject_speed_stop():
    with client.websocket_connect("/ws/test-controls") as ws:
        ws.send_json({"type": "start", "scenario": "ecosystem", "num_agents": 4, "speed_ms": 150, "max_ticks": 100})
        assert ws.receive_json()["type"] == "init"
        ws.send_json({"type": "pause"})
        recv_until(ws, "paused")
        ws.send_json({"type": "inject", "event": {"type": "crisis"}})
        injected, _ = recv_until(ws, "injected")
        assert "redator" in injected["text"]
        ws.send_json({"type": "step"})
        stepped, _ = recv_until(ws, "tick")
        assert any(e["type"] == "inject" for e in stepped["events"])
        ws.send_json({"type": "speed", "value": 400})
        ws.send_json({"type": "resume"})
        recv_until(ws, "resumed")
        ws.send_json({"type": "stop"})
        done, _ = recv_until(ws, "complete")
        assert done["reason"] == "stopped"


def test_bad_input_is_sanitised():
    with client.websocket_connect("/ws/test-bad") as ws:
        ws.send_text("not json at all")
        ws.send_json({"type": "start", "scenario": "<script>", "num_agents": 999, "speed_ms": "fast",
                      "max_ticks": 10 ** 9, "use_llm": True})
        init = ws.receive_json()
        assert init["scenario"] == "disaster" and len(init["agents"]) == 8
        assert init["max_ticks"] <= main.settings.max_ticks_cap
        ws.send_json({"type": "stop"})
        recv_until(ws, "complete")
