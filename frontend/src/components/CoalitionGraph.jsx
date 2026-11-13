import { PERSONALITY } from "../lib/constants";

const W = 300;
const H = 250;

export default function CoalitionGraph({ frame, onSelect, selected }) {
  const agents = frame?.agents ?? [];
  const co = frame?.coalitions ?? { groups: [], edges: [] };

  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 34;
  const pos = {};
  agents.forEach((a, i) => {
    const ang = (i / Math.max(1, agents.length)) * Math.PI * 2 - Math.PI / 2;
    pos[a.id] = { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang), a };
  });

  return (
    <section className="panel overflow-hidden" aria-label="Coalition graph">
      <header className="flex items-center border-b border-white/[0.07] px-3 py-2">
        <h2 className="label mr-auto">Emergent coalitions</h2>
        <span className="tnum text-[11px] text-mute">{co.groups.length} active</span>
      </header>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Alliance and rivalry network between agents">
        {co.groups.map((g) => {
          const pts = g.members.map((m) => pos[m]).filter(Boolean);
          if (!pts.length) return null;
          const gx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
          const gy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
          const r = Math.max(...pts.map((p) => Math.hypot(p.x - gx, p.y - gy))) + 26;
          return <circle key={g.id} cx={gx} cy={gy} r={r} fill={g.color} fillOpacity="0.08" stroke={g.color} strokeOpacity="0.35" strokeDasharray="4 4" />;
        })}

        {co.edges.map((e) => {
          const a = pos[e.a];
          const b = pos[e.b];
          if (!a || !b) return null;
          const rival = e.kind === "rivalry";
          return (
            <line
              key={`${e.kind}-${e.a}-${e.b}`}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={rival ? "#ef7f95" : "#d9b779"}
              strokeOpacity={Math.min(0.9, 0.3 + e.w * 0.18)}
              strokeWidth={Math.min(5, 1 + e.w * 0.8)}
              strokeDasharray={rival ? "5 4" : undefined}
              strokeLinecap="round"
            />
          );
        })}

        {Object.values(pos).map(({ x, y, a }) => {
          const color = PERSONALITY[a.personality]?.color;
          const r = 10 + Math.min(10, (a.resources / 150) * 12);
          return (
            <g
              key={a.id}
              onClick={() => onSelect(a.id === selected ? null : a.id)}
              style={{ cursor: "pointer" }}
              opacity={a.alive ? 1 : 0.28}
              role="button"
              aria-label={`${a.id}, ${a.personality}, ${a.resources} resources`}
            >
              <circle cx={x} cy={y} r={r + 6} fill={color} fillOpacity="0.12" />
              <circle cx={x} cy={y} r={r} fill={color} stroke={a.id === selected ? "#d9b779" : "none"} strokeWidth="2" />
              <text x={x} y={y + 3.5} textAnchor="middle" fontSize="10" fontWeight="700" fill="#0b0a10">{a.id}</text>
            </g>
          );
        })}
        {agents.length === 0 && (
          <text x={cx} y={cy} textAnchor="middle" fontSize="11" fill="#9a94a8">Waiting for agents…</text>
        )}
      </svg>

      <div className="space-y-1.5 border-t border-white/[0.07] px-3 py-2.5">
        {co.groups.length === 0 ? (
          <p className="text-[11px] text-mute">
            No alliances yet. Coalitions form when agents repeatedly help or trade with each other, and fade when they stop.
          </p>
        ) : (
          co.groups.map((g) => (
            <div key={g.id} className="flex items-center gap-2 text-[12px]">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: g.color }} />
              <span className="font-medium">{g.members.join(" + ")}</span>
              <span className="text-mute">{PERSONALITY[g.dominant_personality]?.label ?? g.dominant_personality}</span>
              <span className="tnum ml-auto text-[10.5px] text-mute">since T{g.since} · cohesion {g.cohesion}</span>
            </div>
          ))
        )}
        <div className="flex gap-3 pt-1 text-[10.5px] text-mute">
          <span><span className="mr-1 inline-block h-0.5 w-4 align-middle" style={{ background: "#d9b779" }} />alliance</span>
          <span><span className="mr-1 inline-block h-0.5 w-4 align-middle border-t border-dashed" style={{ borderColor: "#ef7f95" }} />rivalry</span>
        </div>
      </div>
    </section>
  );
}
