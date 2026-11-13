import { Cpu } from "lucide-react";
import { ASSET_STYLE, PERSONALITY } from "../lib/constants";
import MetricsChart from "./MetricsChart";

function Tile({ label, value, hint, tone }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2.5">
      <div className="label">{label}</div>
      <div className="tnum mt-0.5 text-xl font-semibold" style={{ color: tone || "#ece8f0" }}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[10.5px] text-mute">{hint}</div>}
    </div>
  );
}

function scenarioTiles(scenario, score) {
  if (!score) return [];
  if (scenario === "disaster")
    return [
      ["Rescued", score.rescued, "#8fd3b0"],
      ["Lost", score.lost, "#ef7f95"],
      ["Waiting", score.waiting],
    ];
  if (scenario === "market")
    return [
      ["Deals", score.deals],
      ["Net P&L", score.pnl, score.pnl >= 0 ? "#8fd3b0" : "#ef7f95"],
      ["Index", score.index],
    ];
  return [
    ["Eaten", score.eaten, "#8fd3b0"],
    ["Attacks", score.attacks, "#ef7f95"],
    ["Repelled", score.repelled, "#d9b779"],
  ];
}

export default function StatsPanel({ frame, frames, upTo, scenario, maxTicks }) {
  if (!frame) {
    return (
      <div className="panel p-5 text-sm text-mute">
        Metrics appear here once a simulation is running: welfare, inequality (Gini), cooperation index and
        average resources per strategy.
      </div>
    );
  }

  const m = frame.metrics;
  const shown = frames.slice(0, upTo);
  const ticks = shown.map((f) => f.tick);
  const bp = (p) => shown.map((f) => (f.metrics.by_personality?.[p] ?? null));
  const brain = frame.brain;
  const market = scenario === "market" ? frame.env?.assets : null;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile label="Tick" value={`${frame.tick}`} hint={`of ${maxTicks}`} />
        <Tile
          label="Alive"
          value={`${m.alive}/${m.total}`}
          tone={m.alive === m.total ? "#8fd3b0" : m.alive > 0 ? "#e9c46a" : "#ef7f95"}
        />
        <Tile label="Welfare" value={m.welfare} hint="total resources" />
        <Tile label="Gini" value={m.gini.toFixed(2)} hint="0 = equal" />
        <Tile label="Cooperation" value={`${Math.round(m.cooperation_index * 100)}%`} hint="help + trade vs theft" tone="#d9b779" />
        <Tile label="Helps" value={m.helps} tone="#8fd3b0" />
        <Tile label="Trades" value={m.trades} tone="#d9b779" />
        <Tile label="Thefts" value={m.steals} tone="#ef7f95" />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {scenarioTiles(scenario, frame.score).map(([label, value, tone]) => (
          <Tile key={label} label={label} value={value} tone={tone} />
        ))}
      </div>

      {market && (
        <div className="panel grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
          {Object.entries(market).map(([name, a]) => (
            <div key={name} className="text-xs">
              <div className="flex items-center gap-1.5 text-mute">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: ASSET_STYLE[name]?.color }} />
                {name}
              </div>
              <div className="tnum font-medium">
                {a.price.toFixed(1)}{" "}
                <span style={{ color: a.trend >= 0 ? "#8fd3b0" : "#ef7f95" }}>
                  {a.trend >= 0 ? "▲" : "▼"} {Math.abs(a.trend).toFixed(1)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="panel space-y-5 p-4">
        <MetricsChart
          title="Average resources by strategy"
          ticks={ticks}
          yMin={0}
          series={["cooperative", "competitive", "neutral"].map((p) => ({
            name: PERSONALITY[p].short, color: PERSONALITY[p].color, values: bp(p),
          }))}
        />
        <MetricsChart
          title="Cooperation vs inequality"
          ticks={ticks}
          yMin={0}
          yMax={1}
          fmt={(v) => (Math.round(v * 100) / 100).toFixed(2)}
          series={[
            { name: "Cooperation", color: "#d9b779", values: shown.map((f) => f.metrics.cooperation_index) },
            { name: "Gini", color: "#e8a0b4", values: shown.map((f) => f.metrics.gini) },
          ]}
        />
      </div>

      <div className="panel flex items-start gap-2.5 p-3 text-xs text-mute">
        <Cpu size={15} className="mt-0.5 shrink-0 text-gold" aria-hidden="true" />
        {brain.mode === "llm" ? (
          <div>
            <span className="font-medium text-soft">
              LLM planner · {brain.provider} · {brain.model}
            </span>
            <div className="mt-0.5">
              Re-plans every {brain.every} ticks with one batched call. {brain.llm_rounds} calls, {brain.llm_intents} LLM
              intents, {brain.invalid} rejected, {brain.skipped_rounds} skipped (rate budget), avg latency{" "}
              {brain.avg_latency_ms} ms.
              {brain.last_error && <span className="text-comp"> Last error: {brain.last_error}</span>}
            </div>
          </div>
        ) : (
          <div>
            <span className="font-medium text-soft">Rule-based agents</span>
            <div className="mt-0.5">Personality rules plus reflexes. Add a free API key on the server to switch on LLM planning.</div>
          </div>
        )}
      </div>
    </div>
  );
}
