"""Regions of interest (water bowl, food bowl, litter box, ...) drawn on the camera frame.

Only these regions are analysed for drinking / eating / litter behaviour, which keeps
the system non-intrusive (注意事項第 36 點「最小干擾」).

Zone file format (JSON)::

    {
      "frame_size": [1280, 720],
      "zones": [
        {"name": "水碗", "kind": "water",  "polygon": [[100,500],[220,500],[220,600],[100,600]]},
        {"name": "食碗", "kind": "food",   "rect": [300, 500, 420, 600]},
        {"name": "砂盆", "kind": "litter", "rect": [900, 400, 1200, 700]}
      ]
    }

``rect`` is ``[x1, y1, x2, y2]``. ``frame_size`` is optional; when present and the
video has a different resolution, zones are rescaled automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .types import BBox, Behavior

ZONE_KIND_TO_BEHAVIOR = {
    "water": Behavior.DRINKING,
    "food": Behavior.EATING,
    "litter": Behavior.LITTER,
}


@dataclass
class Zone:
    name: str
    kind: str  # water | food | litter
    polygon: list[tuple[float, float]]

    def __post_init__(self) -> None:
        if self.kind not in ZONE_KIND_TO_BEHAVIOR:
            raise ValueError(
                f"zone '{self.name}': unknown kind '{self.kind}', "
                f"expected one of {sorted(ZONE_KIND_TO_BEHAVIOR)}"
            )
        if len(self.polygon) < 3:
            raise ValueError(f"zone '{self.name}': polygon needs at least 3 points")

    @property
    def behavior(self) -> Behavior:
        return ZONE_KIND_TO_BEHAVIOR[self.kind]

    @property
    def bounds(self) -> BBox:
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return BBox(min(xs), min(ys), max(xs), max(ys))

    def contains(self, x: float, y: float) -> bool:
        """Ray-casting point-in-polygon test."""
        inside = False
        pts = self.polygon
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y):
                x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < x_cross:
                    inside = not inside
            j = i
        return inside

    def coverage_by(self, bbox: BBox) -> float:
        """Fraction of this zone's bounding box covered by ``bbox`` (0..1)."""
        zb = self.bounds
        ix = max(0.0, min(zb.x2, bbox.x2) - max(zb.x1, bbox.x1))
        iy = max(0.0, min(zb.y2, bbox.y2) - max(zb.y1, bbox.y1))
        return (ix * iy) / zb.area if zb.area > 0 else 0.0

    def scaled(self, sx: float, sy: float) -> "Zone":
        return Zone(self.name, self.kind, [(x * sx, y * sy) for x, y in self.polygon])

    def as_int_array(self) -> np.ndarray:
        return np.array([[int(x), int(y)] for x, y in self.polygon], dtype=np.int32)


def _zone_from_dict(d: dict) -> Zone:
    if "polygon" in d:
        poly = [(float(x), float(y)) for x, y in d["polygon"]]
    elif "rect" in d:
        x1, y1, x2, y2 = (float(v) for v in d["rect"])
        poly = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    else:
        raise ValueError(f"zone '{d.get('name')}' needs 'polygon' or 'rect'")
    return Zone(name=str(d["name"]), kind=str(d["kind"]), polygon=poly)


def load_zones(path: str | Path, frame_size: tuple[int, int] | None = None) -> list[Zone]:
    """Load zones from JSON; rescale to ``frame_size`` (w, h) if the file declares its own."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    zones = [_zone_from_dict(z) for z in data["zones"]]
    src = data.get("frame_size")
    if src and frame_size and tuple(src) != tuple(frame_size):
        sx = frame_size[0] / src[0]
        sy = frame_size[1] / src[1]
        zones = [z.scaled(sx, sy) for z in zones]
    return zones
