"""毛孩日常哨兵 (PetSentinel) — module ①: turn home-camera video into a pet behaviour timeline."""

from .behavior import BehaviorClassifier, BehaviorConfig
from .events import build_events, summarize
from .pipeline import process_video, write_outputs
from .types import BBox, Behavior, Detection, Event, FrameState
from .zones import Zone, load_zones

__all__ = [
    "BBox", "Behavior", "BehaviorClassifier", "BehaviorConfig", "Detection", "Event",
    "FrameState", "Zone", "build_events", "load_zones", "process_video", "summarize",
    "write_outputs",
]
