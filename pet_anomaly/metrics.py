"""Daily behaviour metrics: the bridge between module ① (vision) and module ② (anomaly).

One row per pet per day. Every metric is something the camera can actually observe
(counts and durations), never an inferred health value.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Metric:
    key: str
    label_zh: str
    unit_zh: str
    # Which directions are worth a reminder. Both, for most metrics.
    watch_up: bool = True
    watch_down: bool = True


METRICS: list[Metric] = [
    Metric("drinking_count", "喝水次數", "次"),
    Metric("drinking_min", "喝水總時間", "分鐘"),
    Metric("eating_count", "進食次數", "次"),
    Metric("eating_min", "進食總時間", "分鐘"),
    Metric("litter_count", "如廁次數", "次"),
    Metric("litter_min", "如廁總時間", "分鐘"),
    Metric("active_min", "活動時間", "分鐘"),
    Metric("resting_h", "休息時間", "小時"),
]
METRIC_KEYS = [m.key for m in METRICS]
METRIC_BY_KEY = {m.key: m for m in METRICS}


def read_daily(path: str | Path) -> list[dict]:
    """Read ``daily.csv`` (columns: date, pet_id, pet_name, species, <metrics>)."""
    rows = []
    with Path(path).open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row = {k: r[k] for k in ("date", "pet_id", "pet_name", "species") if k in r}
            for k in METRIC_KEYS:
                if r.get(k) not in (None, ""):
                    row[k] = float(r[k])
            rows.append(row)
    rows.sort(key=lambda r: (r["pet_id"], r["date"]))
    return rows


def write_daily(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["date", "pet_id", "pet_name", "species", *METRIC_KEYS]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})


def daily_from_events(events_csv: str | Path, date: str) -> list[dict]:
    """Aggregate a module-① ``events.csv`` into one daily row per pet.

    Use this when the camera recorded the whole day; a short clip only gives a
    partial day and should not be compared with full-day baselines.
    """
    agg: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    with Path(events_csv).open(encoding="utf-8-sig") as f:
        for e in csv.DictReader(f):
            a = agg[e["pet_id"]]
            b, dur = e["behavior"], float(e["duration_s"])
            if b in ("drinking", "eating", "litter"):
                a[f"{b}_count"] += 1
                a[f"{b}_min"] += dur / 60
            elif b == "active":
                a["active_min"] += dur / 60
            elif b == "resting":
                a["resting_h"] += dur / 3600
    rows = []
    for pet_id, a in sorted(agg.items()):
        species = pet_id.split("_")[0] if "_" in pet_id else "pet"
        rows.append({"date": date, "pet_id": pet_id, "pet_name": pet_id, "species": species,
                     **{k: float(a.get(k, 0.0)) for k in METRIC_KEYS}})
    return rows
