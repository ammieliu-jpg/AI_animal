"""Turn noisy per-frame labels into clean behaviour events and a daily summary.

1. Majority-vote smoothing over a short sliding window.
2. Run-length segmentation.
3. Segments shorter than a behaviour's minimum duration are merged into a neighbour
   (e.g. walking past the water bowl for 1 s is *not* a drinking event).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .types import Behavior, Event, FrameState

DEFAULT_MIN_DURATION_S: dict[Behavior, float] = {
    Behavior.DRINKING: 3.0,
    Behavior.EATING: 5.0,
    Behavior.LITTER: 8.0,
    Behavior.RESTING: 5.0,
    Behavior.ACTIVE: 2.0,
    Behavior.ABSENT: 2.0,
}


@dataclass
class _Seg:
    behavior: Behavior
    start: int  # frame index, inclusive
    end: int    # frame index, exclusive
    zones: Counter = field(default_factory=Counter)
    conf_sum: float = 0.0


def smooth_labels(states: list[FrameState], window: int) -> list[Behavior]:
    """Centered majority vote. Ties keep the original label."""
    if window <= 1:
        return [s.behavior for s in states]
    half = window // 2
    out = []
    for i, s in enumerate(states):
        votes = Counter(x.behavior for x in states[max(0, i - half): i + half + 1])
        top, n = votes.most_common(1)[0]
        out.append(s.behavior if votes[s.behavior] == n else top)
    return out


def _segments(states: list[FrameState], labels: list[Behavior]) -> list[_Seg]:
    segs: list[_Seg] = []
    for i, (s, b) in enumerate(zip(states, labels)):
        if segs and segs[-1].behavior == b:
            seg = segs[-1]
            seg.end = i + 1
        else:
            seg = _Seg(b, i, i + 1)
            segs.append(seg)
        seg.conf_sum += s.confidence if s.behavior == b else 0.5
        if s.zone and s.behavior == b:
            seg.zones[s.zone] += 1
    return segs


def _merge_adjacent(segs: list[_Seg]) -> list[_Seg]:
    out: list[_Seg] = []
    for s in segs:
        if out and out[-1].behavior == s.behavior:
            p = out[-1]
            p.end, p.conf_sum = s.end, p.conf_sum + s.conf_sum
            p.zones.update(s.zones)
        else:
            out.append(s)
    return out


def build_events(
    states: list[FrameState],
    fps: float,
    pet_id: str = "pet1",
    smooth_window_s: float = 1.0,
    min_duration_s: dict[Behavior, float] | None = None,
    include_absent: bool = False,
) -> list[Event]:
    if not states:
        return []
    mins = {**DEFAULT_MIN_DURATION_S, **(min_duration_s or {})}
    dt = 1.0 / fps
    labels = smooth_labels(states, max(1, int(round(smooth_window_s * fps))))
    segs = _segments(states, labels)

    # Repeatedly absorb the shortest too-short segment into its longer neighbour.
    while len(segs) > 1:
        short = [
            (s.end - s.start, i) for i, s in enumerate(segs)
            if (s.end - s.start) * dt < mins.get(s.behavior, 0.0)
        ]
        if not short:
            break
        _, i = min(short)
        s = segs[i]
        left = segs[i - 1] if i > 0 else None
        right = segs[i + 1] if i + 1 < len(segs) else None
        target = max(
            (n for n in (left, right) if n is not None),
            key=lambda n: n.end - n.start,
        )
        target.start, target.end = min(target.start, s.start), max(target.end, s.end)
        target.conf_sum += 0.5 * (s.end - s.start)
        del segs[i]
        segs = _merge_adjacent(segs)

    events = []
    for s in segs:
        if s.behavior == Behavior.ABSENT and not include_absent:
            continue
        n = s.end - s.start
        events.append(
            Event(
                pet_id=pet_id,
                behavior=s.behavior,
                start_s=round(states[s.start].t, 2),
                end_s=round(states[s.end - 1].t + dt, 2),
                confidence=round(min(1.0, s.conf_sum / n), 3),
                zone=s.zones.most_common(1)[0][0] if s.zones else None,
            )
        )
    return events


def summarize(events: list[Event]) -> dict:
    """Per-behaviour counts and durations — the daily input for module ② (anomaly detection)."""
    out: dict[str, dict] = {}
    for b in Behavior:
        evs = [e for e in events if e.behavior == b]
        if b == Behavior.ABSENT and not evs:
            continue
        total = sum(e.duration_s for e in evs)
        out[b.value] = {
            "label_zh": b.label_zh,
            "count": len(evs),
            "total_s": round(total, 1),
            "mean_s": round(total / len(evs), 1) if evs else 0.0,
        }
    return out
