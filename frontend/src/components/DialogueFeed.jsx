import { useEffect, useRef, useState } from "react";
import { EVENT_STYLE, PERSONALITY } from "../lib/constants";

const SOURCE_BADGE = {
  llm: { label: "LLM", cls: "border-gold/50 text-gold" },
  rule: { label: "RULE", cls: "border-white/15 text-mute" },
  reflex: { label: "REFLEX", cls: "border-white/15 text-mute" },
};

const TABS = [
  ["all", "All"],
  ["say", "Speech"],
  ["event", "Events"],
];

export default function DialogueFeed({ feed, onSelect }) {
  const [tab, setTab] = useState("all");
  const scroller = useRef(null);
  const stick = useRef(true);

  const items = tab === "all" ? feed : feed.filter((i) => i.kind === tab);

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [items.length, tab]);

  const onScroll = () => {
    const el = scroller.current;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  };

  return (
    <section className="panel flex h-full min-h-[320px] flex-col overflow-hidden" aria-label="Agent dialogue and events">
      <header className="flex items-center gap-1 border-b border-white/[0.07] px-3 py-2">
        <h2 className="label mr-auto">Live feed</h2>
        {TABS.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            aria-pressed={tab === id}
            className={`rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
              tab === id ? "bg-gold/15 text-gold" : "text-mute hover:text-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </header>

      <div ref={scroller} onScroll={onScroll} className="flex-1 space-y-2 overflow-y-auto p-3" aria-live="polite">
        {items.length === 0 && (
          <p className="pt-8 text-center text-xs text-mute">Agent messages and world events will stream in here.</p>
        )}
        {items.map((it) =>
          it.kind === "say" ? (
            <button
              key={it.id}
              onClick={() => onSelect(it.agent)}
              className="fade-in block w-full rounded-xl border border-white/[0.06] bg-white/[0.03] p-2.5 text-left transition-colors hover:bg-white/[0.06]"
            >
              <div className="mb-1 flex items-center gap-1.5 text-[11px]">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: PERSONALITY[it.personality]?.color }} />
                <span className="font-semibold" style={{ color: PERSONALITY[it.personality]?.color }}>{it.agent}</span>
                <span className="text-mute">{PERSONALITY[it.personality]?.short}</span>
                {SOURCE_BADGE[it.source] && (
                  <span className={`rounded border px-1 text-[9px] font-semibold tracking-wider ${SOURCE_BADGE[it.source].cls}`}>
                    {SOURCE_BADGE[it.source].label}
                  </span>
                )}
                <span className="tnum ml-auto text-mute">T{it.tick}</span>
              </div>
              <p className="text-[13px] leading-snug text-soft">“{it.text}”</p>
              {(it.intent || it.reasoning) && (
                <p className="mt-1 text-[11px] italic leading-snug text-mute">
                  {it.intent && <span className="not-italic text-gold/80">{it.intent}{it.target ? ` → ${it.target}` : ""}</span>}
                  {it.reasoning && <span>{it.intent ? " · " : ""}{it.reasoning}</span>}
                </p>
              )}
            </button>
          ) : (
            <div key={it.id} className="fade-in flex items-start gap-2 px-1 text-[12px] leading-snug">
              <span className="mt-px w-4 shrink-0 text-center" style={{ color: EVENT_STYLE[it.type]?.color }} aria-hidden="true">
                {EVENT_STYLE[it.type]?.icon ?? "·"}
              </span>
              <span style={{ color: EVENT_STYLE[it.type]?.color }} className="opacity-90">{it.text}</span>
              <span className="tnum ml-auto shrink-0 text-[10px] text-mute">T{it.tick}</span>
            </div>
          ),
        )}
      </div>
    </section>
  );
}
