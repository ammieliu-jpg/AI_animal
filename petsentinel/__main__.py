"""``python -m petsentinel demo`` — run modules ① → ② → ③ in one go."""

import argparse

from .demo import run_demo


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="petsentinel", description="毛孩日常哨兵 — 完整 Demo 流程")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="video -> behaviour -> personal baseline -> reminders")
    d.add_argument("--video", help="home-camera video (optional)")
    d.add_argument("--zones", help="zones JSON for the video")
    d.add_argument("--detector", choices=["motion", "onnx"], default="motion")
    d.add_argument("--model", help="ONNX model for --detector onnx")
    d.add_argument("--out", default="output/demo")
    d.add_argument("--days", type=int, default=60)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--date", help="day to show reminders for (default: the most eventful day)")
    d.add_argument("--llm", action="store_true", help="let Claude write the reminders (needs an API key)")
    args = p.parse_args(argv)
    run_demo(args.out, args.video, args.zones, args.detector, args.model, args.days, args.seed, args.date, args.llm)


main()
