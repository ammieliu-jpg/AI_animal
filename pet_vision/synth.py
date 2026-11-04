"""Synthetic "home camera" clip with known ground truth.

We have no pet of our own and the sandbox cannot download real footage, so this
generator gives a reproducible clip for tests and for checking the pipeline end to end.
It is clearly labelled as synthetic and must not be presented as real data.
Real-footage runs use licensed clips (see docs/proposal-plan.md §3).
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .types import Behavior

W, H = 640, 360
ZONES = [
    {"name": "water_bowl", "kind": "water", "rect": [70, 270, 130, 320]},
    {"name": "food_bowl", "kind": "food", "rect": [190, 270, 250, 320]},
    {"name": "litter_box", "kind": "litter", "rect": [470, 190, 620, 330]},
]
BED = (330, 170)


@dataclass
class Step:
    behavior: Behavior
    duration_s: float
    target: tuple[float, float] | None  # where the pet ends up (None = off-screen)


def default_script() -> list[Step]:
    return [
        Step(Behavior.ABSENT, 4, None),
        Step(Behavior.ACTIVE, 4, (100, 280)),      # walk in from the left to the water bowl
        Step(Behavior.DRINKING, 8, (100, 280)),
        Step(Behavior.ACTIVE, 4, BED),
        Step(Behavior.RESTING, 30, BED),
        Step(Behavior.ACTIVE, 4, (220, 280)),
        Step(Behavior.EATING, 12, (220, 280)),
        Step(Behavior.ACTIVE, 4, (545, 255)),
        Step(Behavior.LITTER, 15, (545, 255)),
        Step(Behavior.ACTIVE, 4, (680, 200)),      # leave through the right edge
        Step(Behavior.ABSENT, 4, None),
    ]


def _background(rng: np.random.Generator) -> np.ndarray:
    bg = np.zeros((H, W, 3), np.uint8)
    bg[:] = (170, 190, 205)                                   # wall
    bg[200:] = (110, 140, 165)                                # floor
    tex = rng.normal(0, 6, (H, W, 1)).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + tex, 0, 255).astype(np.uint8)
    cv2.rectangle(bg, (280, 150), (390, 200), (150, 120, 190), -1)   # pet bed
    for z, col in zip(ZONES, [(200, 120, 40), (40, 120, 200), (90, 90, 90)]):
        x1, y1, x2, y2 = z["rect"]
        if z["kind"] == "litter":
            cv2.rectangle(bg, (x1, y1), (x2, y2), col, 3)
        else:
            cv2.ellipse(bg, ((x1 + x2) // 2, (y1 + y2) // 2 + 10), ((x2 - x1) // 2, 10), 0, 0, 360, col, -1)
    return bg


def _draw_pet(frame: np.ndarray, x: float, y: float, facing: float, head_dy: float) -> None:
    body = (60, 75, 95)
    cv2.ellipse(frame, (int(x), int(y)), (38, 20), 0, 0, 360, body, -1)
    hx = int(x + facing * 36)
    cv2.circle(frame, (hx, int(y - 12 + head_dy)), 14, body, -1)
    cv2.circle(frame, (hx + int(facing * 6), int(y - 15 + head_dy)), 2, (20, 20, 20), -1)
    cv2.line(frame, (int(x - facing * 36), int(y)), (int(x - facing * 60), int(y - 22)), body, 6)


def generate(out_dir: str | Path, fps: float = 15.0, seed: int = 0,
             script: list[Step] | None = None) -> dict[str, Path]:
    """Write ``synthetic.mp4``, ``zones.json`` and ``ground_truth.csv`` into ``out_dir``."""
    rng = np.random.default_rng(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = script or default_script()
    bg = _background(rng)

    video = out / "synthetic.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    gt_rows = []
    pos = (-60.0, 280.0)
    facing = 1.0
    t0 = 0.0
    for step in script:
        n = int(round(step.duration_s * fps))
        start = pos
        if step.target is None and step.behavior == Behavior.ABSENT:
            pos = (-60.0, 280.0) if t0 == 0 else pos
        for i in range(n):
            frame = bg.copy()
            frac = (i + 1) / n
            head_dy = 0.0
            if step.behavior == Behavior.ACTIVE and step.target is not None:
                x = start[0] + (step.target[0] - start[0]) * frac
                y = start[1] + (step.target[1] - start[1]) * frac
                facing = 1.0 if step.target[0] >= start[0] else -1.0
            elif step.target is not None:
                x, y = step.target
                if step.behavior in (Behavior.DRINKING, Behavior.EATING):
                    head_dy = 10 + 5 * math.sin(i / fps * 2 * math.pi * 1.5)  # head bobbing
                elif step.behavior == Behavior.LITTER:
                    x += 4 * math.sin(i / fps * 2 * math.pi * 0.5)             # shuffling / digging
                # RESTING: perfectly still
            else:
                x = None
            if x is not None and -80 < x < W + 80:
                _draw_pet(frame, x, y, facing, head_dy)
                pos = (x, y)
            noise = rng.normal(0, 2.0, frame.shape).astype(np.int16)  # sensor noise
            writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))
        gt_rows.append((step.behavior.value, round(t0, 2), round(t0 + n / fps, 2)))
        t0 += n / fps
    writer.release()

    zones_path = out / "zones.json"
    zones_path.write_text(json.dumps({"frame_size": [W, H], "zones": ZONES}, indent=2), encoding="utf-8")
    gt_path = out / "ground_truth.csv"
    with gt_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["behavior", "start_s", "end_s"])
        wr.writerows(gt_rows)
    return {"video": video, "zones": zones_path, "ground_truth": gt_path}
