import { Download, Flame, Leaf, Pause, Play, Square, StepForward, TrendingUp, Zap } from "lucide-react";
import { SCENARIOS, SPEEDS } from "../lib/constants";

const ICONS = { disaster: Flame, market: TrendingUp, ecosystem: Leaf };

function Seg({ options, value, onChange, disabled, label }) {
  return (
    <div className="flex gap-1 rounded-xl bg-white/[0.04] p-1" role="group" aria-label={label}>
      {options.map(([val, text]) => (
        <button
          key={String(val)}
          onClick={() => onChange(val)}
          disabled={disabled && value !== val ? true : false}
          aria-pressed={value === val}
          className={`flex-1 rounded-lg px-2 py-1.5 text-[11.5px] font-medium transition-colors ${
            value === val ? "bg-gold/20 text-gold" : "text-mute hover:text-soft"
          } disabled:opacity-40`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export default function ControlPanel({
  config, configError, form, setForm, status,
  onStart, onPause, onResume, onStep, onStop, onInject, onSpeed, onExportJson, onExportCsv, canExport,
}) {
  const active = status === "connecting" || status === "running" || status === "paused";
  const llm = config?.llm;
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const start = () =>
    onStart({
      scenario: form.scenario,
      num_agents: form.num_agents,
      preset: form.preset,
      use_llm: form.use_llm && !!llm?.available,
      speed_ms: form.speed_ms,
      max_ticks: form.max_ticks,
      seed: form.seed === "" ? null : Number(form.seed),
    });

  return (
    <div className="space-y-5">
      <fieldset disabled={active} className="space-y-4 border-0 p-0">
        <div>
          <div className="label mb-2">Scenario</div>
          <div className="space-y-1.5">
            {Object.entries(SCENARIOS).map(([id, s]) => {
              const Icon = ICONS[id];
              const on = form.scenario === id;
              return (
                <button
                  key={id}
                  onClick={() => set({ scenario: id })}
                  aria-pressed={on}
                  className={`flex w-full items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors disabled:opacity-50 ${
                    on ? "border-gold/50 bg-gold/10" : "border-white/[0.07] bg-white/[0.03] hover:border-white/20"
                  }`}
                >
                  <Icon size={16} className={`mt-0.5 shrink-0 ${on ? "text-gold" : "text-mute"}`} aria-hidden="true" />
                  <span>
                    <span className="block text-[13px] font-medium">{s.label}</span>
                    <span className="block text-[11px] leading-snug text-mute">{s.blurb}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label htmlFor="agents" className="label mb-2 flex justify-between">
            <span>Agents</span>
            <span className="tnum normal-case tracking-normal text-soft">{form.num_agents}</span>
          </label>
          <input
            id="agents" type="range" min={2} max={config?.limits?.max_agents ?? 8} value={form.num_agents}
            onChange={(e) => set({ num_agents: Number(e.target.value) })} className="w-full"
          />
        </div>

        <div>
          <label htmlFor="preset" className="label mb-2 block">Population</label>
          <select
            id="preset" value={form.preset} onChange={(e) => set({ preset: e.target.value })}
            className="w-full rounded-xl border border-white/10 bg-panel px-3 py-2 text-[13px] text-soft"
          >
            {(config?.presets ?? [{ id: "balanced", label: "Balanced mix" }]).map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <div className="label mb-2">Agent brain</div>
          <Seg
            label="Agent brain" value={form.use_llm && !!llm?.available}
            onChange={(v) => set({ use_llm: v })}
            options={[[true, "LLM planner"], [false, "Rule-based"]]}
          />
          <p className="mt-1.5 text-[11px] leading-snug text-mute">
            {configError
              ? "Backend unreachable."
              : llm?.available
                ? `${llm.provider} · ${llm.model}`
                : llm?.note || "No API key on the server: agents run on rules."}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="ticks" className="label mb-2 block">Length</label>
            <select
              id="ticks" value={form.max_ticks} onChange={(e) => set({ max_ticks: Number(e.target.value) })}
              className="w-full rounded-xl border border-white/10 bg-panel px-3 py-2 text-[13px] text-soft"
            >
              {[50, 100, 150, 200].filter((t) => t <= (config?.limits?.max_ticks ?? 300)).map((t) => (
                <option key={t} value={t}>{t} ticks</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="seed" className="label mb-2 block">Seed</label>
            <input
              id="seed" inputMode="numeric" placeholder="random" value={form.seed}
              onChange={(e) => set({ seed: e.target.value.replace(/\D/g, "").slice(0, 9) })}
              className="w-full rounded-xl border border-white/10 bg-panel px-3 py-2 text-[13px] text-soft placeholder:text-mute"
            />
          </div>
        </div>
      </fieldset>

      <div>
        <div className="label mb-2">Speed</div>
        <Seg
          label="Simulation speed" value={form.speed_ms}
          onChange={(ms) => { set({ speed_ms: ms }); if (active) onSpeed(ms); }}
          options={SPEEDS.map((s) => [s.ms, s.label])}
        />
      </div>

      {!active ? (
        <button
          onClick={start}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-gold to-rose px-4 py-3 text-sm font-semibold text-ink transition-opacity hover:opacity-90"
        >
          <Play size={16} aria-hidden="true" /> Start simulation
        </button>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2">
            {status === "paused" ? (
              <button onClick={onResume} className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-gold/20 px-3 py-2.5 text-[13px] font-semibold text-gold hover:bg-gold/30">
                <Play size={14} aria-hidden="true" /> Resume
              </button>
            ) : (
              <button onClick={onPause} disabled={status !== "running"} className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-white/[0.07] px-3 py-2.5 text-[13px] font-semibold hover:bg-white/10 disabled:opacity-40">
                <Pause size={14} aria-hidden="true" /> Pause
              </button>
            )}
            <button onClick={onStep} disabled={status !== "paused"} aria-label="Advance one tick" className="flex items-center justify-center gap-1.5 rounded-xl bg-white/[0.07] px-3 py-2.5 text-[13px] font-semibold hover:bg-white/10 disabled:opacity-40">
              <StepForward size={14} aria-hidden="true" /> Step
            </button>
            <button onClick={onStop} aria-label="Stop simulation" className="flex items-center justify-center rounded-xl border border-comp/40 bg-comp/10 px-3 py-2.5 text-comp hover:bg-comp/20">
              <Square size={14} aria-hidden="true" />
            </button>
          </div>

          <div>
            <div className="label mb-2 mt-3 flex items-center gap-1.5"><Zap size={11} aria-hidden="true" /> Intervene</div>
            <div className="grid gap-1.5">
              {[
                ["drain", "Resource drain (−20 each)", "text-comp"],
                ["boost", "Supply drop (+30 each)", "text-coop"],
                ["crisis", SCENARIOS[form.scenario] && (config?.scenarios?.[form.scenario]?.crisis ?? "Trigger crisis"), "text-gold"],
              ].map(([type, text, tone]) => (
                <button
                  key={type} onClick={() => onInject(type)}
                  className={`rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-left text-[12px] font-medium transition-colors hover:bg-white/[0.07] ${tone}`}
                >
                  {text}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[10.5px] leading-snug text-mute">Agents re-plan immediately after an intervention.</p>
          </div>
        </div>
      )}

      {canExport && (
        <div>
          <div className="label mb-2 flex items-center gap-1.5"><Download size={11} aria-hidden="true" /> Export run</div>
          <div className="flex gap-2">
            <button onClick={onExportJson} className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[12px] font-medium hover:bg-white/[0.07]">JSON (full replay)</button>
            <button onClick={onExportCsv} className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[12px] font-medium hover:bg-white/[0.07]">CSV (metrics)</button>
          </div>
        </div>
      )}
    </div>
  );
}
