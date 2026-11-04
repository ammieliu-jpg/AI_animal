"""Compare predicted events with ground-truth segments (frame-level, sampled at 10 Hz)."""

from __future__ import annotations

import csv
from pathlib import Path

from .types import Behavior, Event


def load_segments(path: str | Path) -> list[tuple[Behavior, float, float]]:
    with Path(path).open(encoding="utf-8") as f:
        return [(Behavior(r["behavior"]), float(r["start_s"]), float(r["end_s"])) for r in csv.DictReader(f)]


def _label_at(segs: list[tuple[Behavior, float, float]], t: float) -> Behavior:
    for b, s, e in segs:
        if s <= t < e:
            return b
    return Behavior.ABSENT


def evaluate(events: list[Event], truth: list[tuple[Behavior, float, float]],
             ignore_transitions_s: float = 1.0) -> dict:
    """Frame accuracy and per-behaviour IoU. Times within ``ignore_transitions_s`` of a
    ground-truth boundary are skipped, since the exact switch moment is ambiguous."""
    pred = [(e.behavior, e.start_s, e.end_s) for e in events]
    end = max(e for _, _, e in truth)
    bounds = [s for _, s, _ in truth] + [e for _, _, e in truth]
    inter = {b: 0 for b in Behavior}
    union = {b: 0 for b in Behavior}
    correct = total = 0
    t = 0.0
    while t < end:
        if all(abs(t - x) > ignore_transitions_s for x in bounds):
            g, p = _label_at(truth, t), _label_at(pred, t)
            total += 1
            correct += g == p
            for b in Behavior:
                if g == b and p == b:
                    inter[b] += 1
                if g == b or p == b:
                    union[b] += 1
        t += 0.1
    return {
        "frame_accuracy": round(correct / total, 3) if total else 0.0,
        "iou": {b.value: round(inter[b] / union[b], 3) for b in Behavior if union[b]},
    }
