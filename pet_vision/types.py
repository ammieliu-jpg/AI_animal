"""Shared data types for the vision module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Behavior(str, Enum):
    """Behaviors the module can label. Values are stable keys used in CSV output."""

    DRINKING = "drinking"
    EATING = "eating"
    LITTER = "litter"      # 如廁（在砂盆／尿布墊區）
    RESTING = "resting"    # 休息／睡覺（幾乎不動）
    ACTIVE = "active"      # 走動／玩耍
    ABSENT = "absent"      # 畫面中沒有寵物

    @property
    def label_zh(self) -> str:
        return _ZH[self]


_ZH = {
    Behavior.DRINKING: "喝水",
    Behavior.EATING: "進食",
    Behavior.LITTER: "如廁",
    Behavior.RESTING: "休息",
    Behavior.ACTIVE: "活動",
    Behavior.ABSENT: "不在畫面",
}


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def w(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def h(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def diag(self) -> float:
        return (self.w ** 2 + self.h ** 2) ** 0.5


@dataclass
class Detection:
    """One detected pet in one frame."""

    bbox: BBox
    score: float
    label: str = "pet"  # "cat" / "dog" / "pet"
    # Optional keypoints from a pose model, e.g. {"nose": (x, y)}.
    keypoints: dict[str, tuple[float, float]] = field(default_factory=dict)
    # True when the detector is re-using the last known position because the
    # pet stopped moving (motion detector only).
    stationary_hold: bool = False


@dataclass
class FrameState:
    """Per-frame behavior label before temporal smoothing."""

    t: float  # seconds from video start
    behavior: Behavior
    confidence: float
    detection: Detection | None = None
    zone: str | None = None


@dataclass
class Event:
    """A smoothed behavior segment, the unit handed to module ② (anomaly detection)."""

    pet_id: str
    behavior: Behavior
    start_s: float
    end_s: float
    confidence: float
    zone: str | None = None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s
