"""``python -m pet_notify <command>`` — module ③: plain-language reminders and vet report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _daily_index(daily_csv) -> dict:
    if not daily_csv:
        return {}
    from pet_anomaly.metrics import read_daily
    return {(r["pet_id"], r["date"]): r for r in read_daily(daily_csv)}


def cmd_daily(args) -> None:
    from .compose import compose
    from .html import preview_page

    items = _load(args.alerts)
    if args.date:
        items = [a for a in items if a["date"] == args.date]
    else:  # latest day per pet
        latest = {}
        for a in items:
            if a["pet_id"] not in latest or a["date"] > latest[a["pet_id"]]["date"]:
                latest[a["pet_id"]] = a
        items = list(latest.values())
    daily = _daily_index(args.daily)

    writer = None
    if args.llm:
        from .llm import ClaudeWriter
        writer = ClaudeWriter(effort=args.effort)

    notes = [compose(a, daily.get((a["pet_id"], a["date"])), writer) for a in sorted(items, key=lambda a: a["pet_id"])]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "notifications.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(preview_page(notes, simulated=args.simulated), encoding="utf-8")
    for n in notes:
        print(f"{n['emoji']} [{n['pet_name']}] {n['title']}\n   {n['body']}\n   -> {n['next_step']}  ({n['source']})")
        for note in n["notes"]:
            print(f"   note: {note}")
    print(f"\npreview -> {out / 'preview.html'}")


def cmd_vet_report(args) -> None:
    from pet_anomaly.detector import PersonalBaselineDetector
    from pet_anomaly.metrics import read_daily

    from .html import vet_report

    rows = read_daily(args.daily)
    assessments = PersonalBaselineDetector().assess(rows)
    alerts = [a.to_dict() for a in assessments]
    end = args.date or max(r["date"] for r in rows if r["pet_id"] == args.pet)
    page = vet_report(rows, alerts, assessments, args.pet, end, days=args.days, simulated=args.simulated)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"vet report -> {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="pet_notify", description="毛孩日常哨兵 — ③ 白話提醒")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("daily", help="write today's reminder for each pet")
    d.add_argument("alerts", help="alerts.json from pet_anomaly detect")
    d.add_argument("--daily", help="daily.csv (adds today's numbers to 'all normal' messages)")
    d.add_argument("--date", help="YYYY-MM-DD (default: each pet's latest day)")
    d.add_argument("--out", default="output/notify")
    d.add_argument("--llm", action="store_true", help="let Claude write the wording (needs an API key)")
    d.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    d.add_argument("--simulated", action="store_true")
    d.set_defaults(func=cmd_daily)

    v = sub.add_parser("vet-report", help="printable observation record for the vet")
    v.add_argument("daily", help="daily.csv")
    v.add_argument("--pet", required=True)
    v.add_argument("--date", help="last day of the report (default: latest)")
    v.add_argument("--days", type=int, default=14)
    v.add_argument("--out", default="output/notify/vet_report.html")
    v.add_argument("--simulated", action="store_true")
    v.set_defaults(func=cmd_vet_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
