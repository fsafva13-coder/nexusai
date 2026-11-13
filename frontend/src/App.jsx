import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Hexagon } from "lucide-react";
import { useSimSocket } from "./hooks/useSimSocket";
import { BACKEND_URL, fetchConfig } from "./lib/api";
import { DEFAULT_FORM, PERSONALITY } from "./lib/constants";
import { exportCsv, exportJson } from "./lib/export";
import AgentInspector from "./components/AgentInspector";
import CoalitionGraph from "./components/CoalitionGraph";
import ControlPanel from "./components/ControlPanel";
import DialogueFeed from "./components/DialogueFeed";
import ReplayBar from "./components/ReplayBar";
import RunSummary from "./components/RunSummary";
import SimCanvas from "./components/SimCanvas";
import StatsPanel from "./components/StatsPanel";

const STATUS = {
  idle: ["Idle", "bg-white/10 text-mute"],
  connecting: ["Connecting…", "bg-gold/15 text-gold pulse-dot"],
  running: ["Running", "bg-coop/15 text-coop"],
  paused: ["Paused", "bg-neut/15 text-neut"],
  ended: ["Finished", "bg-comp/15 text-comp"],
};

export default function App() {
  const sim = useSimSocket();
  const { status, init, frames, feed, summary, error } = sim;

  const [form, setForm] = useState(DEFAULT_FORM);
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchConfig(ctrl.signal).then(setConfig).catch((e) => {
      if (e.name !== "AbortError") setConfigError(e.message);
    });
    return () => ctrl.abort();
  }, []);

  // keep the canvas theme in sync with the running scenario
  const scenario = init?.scenario ?? form.scenario;

  // replay playback
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => {
      setCursor((c) => {
        const next = (c ?? 0) + 1;
        if (next >= frames.length - 1) {
          setPlaying(false);
          return null;
        }
        return next;
      });
    }, 350);
    return () => clearInterval(timer);
  }, [playing, frames.length]);

  // a new run resets the view
  useEffect(() => {
    if (status === "connecting") {
      setCursor(null);
      setPlaying(false);
      setSelected(null);
    }
  }, [status]);

  const frame = cursor == null ? frames[frames.length - 1] : frames[cursor];
  const upTo = cursor == null ? frames.length : cursor + 1;
  const [statusLabel, statusCls] = STATUS[status];
  const canExport = frames.length > 0 && status !== "connecting";

  const exportPayload = useMemo(() => ({ form, init, frames, summary }), [form, init, frames, summary]);

  return (
    <div className="mx-auto min-h-screen max-w-[1560px] px-4 pb-10 pt-5 sm:px-6">
      <header className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-3">
          <Hexagon className="text-gold" size={30} strokeWidth={1.4} aria-hidden="true" />
          <div>
            <h1 className="font-display text-[28px] font-semibold leading-none tracking-wide">
              Nexus<span className="text-gold">AI</span>
            </h1>
            <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-mute">Autonomous multi-agent simulation</p>
          </div>
        </div>

        <ul className="ml-auto flex flex-wrap items-center gap-3 text-[11px] text-mute" aria-label="Legend">
          {["cooperative", "competitive", "neutral"].map((p) => (
            <li key={p} className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: PERSONALITY[p].color }} />
              {PERSONALITY[p].label}
            </li>
          ))}
          <li>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusCls}`} role="status">{statusLabel}</span>
          </li>
        </ul>
      </header>

      {configError && (
        <div role="alert" className="panel mb-4 flex items-start gap-3 border-gold/30 p-3.5 text-[13px]">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-gold" aria-hidden="true" />
          <div>
            <b className="text-gold">Can&apos;t reach the backend at {BACKEND_URL}.</b>{" "}
            <span className="text-mute">
              Start it with <code className="text-soft">uvicorn main:app --reload --port 8000</code> in <code className="text-soft">backend/</code>.
              Free hosts such as Render sleep when idle and can take about a minute to wake: reload once it is up.
            </span>
          </div>
        </div>
      )}

      {error && status !== "idle" && summary == null && (
        <div role="alert" className="panel mb-4 border-comp/30 p-3.5 text-[13px] text-comp">{error}</div>
      )}
      {error && status === "idle" && (
        <div role="alert" className="panel mb-4 border-comp/30 p-3.5 text-[13px] text-comp">{error}</div>
      )}

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="panel order-2 p-4 lg:order-1 lg:self-start" aria-label="Simulation controls">
          <ControlPanel
            config={config} configError={configError} form={form} setForm={setForm} status={status}
            onStart={sim.start} onPause={sim.pause} onResume={sim.resume} onStep={sim.step}
            onStop={sim.stop} onInject={sim.inject} onSpeed={sim.setSpeed}
            onExportJson={() => exportJson(exportPayload)} onExportCsv={() => exportCsv(exportPayload)}
            canExport={canExport}
          />
        </aside>

        <main className="order-1 min-w-0 space-y-4 lg:order-2">
          <SimCanvas
            frame={frame} init={init} scenario={scenario} selected={selected} onSelect={setSelected}
            speedMs={form.speed_ms}
          />
          <ReplayBar frames={frames} cursor={cursor} setCursor={setCursor} playing={playing} setPlaying={setPlaying} />
          {status === "ended" && <RunSummary summary={summary} error={error} />}
          <StatsPanel frame={frame} frames={frames} upTo={upTo} scenario={scenario} maxTicks={init?.max_ticks ?? form.max_ticks} />
        </main>

        <div className="order-3 grid min-w-0 gap-4 lg:col-span-2 lg:grid-cols-2 xl:col-span-1 xl:grid-cols-1 xl:content-start">
          <CoalitionGraph frame={frame} selected={selected} onSelect={setSelected} />
          <AgentInspector agentId={selected} frame={frame} frames={frames} upTo={upTo} />
          <div className="lg:col-span-2 xl:col-span-1 xl:h-[420px]">
            <DialogueFeed feed={feed} onSelect={setSelected} />
          </div>
        </div>
      </div>

      <footer className="mt-8 text-center text-[11px] text-mute">
        Click any agent to inspect it · Drag the timeline to replay · Same seed, same run.
      </footer>
    </div>
  );
}
