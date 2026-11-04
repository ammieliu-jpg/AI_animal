"""``python -m pet_anomaly <command>`` — module ②: personal baselines and reminders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def cmd_simulate(args) -> None:
    from .simulate import write_simulation
    paths = write_simulation(args.out, days=args.days, seed=args.seed)
    for k, p in paths.items():
        print(f"{k}: {p}")


def cmd_detect(args) -> None:
    from .detector import LEVEL_ZH, PersonalBaselineDetector
    from .metrics import read_daily
    from .report import plot_pet, write_alerts

    rows = read_daily(args.daily)
    assessments = PersonalBaselineDetector().assess(rows)
    out = Path(args.out)
    write_alerts(assessments, out / "alerts.json")
    write_alerts(assessments, out / "latest.json", only_latest=True)

    episodes = None
    if args.episodes:
        from .simulate import read_episodes
        episodes = read_episodes(args.episodes)
    for pet_id in sorted({r["pet_id"] for r in rows}):
        p = plot_pet(rows, assessments, pet_id, out / f"trend_{pet_id}.png", episodes, simulated=args.simulated)
        print(f"chart: {p}")

    print("\nreminders (watch / consult):")
    for a in assessments:
        if a.level in ("watch", "consult"):
            why = "; ".join(f"{r.label_zh} {r.today:g}{r.unit_zh}（平常約 {r.usual:g}，{r.change_pct:+.0f}%）"
                            for r in a.reasons[:2]) or "多項指標組合不尋常"
            print(f"  {a.date} {a.pet_name:<6} {LEVEL_ZH[a.level]:<6} {why}")


def cmd_evaluate(args) -> None:
    from .detector import FixedThresholdDetector, PersonalBaselineDetector
    from .evaluate import evaluate
    from .metrics import read_daily
    from .simulate import read_episodes

    rows = read_daily(args.daily)
    episodes = read_episodes(args.episodes)
    report = {
        "personal_baseline": evaluate(PersonalBaselineDetector().assess(rows), episodes),
        "fixed_threshold": evaluate(FixedThresholdDetector().assess(rows), episodes),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    for name, r in report.items():
        print(f"[{name}] found {r['real_episodes_found']}, mean delay {r['mean_consult_delay_days']} d, "
              f"false 'consult' {r['false_consult_days']}/{r['ordinary_days']} ordinary days, "
              f"'watch' {r['watch_days_on_ordinary_days']}, harmless escalated {r['harmless_episodes_escalated']}")


def cmd_ingest(args) -> None:
    """Append one day of module-① results to daily.csv."""
    from .metrics import daily_from_events, read_daily, write_daily

    new = daily_from_events(args.events, args.date)
    path = Path(args.daily)
    rows = read_daily(path) if path.exists() else []
    rows = [r for r in rows if not (r["date"] == args.date and r["pet_id"] in {n["pet_id"] for n in new})]
    write_daily(sorted(rows + new, key=lambda r: (r["pet_id"], r["date"])), path)
    print(f"added {len(new)} pet-day row(s) for {args.date} -> {path}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="pet_anomaly", description="毛孩日常哨兵 — ② 個體化異常偵測")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="generate simulated daily data with known episodes")
    s.add_argument("--out", default="output/sim")
    s.add_argument("--days", type=int, default=60)
    s.add_argument("--seed", type=int, default=7)
    s.set_defaults(func=cmd_simulate)

    d = sub.add_parser("detect", help="assess every pet-day, write alerts.json and charts")
    d.add_argument("daily", help="daily.csv")
    d.add_argument("--out", default="output/anomaly")
    d.add_argument("--episodes", help="episodes.csv (simulation ground truth, drawn on charts)")
    d.add_argument("--simulated", action="store_true", help="mark charts as simulated data")
    d.set_defaults(func=cmd_detect)

    e = sub.add_parser("evaluate", help="compare personal baseline vs fixed threshold")
    e.add_argument("daily")
    e.add_argument("--episodes", required=True)
    e.add_argument("--out")
    e.set_defaults(func=cmd_evaluate)

    i = sub.add_parser("ingest", help="append one day of module-① events.csv to daily.csv")
    i.add_argument("events")
    i.add_argument("--date", required=True, help="YYYY-MM-DD")
    i.add_argument("--daily", default="data/daily.csv")
    i.set_defaults(func=cmd_ingest)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
