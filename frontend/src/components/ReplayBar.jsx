import { Pause, Play, Radio } from "lucide-react";

export default function ReplayBar({ frames, cursor, setCursor, playing, setPlaying }) {
  const n = frames.length;
  const live = cursor == null;
  const index = live ? n - 1 : cursor;

  const toggle = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (live || cursor >= n - 1) setCursor(0);
    setPlaying(true);
  };

  return (
    <div className="panel flex items-center gap-3 px-3 py-2.5" role="group" aria-label="Replay controls">
      <button
        onClick={toggle}
        disabled={n < 2}
        aria-label={playing ? "Pause replay" : "Replay from the start"}
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-soft transition-colors hover:bg-white/10 disabled:opacity-35"
      >
        {playing ? <Pause size={15} /> : <Play size={15} />}
      </button>

      <input
        type="range"
        min={0}
        max={Math.max(0, n - 1)}
        value={Math.max(0, index)}
        disabled={n < 2}
        onChange={(e) => {
          setPlaying(false);
          const v = Number(e.target.value);
          setCursor(v >= n - 1 ? null : v);
        }}
        aria-label="Scrub through simulation history"
        className="h-1 flex-1 cursor-pointer disabled:opacity-35"
      />

      <span className="tnum w-20 text-right text-[11px] text-mute">
        {n ? `T${frames[Math.max(0, index)].tick} / T${frames[n - 1].tick}` : "no data"}
      </span>

      <button
        onClick={() => {
          setPlaying(false);
          setCursor(null);
        }}
        disabled={n === 0 || live}
        className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold tracking-wide transition-colors ${
          live ? "bg-comp/15 text-comp" : "bg-white/[0.06] text-soft hover:bg-white/10"
        } disabled:cursor-default`}
      >
        <Radio size={12} className={live && n ? "pulse-dot" : ""} aria-hidden="true" />
        {live ? "LIVE" : "Go live"}
      </button>
    </div>
  );
}
