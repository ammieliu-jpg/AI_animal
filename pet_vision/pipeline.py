"""Video in  ->  per-pet behaviour timeline + events + daily summary (+ annotated video).

Multiple pets are supported: detections are linked into tracks (one per pet) and each
track gets its own behaviour classifier and event list (``pet_id`` = ``cat_1``, ``dog_2``…).
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .behavior import BehaviorClassifier, BehaviorConfig
from .detectors.base import Detector
from .events import build_events, summarize
from .tracker import SimpleTracker
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
ACTIVITY_WIDTH = 320  # frames are downscaled to this width to measure motion inside zones


@dataclass
class VideoResult:
    fps: float
    frame_size: tuple[int, int]
    # pet_id -> per-frame states (only frames from the pet's first to last appearance)
    tracks: dict[str, list[FrameState]]
    events: list[Event]
    # per sampled frame: [(pet_id, state)] for drawing
    frame_states: list[list[tuple[str, FrameState]]] = field(default_factory=list, repr=False)

    @property
    def pet_ids(self) -> list[str]:
        return list(self.tracks)

    @property
    def primary_pet(self) -> str | None:
        """The pet seen for the longest time."""
        if not self.tracks:
            return None
        return max(self.tracks, key=lambda p: sum(s.behavior != Behavior.ABSENT for s in self.tracks[p]))

    def events_for(self, pet_id: str) -> list[Event]:
        return [e for e in self.events if e.pet_id == pet_id]

    @property
    def summary(self) -> dict:
        return {p: summarize(self.events_for(p)) for p in self.pet_ids}


class ZoneActivity:
    """Mean grey-level change inside each zone between consecutive sampled frames."""

    def __init__(self, zones: list[Zone], frame_w: int) -> None:
        self.zones = zones
        self.s = ACTIVITY_WIDTH / frame_w if frame_w > ACTIVITY_WIDTH else 1.0
        self._prev: np.ndarray | None = None

    def __call__(self, frame: np.ndarray) -> dict[str, float]:
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (int(w * self.s), int(h * self.s))) if self.s != 1.0 else frame
        g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        prev, self._prev = self._prev, g
        if prev is None:
            return {}
        diff = cv2.absdiff(g, prev)
        out = {}
        for z in self.zones:
            b = z.bounds
            x1, y1 = max(0, int(b.x1 * self.s)), max(0, int(b.y1 * self.s))
            x2, y2 = min(g.shape[1], int(b.x2 * self.s) + 1), min(g.shape[0], int(b.y2 * self.s) + 1)
            out[z.name] = float(diff[y1:y2, x1:x2].mean()) if x2 > x1 and y2 > y1 else 0.0
        return out


def analyze_frames(
    frames: Iterable[tuple[float, np.ndarray]],
    zones: list[Zone],
    detector: Detector,
    fps: float,
    behavior_config: BehaviorConfig | None = None,
    min_track_seconds: float = 2.0,
    keep_frame_states: bool = False,
) -> VideoResult:
    """Core loop, independent of video I/O. ``frames`` yields ``(t_seconds, bgr_frame)``."""
    tracker = SimpleTracker(max_missed=max(1, int(fps * 2)))
    classifiers: dict[int, BehaviorClassifier] = {}
    labels: dict[int, str] = {}
    states: dict[int, list[FrameState]] = {}
    per_frame: list[list[tuple[int, FrameState]]] = []
    activity: ZoneActivity | None = None
    size = (0, 0)

    for t, frame in frames:
        if activity is None:
            size = (frame.shape[1], frame.shape[0])
            activity = ZoneActivity(zones, size[0])
        zone_act = activity(frame)
        assigned = dict(tracker.update(detector.detect(frame)))
        row = []
        for tid in set(states) | set(assigned):
            if tid not in classifiers:
                classifiers[tid] = BehaviorClassifier(zones, behavior_config)
                labels[tid] = assigned[tid].label
                states[tid] = []
            det = assigned.get(tid)
            st = classifiers[tid].classify(t, [det] if det else [], zone_act)
            states[tid].append(st)
            if det is not None:
                row.append((tid, st))
        per_frame.append(row)

    # Drop flickers: tracks seen for less than min_track_seconds are likely false detections.
    keep = [tid for tid, ss in states.items()
            if sum(s.behavior != Behavior.ABSENT for s in ss) / fps >= min_track_seconds]
    # Number pets per species in order of appearance: cat_1, cat_2, dog_1 …
    names: dict[int, str] = {}
    counts: dict[str, int] = {}
    for tid in sorted(keep):
        counts[labels[tid]] = counts.get(labels[tid], 0) + 1
        names[tid] = f"{labels[tid]}_{counts[labels[tid]]}"

    tracks: dict[str, list[FrameState]] = {}
    events: list[Event] = []
    for tid in sorted(keep):
        ss = states[tid]
        while ss and ss[-1].behavior == Behavior.ABSENT:  # trailing frames after the track ended
            ss = ss[:-1]
        tracks[names[tid]] = ss
        events += build_events(ss, fps, pet_id=names[tid], include_absent=True)
    events.sort(key=lambda e: (e.start_s, e.pet_id))

    frame_states = []
    if keep_frame_states:
        frame_states = [[(names[tid], st) for tid, st in row if tid in names] for row in per_frame]
    return VideoResult(fps, size, tracks, events, frame_states)


def _iter_video(cap: cv2.VideoCapture, step: int, src_fps: float, keep: list | None):
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            if keep is not None:
                keep.append(frame)
            yield idx / src_fps, frame
        idx += 1


def _event_at(events: list[Event], pet_id: str, t: float) -> Behavior:
    for e in events:
        if e.pet_id == pet_id and e.start_s <= t < e.end_s:
            return e.behavior
    return Behavior.ABSENT


def _draw(frame: np.ndarray, zones: list[Zone], t: float, row: list[tuple[str, FrameState]],
          events: list[Event], pet_ids: list[str]) -> np.ndarray:
    out = frame.copy()
    # Scale lines and text with resolution so labels stay readable on 1080p / 4K video.
    k = max(1.0, out.shape[1] / 640)
    lw, font = max(2, int(2 * k)), cv2.FONT_HERSHEY_SIMPLEX
    for z in zones:
        c = ZONE_COLORS.get(z.kind, (200, 200, 200))
        cv2.polylines(out, [z.as_int_array()], True, c, lw)
        zb = z.bounds
        name = z.name if z.name.isascii() else z.kind  # OpenCV font cannot draw CJK
        cv2.putText(out, name, (int(zb.x1 + 4 * k), int(zb.y1 + 16 * k)), font, 0.45 * k, c, max(1, int(k)))
    for pet_id, st in row:
        b = st.detection.bbox
        c = COLORS[st.behavior]
        cv2.rectangle(out, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), c, lw)
        zone = st.zone if st.zone and st.zone.isascii() else None
        tag = f"{pet_id} {st.behavior.value}" + (f" @{zone}" if zone else "")
        y = max(int(44 * k), int(b.y1 - 6 * k))
        cv2.putText(out, tag, (int(b.x1 + 4 * k), y), font, 0.5 * k, c, lw)
    bar_h = int(26 * k)
    cv2.rectangle(out, (0, 0), (out.shape[1], bar_h), (30, 30, 30), -1)
    x = int(8 * k)
    cv2.putText(out, f"t={t:5.1f}s", (x, int(18 * k)), font, 0.55 * k, (230, 230, 230), lw)
    x += int(110 * k)
    for pet_id in pet_ids:
        b = _event_at(events, pet_id, t)
        txt = f"{pet_id}: {b.value.upper()}"
        cv2.putText(out, txt, (x, int(18 * k)), font, 0.55 * k, COLORS[b], lw)
        x += int((len(txt) * 11 + 24) * k)
    return out


def process_video(
    video_path: str | Path,
    zones: list[Zone],
    detector: Detector,
    sample_fps: float = 5.0,
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

    kept: list[np.ndarray] | None = [] if annotate_path is not None else None
    result = analyze_frames(_iter_video(cap, step, src_fps, kept), zones, detector, eff_fps,
                            behavior_config, keep_frame_states=annotate_path is not None)
    cap.release()

    if annotate_path is not None and kept:
        writer = cv2.VideoWriter(str(annotate_path), cv2.VideoWriter_fourcc(*"mp4v"), eff_fps, (w, h))
        for i, frame in enumerate(kept):
            writer.write(_draw(frame, zones, i / eff_fps, result.frame_states[i], result.events, result.pet_ids))
        writer.release()

    result.events = [e for e in result.events if e.behavior != Behavior.ABSENT]
    return result


def write_outputs(result: VideoResult, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "events": out / "events.csv",
        "frames": out / "frames.csv",
        "summary": out / "summary.json",
    }
    with paths["events"].open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["pet_id", "behavior", "behavior_zh", "start_s", "end_s", "duration_s", "zone", "confidence"])
        for e in result.events:
            wr.writerow([e.pet_id, e.behavior.value, e.behavior.label_zh, e.start_s, e.end_s,
                         round(e.duration_s, 2), e.zone or "", e.confidence])
    with paths["frames"].open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["pet_id", "t", "behavior", "confidence", "zone", "x1", "y1", "x2", "y2"])
        for pet_id, ss in result.tracks.items():
            for s in ss:
                d = s.detection
                box = [round(v, 1) for v in (d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2)] if d else [""] * 4
                wr.writerow([pet_id, round(s.t, 2), s.behavior.value, s.confidence, s.zone or "", *box])
    paths["summary"].write_text(
        json.dumps({"fps": result.fps, "frame_size": result.frame_size, "pets": result.summary},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return paths
