"""Weight-free detector for a fixed camera watching a single pet.

A running-average background model is updated *selectively*: pixels covered by the
pet are (almost) frozen, so a sleeping pet does not fade into the background and does
not leave a "ghost" when it walks away. A very slow update on those pixels still lets
the model recover from permanent scene changes (e.g. a moved chair).

If the pet still disappears from the mask while it was not near the frame edge, its
last position is *held* — a resting pet is still in the room.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..types import BBox, Detection


class MotionDetector:
    def __init__(
        self,
        diff_threshold: int = 28,
        min_area_ratio: float = 0.002,
        bg_rate: float = 0.02,
        fg_rate: float = 0.0005,
        warmup_frames: int = 10,
        edge_margin_ratio: float = 0.03,
        hold_seconds: float | None = None,
        fps: float = 5.0,
    ) -> None:
        """
        Args:
            diff_threshold: grey-level difference that counts as foreground.
            min_area_ratio: ignore blobs smaller than this fraction of the frame.
            bg_rate: background update rate where no pet is present (lighting changes).
            fg_rate: update rate under the pet; tiny so a still pet stays visible.
            warmup_frames: frames used to learn the empty room before detecting.
            edge_margin_ratio: if the pet was last seen this close to the frame border,
                assume it walked out instead of holding its position.
            hold_seconds: max time to hold a stationary pet (None = indefinitely).
            fps: processing frame rate, used to convert ``hold_seconds`` to frames.
        """
        self.diff_threshold = diff_threshold
        self.min_area_ratio = min_area_ratio
        self.bg_rate = bg_rate
        self.fg_rate = fg_rate
        self.warmup_frames = warmup_frames
        self.edge_margin_ratio = edge_margin_ratio
        self.max_hold = None if hold_seconds is None else int(hold_seconds * fps)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._bg: np.ndarray | None = None
        self._frame_idx = 0
        self._last: BBox | None = None
        self._held = 0

    def _near_edge(self, b: BBox, w: int, h: int) -> bool:
        mx, my = w * self.edge_margin_ratio, h * self.edge_margin_ratio
        return b.x1 <= mx or b.y1 <= my or b.x2 >= w - mx or b.y2 >= h - my

    def _foreground(self, gray: np.ndarray) -> np.ndarray:
        diff = cv2.absdiff(gray, self._bg.astype(np.uint8))
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=2)

    def _update_background(self, gray: np.ndarray, mask: np.ndarray) -> None:
        pet_area = cv2.dilate(mask, self._kernel, iterations=3) > 0
        rate = np.where(pet_area, self.fg_rate, self.bg_rate).astype(np.float32)
        self._bg += rate * (gray.astype(np.float32) - self._bg)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        self._frame_idx += 1
        if self._bg is None:
            self._bg = gray.astype(np.float32)
            return []
        if self._frame_idx <= self.warmup_frames:
            self._bg += 0.3 * (gray.astype(np.float32) - self._bg)
            return []

        mask = self._foreground(gray)
        self._update_background(gray, mask)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = self.min_area_ratio * w * h
        blobs = [c for c in contours if cv2.contourArea(c) >= min_area]

        if blobs:
            # Single-pet assumption: keep the largest blob plus pieces close to it
            # (a pet's body is often split into several pieces by the mask).
            blobs.sort(key=cv2.contourArea, reverse=True)
            x, y, bw, bh = cv2.boundingRect(blobs[0])
            reach = 0.5 * max(bw, bh)
            keep = [blobs[0]]
            for c in blobs[1:]:
                cx, cy, cw, ch = cv2.boundingRect(c)
                if (cx < x + bw + reach and cx + cw > x - reach and
                        cy < y + bh + reach and cy + ch > y - reach):
                    keep.append(c)
            x, y, bw, bh = cv2.boundingRect(np.vstack(keep))
            box = BBox(float(x), float(y), float(x + bw), float(y + bh))
            area = sum(cv2.contourArea(c) for c in keep)
            score = float(min(1.0, area / max(1.0, box.area) + 0.3))
            self._last, self._held = box, 0
            return [Detection(bbox=box, score=score)]

        if self._last is not None and not self._near_edge(self._last, w, h):
            if self.max_hold is None or self._held < self.max_hold:
                self._held += 1
                return [Detection(bbox=self._last, score=0.5, stationary_hold=True)]

        self._last = None
        return []
