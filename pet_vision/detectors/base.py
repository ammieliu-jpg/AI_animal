from __future__ import annotations

from typing import Protocol

import numpy as np

from ..types import Detection


class Detector(Protocol):
    """Anything that turns a BGR frame into pet detections."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        ...
