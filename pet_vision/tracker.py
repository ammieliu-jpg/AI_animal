"""Keep a stable ID for each pet across frames, so multi-pet homes get separate records.

Greedy IoU matching (with a centre-distance fallback for fast moves). IDs are only
stable *within one video*; recognising the same cat across days needs an appearance
model (individual re-identification) and is future work.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import BBox, Detection


def iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    bbox: BBox
    label: str
    missed: int = 0
    hits: int = 0


class SimpleTracker:
    def __init__(self, iou_threshold: float = 0.2, max_missed: int = 10) -> None:
        """
        Args:
            iou_threshold: minimum overlap to continue a track.
            max_missed: frames a track survives without a matching detection
                (e.g. a pet briefly hidden behind furniture).
        """
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.tracks: dict[int, Track] = {}
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
        """Assign each detection a track ID. Returns ``(track_id, detection)`` pairs."""
        pairs = []
        for tid, tr in self.tracks.items():
            for di, d in enumerate(detections):
                score = iou(tr.bbox, d.bbox)
                if score < self.iou_threshold:
                    # Fallback for fast motion: centres close relative to body size.
                    (ax, ay), (bx, by) = tr.bbox.center, d.bbox.center
                    dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                    if dist < 0.5 * max(tr.bbox.diag, d.bbox.diag) and tr.label == d.label:
                        score = self.iou_threshold * 0.5  # weaker than any real overlap
                    else:
                        continue
                pairs.append((score, tid, di))
        pairs.sort(reverse=True)

        used_t, used_d, out = set(), set(), []
        for _, tid, di in pairs:
            if tid in used_t or di in used_d:
                continue
            used_t.add(tid)
            used_d.add(di)
            tr = self.tracks[tid]
            tr.bbox, tr.missed, tr.hits = detections[di].bbox, 0, tr.hits + 1
            out.append((tid, detections[di]))

        for di, d in enumerate(detections):
            if di not in used_d:
                tid = self._next_id
                self._next_id += 1
                self.tracks[tid] = Track(tid, d.bbox, d.label, hits=1)
                out.append((tid, d))

        for tid in list(self.tracks):
            if tid not in used_t and all(t != tid for t, _ in out):
                self.tracks[tid].missed += 1
                if self.tracks[tid].missed > self.max_missed:
                    del self.tracks[tid]
        return sorted(out)
