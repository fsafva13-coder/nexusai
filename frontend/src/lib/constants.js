export const GRID = 12;

export const PERSONALITY = {
  cooperative: { label: "Cooperative", short: "COOP", color: "#8fd3b0" },
  competitive: { label: "Competitive", short: "COMP", color: "#ef7f95" },
  neutral: { label: "Neutral (tit-for-tat)", short: "NEUT", color: "#9db7f5" },
  mixed: { label: "Mixed", short: "MIX", color: "#d9b779" },
};

export const SCENARIOS = {
  disaster: {
    label: "Disaster Response",
    blurb: "Rescue survivors before the fire does. Heavy ones need two rescuers.",
    bg: "#150d12",
    verb: "rescue",
  },
  market: {
    label: "Market Trading",
    blurb: "Trade drifting assets. Crashing assets are traps.",
    bg: "#0c0f19",
    verb: "deal",
  },
  ecosystem: {
    label: "Ecosystem",
    blurb: "Forage for food. Predators hunt anyone who is alone.",
    bg: "#0a1411",
    verb: "forage",
  },
};

export const ASSET_STYLE = {
  gold: { color: "#e7c873", sym: "Au" },
  oil: { color: "#b794f4", sym: "Oil" },
  tech: { color: "#7cc4f2", sym: "Tc" },
  grain: { color: "#a7d78b", sym: "Gr" },
};

export const EVENT_STYLE = {
  help: { color: "#8fd3b0", icon: "♡" },
  trade: { color: "#d9b779", icon: "⇄" },
  steal: { color: "#ef7f95", icon: "✕" },
  death: { color: "#9a94a8", icon: "†" },
  coalition: { color: "#d9b779", icon: "◈" },
  world: { color: "#9db7f5", icon: "◌" },
  inject: { color: "#e8a0b4", icon: "⚡" },
};

export const SPEEDS = [
  { ms: 4000, label: "Slow" },
  { ms: 2500, label: "Normal" },
  { ms: 1200, label: "Fast" },
  { ms: 500, label: "Turbo" },
];

export const DEFAULT_FORM = {
  scenario: "disaster",
  num_agents: 6,
  preset: "balanced",
  use_llm: true,
  speed_ms: 1200,
  seed: "",
  max_ticks: 100,
};

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
