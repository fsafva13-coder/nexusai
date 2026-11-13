import { PERSONALITY } from "../lib/constants";

function insight(s) {
  const bp = s.by_personality || {};
  const ranked = Object.entries(bp).sort((a, b) => b[1] - a[1]);
  if (ranked.length < 2) {
    return `${s.survivors} of ${s.total_agents} agents survived with ${s.welfare} resources in total.`;
  }
  const [top, topVal] = ranked[0];
  const [low, lowVal] = ranked[ranked.length - 1];
  const stolen = s.steals > s.helps + s.trades;
  return (
    `${PERSONALITY[top].label} agents ended richest (${topVal} average) and ${PERSONALITY[low].label.toLowerCase()} agents poorest (${lowVal}). ` +
    (stolen
      ? "Theft outweighed cooperation, which shrinks the total pie."
      : "Cooperation outweighed theft, which grows the total pie.")
  );
}

export default function RunSummary({ summary, error }) {
  if (!summary && !error) return null;
  if (!summary) {
    return (
      <div role="alert" className="panel border-comp/30 p-4 text-sm text-comp">{error}</div>
    );
  }
  const maxVal = Math.max(1, ...Object.values(summary.by_personality));
  const reasons = { max_ticks: "Time limit reached", extinction: "Every agent died", stopped: "Stopped by you" };

  return (
    <section className="panel fade-in space-y-3 p-4" aria-label="Run summary">
      <header className="flex items-baseline gap-2">
        <h2 className="font-display text-2xl font-semibold text-gold">Run complete</h2>
        <span className="text-xs text-mute">{reasons[summary.reason] ?? summary.reason} · seed {summary.seed}</span>
      </header>
      <p className="text-[13px] leading-relaxed text-soft/90">{insight(summary)}</p>

      <div className="space-y-1.5">
        {Object.entries(summary.by_personality).map(([p, v]) => (
          <div key={p} className="flex items-center gap-2 text-[12px]">
            <span className="w-28 text-mute">{PERSONALITY[p].label.split(" ")[0]}</span>
            <div className="h-2 flex-1 rounded-full bg-white/10">
              <div className="h-2 rounded-full" style={{ width: `${(v / maxVal) * 100}%`, background: PERSONALITY[p].color }} />
            </div>
            <span className="tnum w-10 text-right">{v}</span>
          </div>
        ))}
        <p className="text-[10.5px] text-mute">Average final resources per strategy (the dead count as zero).</p>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        {[
          ["Survivors", `${summary.survivors}/${summary.total_agents}`],
          ["Welfare", summary.welfare],
          ["Gini", summary.gini.toFixed(2)],
          ["Coalitions", summary.coalitions_formed],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl bg-white/[0.04] px-2 py-2">
            <dd className="tnum text-lg font-semibold">{v}</dd>
            <dt className="label">{k}</dt>
          </div>
        ))}
      </dl>
    </section>
  );
}
