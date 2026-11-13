"""Drives one engine over a message channel (a WebSocket in production, a queue in tests).

Control messages from the client: pause, resume, step, speed, inject, stop.
A dedicated reader task feeds ``inbox`` so that waiting for the next tick never
cancels a socket read (which can drop messages).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from .engine import SimulationEngine

Send = Callable[[dict], Awaitable[None]]


class Session:
    def __init__(self, engine: SimulationEngine, send: Send, inbox: "asyncio.Queue[dict]",
                 speed_ms: int = 2500):
        self.engine = engine
        self.send = send
        self.inbox = inbox
        self.speed_ms = max(0, min(10_000, int(speed_ms)))
        self.paused = False
        self._next_at = 0.0

    async def _handle(self, msg: dict, loop: asyncio.AbstractEventLoop) -> Optional[str]:
        kind = msg.get("type")
        if kind == "__disconnect__":
            return "disconnect"
        if kind == "stop":
            return "stop"
        if kind == "pause":
            if not self.paused:
                self.paused = True
                await self.send({"type": "paused", "tick": self.engine.tick})
        elif kind == "resume":
            if self.paused:
                self.paused = False
                self._next_at = loop.time()
                await self.send({"type": "resumed", "tick": self.engine.tick})
        elif kind == "step":
            if self.paused:
                return "step"
        elif kind == "speed":
            try:
                self.speed_ms = max(0, min(10_000, int(msg.get("value", self.speed_ms))))
            except (TypeError, ValueError):
                pass
        elif kind == "inject":
            event = msg.get("event")
            name = event.get("type") if isinstance(event, dict) else event
            text = self.engine.inject(str(name))
            if text:
                await self.send({"type": "injected", "event": name, "text": text})
        return None

    async def run(self) -> str:
        """Run until the engine finishes, the client stops, or the client disconnects."""
        loop = asyncio.get_running_loop()
        await self.send(self.engine.init_payload())
        self._next_at = loop.time() + 0.4
        reason = "finished"

        while not self.engine.finished:
            if self.paused:
                timeout: Optional[float] = 20.0            # heartbeat so proxies keep the socket open
            else:
                timeout = max(0.0, self._next_at - loop.time())

            msg: Optional[dict] = None
            if timeout > 0:
                try:
                    msg = await asyncio.wait_for(self.inbox.get(), timeout)
                except asyncio.TimeoutError:
                    msg = None
            else:
                try:
                    msg = self.inbox.get_nowait()
                except asyncio.QueueEmpty:
                    msg = None

            if msg is not None:
                action = await self._handle(msg, loop)
                if action == "disconnect":
                    return "disconnected"
                if action == "stop":
                    reason = "stopped"
                    break
                if action != "step":
                    continue
            elif self.paused:
                await self.send({"type": "ping"})
                continue

            state = await self.engine.step()
            await self.send(state)
            self._next_at = loop.time() + self.speed_ms / 1000

        if reason == "stopped" and not self.engine.finished:
            self.engine.end_reason = "stopped"
        await self.send(self.engine.summary())
        return reason
