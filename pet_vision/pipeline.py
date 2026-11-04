"""Video in  ->  behaviour timeline + events + daily summary (+ annotated video)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .behavior import BehaviorClassifier, BehaviorConfig
from .detectors.base import Detector
from .events import build_events, summarize
from .types import Behavior, Event, FrameState
from .zones import Zone

# BGR colours for the overlay (OpenCV's built-in font is ASCII-only, so labels are English).
COLORS = {
    Behavior.DRINKING: (255, 160, 0),
    Behavior.EATING: (0, 170, 255),
    Behavior.LITTER: (180, 80, 200),
    Behavior.RESTING: (120, 200, 120),
    Behavior.ACTIVE: (60, 60, 230),
    Behavior.ABSENT: (150, 150, 150),
}
ZONE_COLORS = {"water": (255, 160, 0), "food": (0, 170, 255), "litter": (180, 80, 200)}


@dataclass
class VideoResult:
    fps: float
    frame_size: tuple[int, int]
    states: list[FrameState]
    events: list[Event]

    @property
    def summary(self) -> dict:
        return summarize(self.events)


def _draw(frame: np.ndarray, zones: list[Zone], st: FrameState, current: Behavior) -> np.ndarray:
    out = frame.copy()
    for z in zones:
        c = ZONE_COLORS.get(z.kind, (200, 200, 200))
        cv2.polylines(out, [z.as_int_array()], True, c, 2)
        zb = z.bounds
        cv2.putText(out, z.kind, (int(zb.x1), int(zb.y1) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
    if st.detection is not None:
        b = st.detection.bbox
        c = COLORS[st.behavior]
        cv2.rectangle(out, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), c, 2)
        tag = f"{st.detection.label} {st.behavior.value} {st.confidence:.2f}"
        cv2.putText(out, tag, (int(b.x1), max(14, int(b.y1) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 2)
    banner = f"t={st.t:6.1f}s  event: {current.value.upper()}"
    cv2.rectangle(out, (0, 0), (out.shape[1], 26), (30, 30, 30), -1)
    cv2.putText(out, banner, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLORS[current], 2)
    return out


def _event_at(events: list[Event], t: float) -> Behavior:
    for e in events:
        if e.start_s <= t < e.end_s:
            return e.behavior
    return Behavior.ABSENT


def process_video(
    video_path: str | Path,
    zones: list[Zone],
    detector: Detector,
    sample_fps: float = 5.0,
    pet_id: str = "pet1",
    behavior_config: BehaviorConfig | None = None,
    annotate_path: str | Path | None = None,
) -> VideoResult:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {video_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, int(round(src_fps / sample_fps)))
    eff_fps = src_fps / step

    clf = BehaviorClassifier(zones, behavior_config)
    states: list[FrameState] = []
    kept_frames: list[np.ndarray] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / src_fps
            states.append(clf.classify(t, detector.detect(frame)))
            if annotate_path is not None:
                kept_frames.append(frame)
        idx += 1
    cap.release()

    events = build_events(states, eff_fps, pet_id=pet_id, include_absent=True)

    if annotate_path is not None and kept_frames:
        writer = cv2.VideoWriter(str(annotate_path), cv2.VideoWriter_fourcc(*"mp4v"), eff_fps, (w, h))
        for frame, st in zip(kept_frames, states):
            writer.write(_draw(frame, zones, st, _event_at(events, st.t)))
        writer.release()

    return VideoResult(eff_fps, (w, h), states, [e for e in events if e.behavior != Behavior.ABSENT])


def write_outputs(result: VideoResult, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "events": out / "events.csv",
        "frames": out / "frames.csv",
        "summary": out / "summary.json",
    }
    with paths["events"].open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["pet_id", "behavior", "behavior_zh", "start_s", "end_s", "duration_s", "zone", "confidence"])
        for e in result.events:
            wr.writerow([e.pet_id, e.behavior.value, e.behavior.label_zh, e.start_s, e.end_s,
                         round(e.duration_s, 2), e.zone or "", e.confidence])
    with paths["frames"].open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["t", "behavior", "confidence", "zone", "x1", "y1", "x2", "y2", "label"])
        for s in result.states:
            d = s.detection
            box = [round(v, 1) for v in (d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2)] if d else ["", "", "", ""]
            wr.writerow([round(s.t, 2), s.behavior.value, s.confidence, s.zone or "", *box, d.label if d else ""])
    paths["summary"].write_text(
        json.dumps({"fps": result.fps, "frame_size": result.frame_size, "behaviors": result.summary},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return paths
