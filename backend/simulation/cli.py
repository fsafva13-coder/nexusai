"""Command-line runner.

    python -m simulation.cli run     --scenario disaster --agents 6 --ticks 80 --seed 1
    python -m simulation.cli compare --scenario ecosystem --seeds 10
"""
from __future__ import annotations

import argparse
import asyncio
import json

from .constants import PRESETS, SCENARIOS
from .experiments import compare_presets, run_once


def _table(results: dict) -> str:
    header = (f"{'composition':<30}{'alive':>6}{'welfare':>8}{'gini':>6}{'coop':>6}{'helps':>6}"
              f"{'trades':>7}{'steals':>7}{'coal.':>6}   avg resources (coop / comp / neut)")
    lines = [header, "-" * len(header)]
    for name, r in results.items():
        bp = r["by_personality"]
        cells = " / ".join(f"{bp[p]:>4.0f}" if p in bp else "   -" for p in ("cooperative", "competitive", "neutral"))
        lines.append(
            f"{PRESETS[name]['label']:<30}{r['survivors']:>6.1f}{r['welfare']:>8.0f}"
            f"{r['gini']:>6.2f}{r['cooperation_index']:>6.2f}{r['helps']:>6.1f}"
            f"{r['trades']:>7.1f}{r['steals']:>7.1f}{r['coalitions_formed']:>6.1f}   {cells}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="simulation.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("run", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--scenario", choices=SCENARIOS, default="disaster")
        p.add_argument("--agents", type=int, default=6)
        p.add_argument("--ticks", type=int, default=80)
        p.add_argument("--json", action="store_true", help="print raw JSON")
        if name == "run":
            p.add_argument("--seed", type=int, default=0)
            p.add_argument("--preset", choices=list(PRESETS), default="balanced")
        else:
            p.add_argument("--seeds", type=int, default=8)
    args = parser.parse_args()

    if args.cmd == "run":
        result = asyncio.run(run_once(args.scenario, args.agents, args.ticks, args.seed, args.preset))
        print(json.dumps(result, indent=2) if args.json else
              "\n".join(f"{k:>20}: {v}" for k, v in result.items() if k != "brain"))
    else:
        results = asyncio.run(compare_presets(args.scenario, args.agents, args.ticks, args.seeds))
        print(json.dumps(results, indent=2) if args.json else
              f"{args.scenario} | {args.agents} agents | {args.ticks} ticks | mean of {args.seeds} seeds\n\n{_table(results)}")


if __name__ == "__main__":
    main()
