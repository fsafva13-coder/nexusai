import { useEffect, useRef, useState } from "react";
import { ASSET_STYLE, GRID, PERSONALITY, SCENARIOS } from "../lib/constants";

const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function hexagon(ctx, cx, cy, r) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 3) * i - Math.PI / 6;
    const x = cx + r * Math.cos(a);
    const y = cy + r * Math.sin(a);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

const center = (cell, gx, gy) => [(gx + 0.5) * cell, (gy + 0.5) * cell];

/* ---------------------------------------------------------------- scenario layers */
function drawDisaster(ctx, env, cell, now) {
  (env.fires || []).forEach((f, i) => {
    const [cx, cy] = center(cell, f.x, f.y);
    const half = (f.radius + 0.5) * cell;
    const flicker = 0.5 + 0.12 * Math.sin(now / 170 + i * 2);
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, half * 1.35);
    g.addColorStop(0, `rgba(255,140,60,${flicker + 0.15})`);
    g.addColorStop(0.7, `rgba(240,80,50,${flicker * 0.45})`);
    g.addColorStop(1, "rgba(240,80,50,0)");
    ctx.fillStyle = g;
    roundRect(ctx, cx - half, cy - half, half * 2, half * 2, cell * 0.4);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,150,90,0.35)";
    ctx.setLineDash([4, 5]);
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
  });

  (env.survivors || []).forEach((s) => {
    const [cx, cy] = center(cell, s.x, s.y);
    const r = cell * 0.24;
    if (s.status === "waiting") {
      const pulse = 1 + 0.12 * Math.sin(now / 260 + s.x);
      ctx.fillStyle = "rgba(244,207,122,0.16)";
      ctx.beginPath();
      ctx.arc(cx, cy, r * 1.9 * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#f4cf7a";
      ctx.beginPath();
      ctx.moveTo(cx, cy - r);
      ctx.lineTo(cx + r, cy);
      ctx.lineTo(cx, cy + r);
      ctx.lineTo(cx - r, cy);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#0b0a10";
      const pips = s.needs;
      for (let p = 0; p < pips; p++) {
        ctx.beginPath();
        ctx.arc(cx + (p - (pips - 1) / 2) * r * 0.55, cy, r * 0.16, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.globalAlpha = 0.55;
      ctx.strokeStyle = s.status === "rescued" ? "#8fd3b0" : "#9a94a8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      if (s.status === "rescued") {
        ctx.moveTo(cx - r * 0.7, cy);
        ctx.lineTo(cx - r * 0.1, cy + r * 0.6);
        ctx.lineTo(cx + r * 0.8, cy - r * 0.6);
      } else {
        ctx.moveTo(cx - r * 0.6, cy - r * 0.6);
        ctx.lineTo(cx + r * 0.6, cy + r * 0.6);
        ctx.moveTo(cx + r * 0.6, cy - r * 0.6);
        ctx.lineTo(cx - r * 0.6, cy + r * 0.6);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  });
}

function drawMarket(ctx, env, cell) {
  (env.deals || []).forEach((d) => {
    const style = ASSET_STYLE[d.asset] || { color: "#bbb", sym: "?" };
    const [cx, cy] = center(cell, d.x, d.y);
    const r = cell * 0.36;
    ctx.fillStyle = style.color + "26";
    hexagon(ctx, cx, cy, r);
    ctx.fill();
    ctx.strokeStyle = style.color;
    ctx.lineWidth = 1.3;
    ctx.stroke();
    ctx.fillStyle = style.color;
    ctx.font = `600 ${cell * 0.24}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(style.sym, cx, cy - cell * 0.03);
    ctx.fillStyle = d.est >= 0 ? "#8fd3b0" : "#ef7f95";
    ctx.font = `600 ${cell * 0.2}px Inter, sans-serif`;
    ctx.fillText(`${d.est >= 0 ? "+" : ""}${d.est}`, cx, cy + r + cell * 0.14);
  });
}

function drawEcosystem(ctx, env, cell, now) {
  (env.food || []).forEach((f) => {
    const [cx, cy] = center(cell, f.x, f.y);
    const r = cell * (0.12 + Math.min(f.value, 30) / 300);
    ctx.fillStyle = "rgba(143,211,176,0.18)";
    ctx.beginPath();
    ctx.arc(cx, cy, r * 2.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#a7d78b";
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  });
  (env.predators || []).forEach((p, i) => {
    const [cx, cy] = center(cell, p.x, p.y);
    const r = cell * 0.3;
    ctx.strokeStyle = "rgba(239,127,149,0.4)";
    ctx.setLineDash([3, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, cell * 1.05 + Math.sin(now / 300 + i) * 2, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#e0456a";
    ctx.beginPath();
    ctx.moveTo(cx, cy - r);
    ctx.lineTo(cx + r * 0.95, cy + r * 0.8);
    ctx.lineTo(cx - r * 0.95, cy + r * 0.8);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(cx - r * 0.28, cy + r * 0.12, r * 0.1, 0, Math.PI * 2);
    ctx.arc(cx + r * 0.28, cy + r * 0.12, r * 0.1, 0, Math.PI * 2);
    ctx.fill();
  });
}

/* ---------------------------------------------------------------- interactions */
function arrow(ctx, x1, y1, x2, y2, head) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  const a = Math.atan2(y2 - y1, x2 - x1);
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - head * Math.cos(a - 0.45), y2 - head * Math.sin(a - 0.45));
  ctx.lineTo(x2 - head * Math.cos(a + 0.45), y2 - head * Math.sin(a + 0.45));
  ctx.closePath();
  ctx.fill();
}

function drawInteractions(ctx, list, shown, cell) {
  (list || []).forEach((it) => {
    const a = shown[it.from];
    const b = shown[it.to];
    if (!a || !b) return;
    const [x1, y1] = center(cell, a[0], a[1]);
    const [x2, y2] = center(cell, b[0], b[1]);
    ctx.lineWidth = 2;
    if (it.type === "help") {
      ctx.strokeStyle = ctx.fillStyle = "rgba(143,211,176,0.9)";
      ctx.setLineDash([5, 4]);
      arrow(ctx, x1, y1, x2, y2, cell * 0.22);
    } else if (it.type === "trade") {
      ctx.strokeStyle = "rgba(217,183,121,0.95)";
      ctx.setLineDash([]);
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    } else if (it.type === "steal") {
      ctx.strokeStyle = ctx.fillStyle = "rgba(239,127,149,0.95)";
      ctx.setLineDash([]);
      arrow(ctx, x1, y1, x2, y2, cell * 0.26);
    } else {
      ctx.strokeStyle = "rgba(217,183,121,0.35)";
      ctx.setLineDash([2, 5]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  });
}

/* ---------------------------------------------------------------- agents */
function resourceColor(frac) {
  if (frac > 0.5) return "#8fd3b0";
  if (frac > 0.25) return "#e9c46a";
  return "#ef7f95";
}

function drawAgents(ctx, agents, shown, cell, selected, now) {
  agents.forEach((ag) => {
    const p = shown[ag.id] || [ag.x, ag.y];
    const [cx, cy] = center(cell, p[0], p[1]);
    const color = PERSONALITY[ag.personality]?.color || "#ddd";
    const r = cell * 0.31;

    if (ag.alive === false) {
      ctx.globalAlpha = 0.3;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.8, 0, Math.PI * 2);
      ctx.moveTo(cx - r * 0.4, cy - r * 0.4);
      ctx.lineTo(cx + r * 0.4, cy + r * 0.4);
      ctx.moveTo(cx + r * 0.4, cy - r * 0.4);
      ctx.lineTo(cx - r * 0.4, cy + r * 0.4);
      ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }

    const glow = ctx.createRadialGradient(cx, cy, r * 0.4, cx, cy, r * 2.3);
    glow.addColorStop(0, color + "55");
    glow.addColorStop(1, color + "00");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 2.3, 0, Math.PI * 2);
    ctx.fill();

    // resource ring
    const frac = Math.max(0, Math.min(1, ag.resources / 150));
    ctx.lineWidth = Math.max(2, cell * 0.07);
    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    ctx.beginPath();
    ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = resourceColor(frac);
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.arc(cx, cy, r + 4, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * frac);
    ctx.stroke();
    ctx.lineCap = "butt";

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#0b0a10";
    ctx.font = `700 ${cell * 0.25}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(ag.id, cx, cy + 0.5);

    if (ag.id === selected) {
      ctx.strokeStyle = "#d9b779";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.arc(cx, cy, r + 9 + Math.sin(now / 250) * 1.2, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (ag.message) {
      ctx.fillStyle = "#ece8f0";
      ctx.beginPath();
      ctx.arc(cx + r * 0.95, cy - r * 1.15, cell * 0.075, 0, Math.PI * 2);
      ctx.arc(cx + r * 1.3, cy - r * 1.15, cell * 0.075, 0, Math.PI * 2);
      ctx.arc(cx + r * 1.65, cy - r * 1.15, cell * 0.075, 0, Math.PI * 2);
      ctx.fill();
    }

    if (ag.delta && Math.abs(ag.delta) >= 5) {
      ctx.font = `600 ${cell * 0.22}px Inter, sans-serif`;
      ctx.fillStyle = ag.delta > 0 ? "#8fd3b0" : "#ef7f95";
      ctx.fillText(`${ag.delta > 0 ? "+" : ""}${ag.delta}`, cx, cy - r - 10);
    }
  });
}

/* ---------------------------------------------------------------- frame */
function drawFrame(ctx, S, now) {
  const { size, frame, init, scenario, selected, shown } = S;
  const cell = size / GRID;
  ctx.clearRect(0, 0, size, size);
  ctx.fillStyle = SCENARIOS[scenario]?.bg || "#12101a";
  ctx.fillRect(0, 0, size, size);

  ctx.strokeStyle = "rgba(255,255,255,0.045)";
  ctx.lineWidth = 1;
  for (let i = 1; i < GRID; i++) {
    ctx.beginPath();
    ctx.moveTo(i * cell, 0);
    ctx.lineTo(i * cell, size);
    ctx.moveTo(0, i * cell);
    ctx.lineTo(size, i * cell);
    ctx.stroke();
  }

  const env = frame?.env || {};
  if (scenario === "disaster") drawDisaster(ctx, env, cell, now);
  else if (scenario === "market") drawMarket(ctx, env, cell);
  else drawEcosystem(ctx, env, cell, now);

  drawInteractions(ctx, frame?.interactions, shown, cell);
  drawAgents(ctx, frame?.agents || init?.agents || [], shown, cell, selected, now);

  if (!frame && !init) {
    ctx.fillStyle = "rgba(236,232,240,0.55)";
    ctx.font = `500 ${cell * 0.34}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Choose a scenario and press Start", size / 2, size / 2);
  }
}

export default function SimCanvas({ frame, init, scenario, selected, onSelect, speedMs }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const [size, setSize] = useState(560);
  const anim = useRef({ from: {}, to: {}, shown: {}, start: 0, dur: 0 });
  const live = useRef({});
  live.current = { size, frame, init, scenario, selected };

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => {
      setSize(Math.max(260, Math.min(680, Math.floor(entry.contentRect.width))));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // retarget the interpolation whenever a new frame arrives
  useEffect(() => {
    const a = anim.current;
    const agents = frame?.agents || init?.agents || [];
    const to = {};
    agents.forEach((ag) => {
      to[ag.id] = [ag.x, ag.y];
    });
    a.from = { ...a.shown };
    Object.keys(to).forEach((id) => {
      if (!a.from[id]) a.from[id] = to[id];
    });
    a.to = to;
    a.start = performance.now();
    a.dur = Math.min(520, Math.max(120, (speedMs || 1000) * 0.55));
  }, [frame, init, speedMs]);

  useEffect(() => {
    let raf;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const loop = (now) => {
      const S = live.current;
      const a = anim.current;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== S.size * dpr) {
        canvas.width = S.size * dpr;
        canvas.height = S.size * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const t = reduce || !a.dur ? 1 : ease(Math.min(1, (now - a.start) / a.dur));
      Object.keys(a.to).forEach((id) => {
        const f = a.from[id] || a.to[id];
        a.shown[id] = [lerp(f[0], a.to[id][0], t), lerp(f[1], a.to[id][1], t)];
      });
      drawFrame(ctx, { ...S, shown: a.shown }, now);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const handleClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const cell = rect.width / GRID;
    const px = (e.clientX - rect.left) / cell - 0.5;
    const py = (e.clientY - rect.top) / cell - 0.5;
    let best = null;
    let bestD = 0.75;
    const shown = anim.current.shown;
    (frame?.agents || init?.agents || []).forEach((ag) => {
      const p = shown[ag.id] || [ag.x, ag.y];
      const d = Math.hypot(p[0] - px, p[1] - py);
      if (d < bestD) {
        best = ag.id;
        bestD = d;
      }
    });
    onSelect(best === selected ? null : best);
  };

  const alive = frame ? frame.metrics.alive : init ? init.agents.length : 0;
  return (
    <div ref={wrapRef} className="w-full">
      <div className="panel mx-auto overflow-hidden" style={{ width: size, background: SCENARIOS[scenario]?.bg }}>
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          role="img"
          aria-label={`Simulation grid${frame ? `, tick ${frame.tick}` : ""}, ${alive} agents alive. Click an agent to inspect it.`}
          style={{ width: size, height: size, display: "block", cursor: "pointer" }}
        />
      </div>
    </div>
  );
}
