"""NexusAI API: FastAPI + WebSocket simulation server."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import load_settings
from simulation.brain import Brain
from simulation.constants import MAX_AGENTS, PERSONALITIES, PRESETS, SCENARIO_INFO, SCENARIOS
from simulation.engine import SimulationEngine
from simulation.experiments import run_batch
from simulation.llm import LLMClient
from simulation.session import Session

log = logging.getLogger("nexusai")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = load_settings()
shared_llm: Optional[LLMClient] = LLMClient.from_settings(settings)   # one budget for all sessions
if shared_llm:
    log.info("LLM provider: %s (%s) | every %d ticks | %d rpm / %d tpm",
             settings.provider, settings.model, settings.llm_every, settings.llm_rpm, settings.llm_tpm)
else:
    log.info(settings.note or "Rule-based agents (no LLM).")

app = FastAPI(title="NexusAI API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
sessions: set = set()


@app.on_event("shutdown")
async def _shutdown() -> None:
    if shared_llm:
        await shared_llm.aclose()


@app.get("/")
def root():
    return {"name": "NexusAI", "version": "2.0.0", "docs": "/docs", "websocket": "/ws/{session_id}"}


@app.get("/health")
def health():
    return {"status": "ok", "sessions": len(sessions), "llm": settings.provider}


@app.get("/api/config")
def config():
    return {
        "llm": {
            "available": shared_llm is not None,
            "provider": settings.provider,
            "model": settings.model,
            "every": settings.llm_every,
            "note": settings.note,
        },
        "scenarios": {k: {"label": v["label"], "description": v["description"], "crisis": v["crisis"]}
                      for k, v in SCENARIO_INFO.items()},
        "presets": [{"id": k, "label": v["label"]} for k, v in PRESETS.items()],
        "personalities": list(PERSONALITIES),
        "limits": {"max_agents": MAX_AGENTS, "max_ticks": settings.max_ticks_cap},
    }


@app.get("/api/experiment")
async def experiment(
    scenario: str = "disaster",
    preset: str = "balanced",
    agents: int = Query(6, ge=2, le=MAX_AGENTS),
    ticks: int = Query(80, ge=10, le=150),
    seeds: int = Query(5, ge=1, le=8),
):
    """Headless, deterministic, rule-based batch run: handy for comparing strategies."""
    if scenario not in SCENARIOS or preset not in PRESETS:
        raise HTTPException(status_code=400, detail="unknown scenario or preset")
    return await run_batch(scenario, agents, ticks, seeds, preset)


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def build_engine(cfg: dict) -> tuple[SimulationEngine, int]:
    scenario = cfg.get("scenario") if cfg.get("scenario") in SCENARIOS else "disaster"
    seed = cfg.get("seed")
    seed = _int(seed, 0, 0, 10**9) if seed not in (None, "") else None
    personalities = cfg.get("personalities") if isinstance(cfg.get("personalities"), list) else None
    preset = cfg.get("preset") if cfg.get("preset") in PRESETS else "balanced"
    use_llm = bool(cfg.get("use_llm", True)) and shared_llm is not None
    brain = Brain(shared_llm, every=settings.llm_every, use_llm=use_llm)
    engine = SimulationEngine(
        scenario=scenario,
        num_agents=_int(cfg.get("num_agents"), 6, 2, MAX_AGENTS),
        seed=seed,
        personalities=personalities,
        preset=preset,
        brain=brain,
        max_ticks=_int(cfg.get("max_ticks"), 100, 10, settings.max_ticks_cap),
    )
    return engine, _int(cfg.get("speed_ms"), 2500, 0, 10_000)


@app.websocket("/ws/{sim_id}")
async def simulation_socket(websocket: WebSocket, sim_id: str):
    await websocket.accept()

    async def send(obj: dict) -> None:
        await websocket.send_text(json.dumps(obj))

    if len(sessions) >= settings.max_sessions:
        await send({"type": "error", "message": "Server is busy. Try again in a minute."})
        await websocket.close(code=1013)
        return

    inbox: asyncio.Queue = asyncio.Queue()

    async def reader() -> None:
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict):
                    await inbox.put(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            await inbox.put({"type": "__disconnect__"})

    reader_task = asyncio.create_task(reader())
    sessions.add(sim_id)
    try:
        cfg = None
        while cfg is None:
            msg = await asyncio.wait_for(inbox.get(), timeout=20)
            if msg.get("type") == "__disconnect__":
                return
            if msg.get("type") in (None, "start"):
                cfg = msg
        engine, speed_ms = build_engine(cfg)
        log.info("session %s: %s, %d agents, brain=%s", sim_id[:8], engine.scenario,
                 len(engine.agents), engine.brain.mode)
        await Session(engine, send, inbox, speed_ms).run()
    except asyncio.TimeoutError:
        log.info("session %s: no start message received", sim_id[:8])
    except (WebSocketDisconnect, RuntimeError):
        log.info("session %s: client disconnected", sim_id[:8])
    except Exception as exc:  # noqa: BLE001
        log.exception("session %s failed", sim_id[:8])
        try:
            await send({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        except Exception:  # noqa: BLE001
            pass
    finally:
        reader_task.cancel()
        sessions.discard(sim_id)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
