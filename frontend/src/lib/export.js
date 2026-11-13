function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const stem = (init) => `nexusai-${init?.scenario ?? "run"}-seed${init?.seed ?? "x"}`;

export function exportJson({ form, init, frames, summary }) {
  const body = { exported_at: new Date().toISOString(), config: form, init, summary, frames };
  download(`${stem(init)}.json`, JSON.stringify(body), "application/json");
}

export function exportCsv({ init, frames }) {
  const head = [
    "tick", "alive", "welfare", "avg_resources", "gini", "cooperation_index",
    "helps", "trades", "steals", "avg_cooperative", "avg_competitive", "avg_neutral",
  ];
  const rows = frames.map((f) => {
    const m = f.metrics;
    const bp = m.by_personality || {};
    return [
      f.tick, m.alive, m.welfare, m.avg_resources, m.gini, m.cooperation_index,
      m.helps, m.trades, m.steals, bp.cooperative ?? "", bp.competitive ?? "", bp.neutral ?? "",
    ].join(",");
  });
  download(`${stem(init)}.csv`, [head.join(","), ...rows].join("\n"), "text/csv");
}
