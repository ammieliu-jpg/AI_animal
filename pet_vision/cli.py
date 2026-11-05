"""Command line entry point: ``python -m pet_vision <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2


def _detector(args):
    if args.detector == "onnx":
        if not args.model:
            sys.exit("--model is required for --detector onnx")
        from .detectors import OnnxYoloDetector
        return OnnxYoloDetector(args.model, conf_threshold=args.conf)
    from .detectors import MotionDetector
    return MotionDetector(fps=args.fps)


def cmd_run(args) -> None:
    from .pipeline import process_video, write_outputs
    from .zones import load_zones

    cap = cv2.VideoCapture(args.video)
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    zones = load_zones(args.zones, size)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = process_video(
        args.video, zones, _detector(args), sample_fps=args.fps,
        annotate_path=None if args.no_annotate else out / "annotated.mp4",
        overview_path=out / "overview.jpg",
    )
    paths = write_outputs(result, out)
    print(f"{len(result.pet_ids)} pet(s), {len(result.events)} events -> {paths['events']}")
    print(f"overview image -> {out / 'overview.jpg'}")
    for pet_id in result.pet_ids:
        print(f"[{pet_id}]")
        for e in result.events_for(pet_id):
            where = f" @{e.zone}" if e.zone else ""
            print(f"  {e.start_s:7.1f}s - {e.end_s:7.1f}s  {e.behavior.label_zh:<4} ({e.behavior.value}{where}, "
                  f"{e.duration_s:.1f}s, conf {e.confidence:.2f})")
    if args.ground_truth and result.primary_pet:
        from .evaluate import evaluate, load_segments
        report = evaluate(result.events_for(result.primary_pet), load_segments(args.ground_truth))
        (out / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("evaluation:", json.dumps(report))


def cmd_synth(args) -> None:
    from .synth import generate
    paths = generate(args.out, fps=args.fps, seed=args.seed)
    for k, p in paths.items():
        print(f"{k}: {p}")


def cmd_snapshot(args) -> None:
    """Save one frame with a coordinate grid, to read off zone coordinates by eye."""
    cap = cv2.VideoCapture(args.video)
    cap.set(cv2.CAP_PROP_POS_MSEC, args.at * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"cannot read frame from {args.video}")
    h, w = frame.shape[:2]
    for x in range(0, w, 50):
        cv2.line(frame, (x, 0), (x, h), (255, 255, 255) if x % 100 == 0 else (160, 160, 160), 1)
        if x % 100 == 0:
            cv2.putText(frame, str(x), (x + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    for y in range(0, h, 50):
        cv2.line(frame, (0, y), (w, y), (255, 255, 255) if y % 100 == 0 else (160, 160, 160), 1)
        if y % 100 == 0:
            cv2.putText(frame, str(y), (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    cv2.imwrite(args.out, frame)
    print(f"saved {args.out} ({w}x{h})")


def cmd_init(args) -> None:
    from .batch import write_templates
    for p in write_templates(Path(args.folder)):
        print(f"created {p}")


def cmd_prepare(args) -> None:
    from .batch import prepare
    for n in prepare(Path(args.folder), args.model):
        print(n)


def cmd_batch(args) -> None:
    from .batch import run_batch
    run_batch(Path(args.folder), Path(args.out), args.detector, args.model, args.fps, args.annotate)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="pet_vision", description="毛孩日常哨兵 — ① 視覺模組")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="analyse a video and write events / summary")
    r.add_argument("video")
    r.add_argument("--zones", required=True, help="zones JSON (water / food / litter)")
    r.add_argument("--out", default="output")
    r.add_argument("--detector", choices=["motion", "onnx"], default="motion")
    r.add_argument("--model", help="ONNX model path for --detector onnx")
    r.add_argument("--conf", type=float, default=0.35)
    r.add_argument("--fps", type=float, default=5.0, help="processing frame rate")
    r.add_argument("--no-annotate", action="store_true")
    r.add_argument("--ground-truth", help="ground_truth.csv to score against")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("synth", help="generate a synthetic test clip with ground truth")
    s.add_argument("--out", default="output/synthetic")
    s.add_argument("--fps", type=float, default=15.0)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_synth)

    n = sub.add_parser("snapshot", help="save a frame with a coordinate grid for drawing zones")
    n.add_argument("video")
    n.add_argument("--at", type=float, default=0.0, help="time in seconds")
    n.add_argument("--out", default="snapshot.jpg")
    n.set_defaults(func=cmd_snapshot)

    i = sub.add_parser("init", help="create sources.csv / labels.csv templates in a video folder")
    i.add_argument("folder")
    i.set_defaults(func=cmd_init)

    pr = sub.add_parser("prepare", help="snapshots for every video (+ draft bowl zones with --model)")
    pr.add_argument("folder")
    pr.add_argument("--model", help="ONNX YOLO model: auto-draft bowl zones")
    pr.set_defaults(func=cmd_prepare)

    b = sub.add_parser("batch", help="run every video in a folder and score against labels.csv")
    b.add_argument("folder")
    b.add_argument("--out", default="output/batch")
    b.add_argument("--detector", choices=["motion", "onnx"], default="motion")
    b.add_argument("--model")
    b.add_argument("--fps", type=float, default=5.0)
    b.add_argument("--annotate", action="store_true", help="also write annotated videos (slower)")
    b.set_defaults(func=cmd_batch)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
