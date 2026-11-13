import { useState } from "react";

const W = 320;
const PAD = { l: 34, r: 8, t: 8, b: 20 };

function segments(values, x, y) {
  const out = [];
  let current = [];
  values.forEach((v, i) => {
    if (v == null) {
      if (current.length) out.push(current);
      current = [];
    } else {
      current.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    }
  });
  if (current.length) out.push(current);
  return out;
}

/**
 * Small, dependency-free line chart.
 * series: [{ name, color, values: (number|null)[] }]   ticks: number[] (x labels)
 */
export default function MetricsChart({ title, series, ticks, height = 150, yMin, yMax, fmt = (v) => v }) {
  const [hover, setHover] = useState(null);
  const n = ticks.length;
  const all = series.flatMap((s) => s.values).filter((v) => v != null);
  let lo = yMin ?? Math.min(0, ...(all.length ? all : [0]));
  let hi = yMax ?? Math.max(1, ...(all.length ? all : [1]));
  if (hi === lo) hi = lo + 1;

  const x = (i) => PAD.l + (n <= 1 ? 0 : i / (n - 1)) * (W - PAD.l - PAD.r);
  const y = (v) => PAD.t + (1 - (v - lo) / (hi - lo)) * (height - PAD.t - PAD.b);
  const idx = hover == null ? n - 1 : hover;

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  const levels = [0, 0.5, 1].map((f) => lo + (hi - lo) * f);

  return (
    <figure className="m-0">
      <figcaption className="label mb-1.5 flex items-center justify-between">
        <span>{title}</span>
        {n > 0 && <span className="tnum normal-case tracking-normal text-mute">tick {ticks[idx]}</span>}
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        className="w-full"
        role="img"
        aria-label={`${title} over time`}
        onMouseMove={n > 1 ? onMove : undefined}
        onMouseLeave={() => setHover(null)}
      >
        {levels.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="rgba(255,255,255,0.07)" />
            <text x={PAD.l - 5} y={y(v) + 3} textAnchor="end" fontSize="9" fill="#9a94a8">
              {fmt(Math.round(v * 100) / 100)}
            </text>
          </g>
        ))}
        {n > 0 && (
          <>
            <text x={PAD.l} y={height - 5} fontSize="9" fill="#9a94a8">{ticks[0]}</text>
            <text x={W - PAD.r} y={height - 5} fontSize="9" fill="#9a94a8" textAnchor="end">{ticks[n - 1]}</text>
          </>
        )}
        {series.map((s) =>
          segments(s.values, x, y).map((pts, k) => (
            <polyline
              key={`${s.name}-${k}`}
              points={pts.join(" ")}
              fill="none"
              stroke={s.color}
              strokeWidth="1.8"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )),
        )}
        {n > 0 && hover != null && (
          <line x1={x(idx)} x2={x(idx)} y1={PAD.t} y2={height - PAD.b} stroke="rgba(217,183,121,0.5)" strokeDasharray="3 3" />
        )}
        {n > 0 &&
          series.map((s) =>
            s.values[idx] != null ? <circle key={s.name} cx={x(idx)} cy={y(s.values[idx])} r="3" fill={s.color} /> : null,
          )}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-1.5 text-mute">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
            {s.name}
            <span className="tnum font-medium text-soft">{s.values[idx] == null ? "–" : fmt(s.values[idx])}</span>
          </span>
        ))}
      </div>
    </figure>
  );
}
