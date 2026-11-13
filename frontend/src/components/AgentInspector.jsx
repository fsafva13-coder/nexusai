import { PERSONALITY } from "../lib/constants";

function Spark({ values, color }) {
  const pts = values.filter((v) => v != null);
  if (pts.length < 2) return null;
  const hi = Math.max(...pts, 1);
  const w = 160;
  const h = 34;
  const d = pts.map((v, i) => `${((i / (pts.length - 1)) * w).toFixed(1)},${(h - (v / hi) * (h - 4) - 2).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-full" role="img" aria-label="Resource history">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg bg-white/[0.04] px-2 py-1.5 text-center">
      <div className="tnum text-sm font-semibold">{value}</div>
      <div className="text-[9.5px] uppercase tracking-wider text-mute">{label}</div>
    </div>
  );
}

export default function AgentInspector({ agentId, frame, frames, upTo }) {
  const agent = frame?.agents.find((a) => a.id === agentId);
  if (!agent) {
    return (
      <section className="panel p-4 text-xs text-mute" aria-label="Agent inspector">
        <h2 className="label mb-1.5">Agent inspector</h2>
        Click an agent on the grid, in the graph or in the feed to see its intent, trust ledger and memory.
      </section>
    );
  }

  const p = PERSONALITY[agent.personality];
  const history = frames.slice(0, upTo).map((f) => f.agents.find((a) => a.id === agentId)?.resources ?? null);
  const s = agent.stats;
  const trust = Object.entries(agent.trust || {});

  return (
    <section className="panel space-y-3 p-4" aria-label="Agent inspector">
      <header className="flex items-center gap-2">
        <span className="inline-block h-3 w-3 rounded-full" style={{ background: p.color }} />
        <h2 className="text-base font-semibold">{agent.id}</h2>
        <span className="text-xs" style={{ color: p.color }}>{p.label}</span>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold ${agent.alive ? "bg-coop/15 text-coop" : "bg-white/10 text-mute"}`}>
          {agent.alive ? "ALIVE" : "DEAD"}
        </span>
      </header>

      <div>
        <div className="mb-1 flex items-baseline justify-between text-xs">
          <span className="text-mute">Resources</span>
          <span className="tnum font-semibold">{agent.resources}</span>
        </div>
        <Spark values={history} color={p.color} />
      </div>

      <dl className="space-y-1 text-[12px]">
        <div className="flex gap-2">
          <dt className="w-14 shrink-0 text-mute">Intent</dt>
          <dd>
            {agent.intent ? (
              <>
                <span className="text-gold">{agent.intent}</span>
                {agent.intent_target ? ` → ${agent.intent_target}` : ""}
                <span className="ml-1.5 text-[10px] uppercase text-mute">{agent.intent_source}</span>
              </>
            ) : "–"}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-14 shrink-0 text-mute">Action</dt>
          <dd>{agent.action}{agent.target ? ` → ${agent.target}` : ""}</dd>
        </div>
        {agent.effect && (
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-mute">Result</dt>
            <dd className="text-soft">{agent.effect}</dd>
          </div>
        )}
      </dl>

      <div className="grid grid-cols-3 gap-1.5">
        <Stat label="gathered" value={s.gathered} />
        <Stat label="helped" value={s.helps_given} />
        <Stat label="helped by" value={s.helps_received} />
        <Stat label="trades" value={s.trades} />
        <Stat label="stole" value={s.steals_done} />
        <Stat label="robbed" value={s.steals_suffered} />
      </div>

      <div>
        <div className="label mb-1.5">Trust ledger</div>
        {trust.length === 0 ? (
          <p className="text-[11px] text-mute">No strong feelings about anyone yet.</p>
        ) : (
          <ul className="space-y-1">
            {trust.map(([id, v]) => (
              <li key={id} className="flex items-center gap-2 text-[11px]">
                <span className="w-7 font-medium">{id}</span>
                <div className="relative h-1.5 flex-1 rounded-full bg-white/10">
                  <div className="absolute left-1/2 top-0 h-full w-px bg-white/30" />
                  <div
                    className="absolute top-0 h-full rounded-full"
                    style={{
                      background: v >= 0 ? "#8fd3b0" : "#ef7f95",
                      left: v >= 0 ? "50%" : `${50 + v * 50}%`,
                      width: `${Math.abs(v) * 50}%`,
                    }}
                  />
                </div>
                <span className="tnum w-9 text-right text-mute">{v.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {agent.memory?.length > 0 && (
        <div>
          <div className="label mb-1.5">Short-term memory</div>
          <ul className="space-y-0.5 text-[11px] text-mute">
            {agent.memory.slice().reverse().map((m, i) => <li key={i} className="truncate" title={m}>{m}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}
