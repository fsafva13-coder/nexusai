import { useCallback, useEffect, useRef, useState } from "react";
import { wsBase } from "../lib/api";

const MAX_FRAMES = 500;
const MAX_FEED = 400;

/**
 * Owns the WebSocket and everything received over it.
 * status: idle | connecting | running | paused | ended
 */
export function useSimSocket() {
  const wsRef = useRef(null);
  const statusRef = useRef("idle");
  const feedId = useRef(0);
  const [status, setStatusState] = useState("idle");
  const [init, setInit] = useState(null);
  const [frames, setFrames] = useState([]);
  const [feed, setFeed] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  const setStatus = useCallback((s) => {
    statusRef.current = s;
    setStatusState(s);
  }, []);

  const send = useCallback((obj) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }, []);

  const handleMessage = useCallback(
    (msg) => {
      switch (msg.type) {
        case "init":
          setInit(msg);
          setStatus("running");
          break;
        case "tick": {
          setFrames((prev) => {
            const next = prev.length >= MAX_FRAMES ? prev.slice(prev.length - MAX_FRAMES + 1) : prev.slice();
            next.push(msg);
            return next;
          });
          const items = [];
          for (const a of msg.agents) {
            if (a.message) {
              items.push({
                id: `s${msg.tick}-${a.id}`, kind: "say", tick: msg.tick, agent: a.id,
                personality: a.personality, source: a.intent_source ?? a.source,
                text: a.message, reasoning: a.reasoning, intent: a.intent, target: a.intent_target,
              });
            }
          }
          for (const ev of msg.events) {
            items.push({ id: `e${feedId.current++}`, kind: "event", tick: msg.tick, type: ev.type, text: ev.text });
          }
          if (items.length) setFeed((prev) => [...prev, ...items].slice(-MAX_FEED));
          break;
        }
        case "paused":
          setStatus("paused");
          break;
        case "resumed":
          setStatus("running");
          break;
        case "complete":
          setSummary(msg);
          setStatus("ended");
          break;
        case "error":
          setError(msg.message || "The server reported an error.");
          setStatus("ended");
          break;
        default:
          break; // ping, injected (the matching event arrives with the next tick)
      }
    },
    [setStatus],
  );

  const start = useCallback(
    (config) => {
      wsRef.current?.close();
      setInit(null);
      setFrames([]);
      setFeed([]);
      setSummary(null);
      setError(null);
      setStatus("connecting");

      let ws;
      try {
        ws = new WebSocket(`${wsBase()}/ws/${crypto.randomUUID()}`);
      } catch (e) {
        setError(`Could not open a connection: ${e.message}`);
        setStatus("idle");
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: "start", ...config }));
      ws.onmessage = (e) => {
        try {
          handleMessage(JSON.parse(e.data));
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = () => {
        if (statusRef.current === "connecting") {
          setError("Could not reach the simulation server. Is the backend running? (Free hosts can take ~50 s to wake up.)");
        }
      };
      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        if (statusRef.current === "connecting") setStatus("idle");
        else if (statusRef.current !== "ended") {
          setError("Connection to the server was lost.");
          setStatus("ended");
        }
      };
    },
    [handleMessage, setStatus],
  );

  const stop = useCallback(() => {
    send({ type: "stop" });
    const ws = wsRef.current;
    setTimeout(() => {
      if (wsRef.current === ws && statusRef.current !== "ended") {
        ws?.close();
        setStatus("ended");
      }
    }, 2500);
  }, [send, setStatus]);

  useEffect(() => () => wsRef.current?.close(), []);

  return {
    status, init, frames, feed, summary, error,
    start, stop,
    pause: () => send({ type: "pause" }),
    resume: () => send({ type: "resume" }),
    step: () => send({ type: "step" }),
    setSpeed: (ms) => send({ type: "speed", value: ms }),
    inject: (type) => send({ type: "inject", event: { type } }),
    clearError: () => setError(null),
  };
}
