"""Per-frame behaviour rules: detection + zones + motion  ->  behaviour label.

Rules (explainable on purpose, so the proposal can state exactly how the AI output
is produced):

1. No pet detected                              -> ABSENT
2. Detector is holding a motionless pet         -> RESTING
3. Pet's anchor point is inside a zone and the
   pet is not walking fast                      -> DRINKING / EATING / LITTER
   (anchor = nose keypoint if a pose model gives one, otherwise the bounding box)
4. Otherwise speed decides                      -> ACTIVE or RESTING

Speed is measured in "body diagonals per second" so it does not depend on the camera
resolution or how far the pet is from the camera.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .types import BBox, Behavior, Detection, FrameState
from .zones import Zone


@dataclass
class BehaviorConfig:
    active_speed: float = 0.25        # body-diagonals / s above which the pet is "active"
    zone_max_speed: float = 0.25      # moving faster than this in a zone = just passing (same as active_speed)
    bowl_min_coverage: float = 0.5    # fraction of a bowl zone covered by the pet's bbox
    speed_window_s: float = 1.0       # time window for the speed estimate


class BehaviorClassifier:
    def __init__(self, zones: list[Zone], config: BehaviorConfig | None = None) -> None:
        self.zones = zones
        self.cfg = config or BehaviorConfig()
        self._history: deque[tuple[float, BBox]] = deque()

    def reset(self) -> None:
        self._history.clear()

    def _speed(self, t: float, det: Detection) -> float:
        """Fastest-moving box edge, in body diagonals per second.

        Using edges instead of the centre keeps the estimate honest when the pet is
        partly outside the frame (one edge is pinned to the border while the other moves).
        """
        b = det.bbox
        self._history.append((t, b))
        while self._history and t - self._history[0][0] > self.cfg.speed_window_s:
            self._history.popleft()
        t0, b0 = self._history[0]
        dt = t - t0
        if dt <= 0:
            return 0.0
        dx = max(abs(b.x1 - b0.x1), abs(b.x2 - b0.x2))
        dy = max(abs(b.y1 - b0.y1), abs(b.y2 - b0.y2))
        return (dx ** 2 + dy ** 2) ** 0.5 / max(b.diag, 1.0) / dt

    def _zone_hit(self, det: Detection) -> tuple[Zone | None, float]:
        """Return the zone the pet is using and a 0..1 strength of that match."""
        best: tuple[Zone | None, float] = (None, 0.0)
        nose = det.keypoints.get("nose")
        cx, cy = det.bbox.center
        for z in self.zones:
            if nose is not None:
                strength = 1.0 if z.contains(*nose) else 0.0
            elif z.kind == "litter":
                # Litter boxes are large: the pet's body centre must be inside.
                strength = 1.0 if z.contains(cx, cy) else 0.0
            else:
                # Bowls are small: the pet's body must cover most of the bowl.
                cov = z.coverage_by(det.bbox)
                strength = cov if cov >= self.cfg.bowl_min_coverage else 0.0
            if strength > best[1]:
                best = (z, strength)
        return best

    def classify(self, t: float, detections: list[Detection]) -> FrameState:
        if not detections:
            self.reset()
            return FrameState(t=t, behavior=Behavior.ABSENT, confidence=0.9)

        det = detections[0]  # single-pet prototype: highest-scoring detection
        speed = self._speed(t, det)

        if det.stationary_hold:
            return FrameState(t, Behavior.RESTING, 0.6, det)

        zone, strength = self._zone_hit(det)
        if zone is not None and speed <= self.cfg.zone_max_speed:
            return FrameState(t, zone.behavior, round(det.score * strength, 3), det, zone.name)

        if speed >= self.cfg.active_speed:
            return FrameState(t, Behavior.ACTIVE, round(det.score, 3), det)
        return FrameState(t, Behavior.RESTING, round(det.score * 0.9, 3), det)
