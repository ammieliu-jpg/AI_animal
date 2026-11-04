"""Personal-baseline anomaly detection.

For every pet and every day:

1. **Personal baseline** — median and robust spread (MAD) of each metric over the
   pet's own recent days (default: last 21 eligible days). Days already judged
   "consult" are left out so an ongoing change does not become the new normal.
2. **Per-metric deviation** — robust z-score of today vs. that baseline.
3. **Unusual combination** — an Isolation Forest trained on the pet's own history
   flags days whose *combination* of metrics is unusual even if no single metric is.
4. **Reminder level** — persistence rules turn deviations into three levels:
   ``normal`` (🟢), ``watch`` (🟡 留意), ``consult`` (🟠 建議諮詢獸醫).
   The highest level is a suggestion to consult a vet; nothing here is a diagnosis
   (注意事項第 33 點).

``FixedThresholdDetector`` is the comparison baseline: one species-wide threshold per
metric, the way a typical "alert when above X" device works.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np

from .metrics import METRIC_BY_KEY, METRIC_KEYS

LEVELS = ["learning", "normal", "watch", "consult"]
LEVEL_ZH = {"learning": "建立基線中", "normal": "正常", "watch": "留意", "consult": "建議諮詢獸醫"}


@dataclass
class Reason:
    metric: str
    label_zh: str
    unit_zh: str
    today: float
    usual: float
    change_pct: float
    z: float
    direction: str      # "up" | "down"
    days_in_row: int


@dataclass
class DayAssessment:
    date: str
    pet_id: str
    pet_name: str
    species: str
    level: str
    reasons: list[Reason] = field(default_factory=list)
    unusual_combination: bool = False
    baseline_days: int = 0
    # metric -> (usual, low, high) on the raw scale: the pet's typical range (about ±2 spreads),
    # for charts. Reminders use the stricter rules in Escalation.
    band: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    @property
    def level_zh(self) -> str:
        return LEVEL_ZH[self.level]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level_zh"] = self.level_zh
        return d


@dataclass
class DetectorConfig:
    window_days: int = 28
    min_history: int = 14    # two weeks of learning before any reminder
    min_same_type: int = 5   # weekend/weekday-specific baseline once this many days exist
    gap_days: int = 2        # leave the last N days out of the baseline (they are being judged)
    watch_z: float = 3.5     # one day this far off -> watch
    multi_z: float = 3.0     # two metrics drifting together this far (2-3 days) -> consult
    sustained_z: float = 4.5 # 2-3 day combined deviation this far off -> consult
    support_z: float = 1.5   # every day in that stretch must be at least this far off, same side
    iforest_min_history: int = 14
    use_iforest: bool = True


def transform(key: str, x: float) -> float:
    """Durations are right-skewed (an occasional long meal is normal), so they are
    compared on a log scale; counts stay as they are."""
    return float(np.log(x + 1.0)) if METRIC_BY_KEY[key].unit_zh != "次" else float(x)


def _is_weekend(iso: str) -> bool:
    return date.fromisoformat(iso).weekday() >= 5


class Escalation:
    """Turns daily per-metric z-scores into a reminder level.

    A single odd day only ever reaches ``watch``. ``consult`` needs the *same* change
    to persist: the combined deviation of the last 2–3 days (sum of z / sqrt(n), which is
    how much evidence the days add up to) must be large, and every one of those days
    must lean the same way. This catches gradual and sudden changes alike while
    one-off spikes (a visitor, a busy day) stay at ``watch``.
    """

    def __init__(self, cfg: DetectorConfig) -> None:
        self.cfg = cfg
        self.history: list[dict[str, float]] = []

    def _run(self, k: str) -> int:
        """Consecutive most-recent days where metric k leans the same way (>= support_z)."""
        n, sign = 0, 0
        for z in reversed(self.history):
            v = z.get(k, 0.0)
            s = 1 if v >= self.cfg.support_z else -1 if v <= -self.cfg.support_z else 0
            if s == 0 or (sign and s != sign):
                break
            sign, n = s, n + 1
        return n

    def _sustained(self, k: str) -> float:
        """Largest |combined z| over the last 2 or 3 days, if all of them lean the same way."""
        run = self._run(k)
        best = 0.0
        for n in (2, 3):
            if run >= n:
                zs = [h[k] for h in self.history[-n:]]
                best = max(best, abs(sum(zs)) / np.sqrt(n))
        return best

    def update(self, z_today: dict[str, float]) -> tuple[str, dict[str, int]]:
        self.history = (self.history + [z_today])[-3:]
        runs = {k: self._run(k) for k in z_today}
        sustained = {k: self._sustained(k) for k in z_today}
        strong = [k for k, v in sustained.items() if v >= self.cfg.sustained_z]
        several = [k for k, v in sustained.items() if v >= self.cfg.multi_z]
        if strong or len(several) >= 2:
            return "consult", runs
        if any(abs(v) >= self.cfg.watch_z for v in z_today.values()) or several:
            return "watch", runs
        return "normal", runs


class PersonalBaselineDetector:
    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.cfg = config or DetectorConfig()

    @staticmethod
    def baseline(history: list[dict], key: str) -> tuple[float, float, float]:
        """Returns (usual raw value, centre, spread); centre/spread are on the
        ``transform`` scale used for z-scores."""
        raw = np.array([h[key] for h in history if key in h], dtype=float)
        vals = np.array([transform(key, v) for v in raw])
        med = float(np.median(vals))
        mad = float(np.median(np.abs(vals - med)))
        if METRIC_BY_KEY[key].unit_zh == "次":
            # Counts of random events vary by about sqrt(mean) day to day (Poisson).
            floor = max(1.0, float(np.sqrt(max(med, 0.0))), 0.08 * abs(med))
        else:
            floor = 0.08  # ~8 % on the log scale
        return float(np.median(raw)), med, max(1.4826 * mad, floor)

    def _day_type_offset(self, history: list[dict], today: dict, key: str) -> float:
        """Weekend and weekday routines differ (owner at home -> more play). Estimate that
        difference from the pet's own history (median of each day type) and remove it,
        so the spread can still be estimated from *all* days."""
        wk = _is_weekend(today["date"])
        same = [transform(key, h[key]) for h in history if _is_weekend(h["date"]) == wk]
        other = [transform(key, h[key]) for h in history if _is_weekend(h["date"]) != wk]
        if len(same) < self.cfg.min_same_type or len(other) < self.cfg.min_same_type:
            return 0.0
        return float(np.median(same) - np.median(other))

    def _stats(self, history: list[dict], today: dict) -> dict:
        """Per metric (usual raw value, centre, spread), adjusted for today's day type."""
        out = {}
        for k in METRIC_KEYS:
            wk = _is_weekend(today["date"])
            off = self._day_type_offset(history, today, k)
            # Shift the other day type onto today's level, then take robust statistics.
            vals = [transform(k, h[k]) + (0.0 if _is_weekend(h["date"]) == wk else off) for h in history]
            raw_same = [h[k] for h in history if _is_weekend(h["date"]) == wk] or [h[k] for h in history]
            med = float(np.median(vals))
            mad = float(np.median(np.abs(np.array(vals) - med)))
            if METRIC_BY_KEY[k].unit_zh == "次":
                floor = max(1.0, float(np.sqrt(max(med, 0.0))), 0.08 * abs(med))
            else:
                floor = 0.08
            # Small samples underestimate spread; widen a little (≈ t-distribution correction).
            n = len(vals)
            spread = max(1.4826 * mad * (1 + 2.0 / max(n, 1)), floor)
            out[k] = (float(np.median(raw_same)), med, spread)
        return out

    def _iforest_flag(self, history: list[dict], today: dict, stats: dict) -> bool:
        if not self.cfg.use_iforest or len(history) < self.cfg.iforest_min_history:
            return False
        from sklearn.ensemble import IsolationForest

        def vec(r):
            return [(transform(k, r[k]) - stats[k][1]) / stats[k][2] for k in METRIC_KEYS]

        X = np.array([vec(h) for h in history])
        model = IsolationForest(n_estimators=60, random_state=0).fit(X)
        train = model.score_samples(X)
        return bool(model.score_samples(np.array([vec(today)]))[0] < train.min())

    def assess(self, rows: list[dict]) -> list[DayAssessment]:
        by_pet: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_pet[r["pet_id"]].append(r)
        out: list[DayAssessment] = []
        for pet_id, days in by_pet.items():
            days.sort(key=lambda r: r["date"])
            esc = Escalation(self.cfg)
            eligible: list[dict] = []   # days usable as "normal" reference
            recent: list[dict] = []     # the last gap_days days, not yet in the baseline
            for r in days:
                history = eligible[-self.cfg.window_days:]
                a = DayAssessment(r["date"], pet_id, r.get("pet_name", pet_id), r.get("species", ""),
                                  "learning", baseline_days=len(history))
                if len(history) < self.cfg.min_history:
                    eligible.append(r)
                    out.append(a)
                    continue
                stats = self._stats(history, r)
                z = {k: (transform(k, r[k]) - stats[k][1]) / stats[k][2] for k in METRIC_KEYS}
                a.level, runs = esc.update(z)
                a.unusual_combination = self._iforest_flag(history, r, stats)
                if a.unusual_combination and a.level == "normal":
                    a.level = "watch"
                a.reasons = _reasons(r, stats, z, runs, self.cfg.watch_z, self.cfg.support_z)
                a.band = {k: _band(k, stats[k], 2.0) for k in METRIC_KEYS}
                # A day joins the baseline gap_days later, and only if it was not a "consult" day,
                # so an ongoing change does not quietly become the new normal.
                recent.append((r, a.level))
                if len(recent) > self.cfg.gap_days:
                    old, lvl = recent.pop(0)
                    if lvl != "consult":
                        eligible.append(old)
                out.append(a)
        out.sort(key=lambda a: (a.pet_id, a.date))
        return out


def _inverse(key: str, y: float) -> float:
    return float(np.exp(y) - 1.0) if METRIC_BY_KEY[key].unit_zh != "次" else float(y)


def _band(key: str, stat: tuple[float, float, float], zmax: float) -> tuple[float, float, float]:
    usual, c, s = stat
    return (round(usual, 2), round(max(0.0, _inverse(key, c - zmax * s)), 2), round(_inverse(key, c + zmax * s), 2))


def _reasons(r: dict, stats: dict, z: dict, runs: dict, watch_z: float, support_z: float) -> list[Reason]:
    """Metrics worth mentioning: off today, or part of a multi-day drift."""
    picked = [k for k in METRIC_KEYS if abs(z[k]) >= watch_z or (runs[k] >= 2 and abs(z[k]) >= support_z)]
    out = []
    for k in sorted(picked, key=lambda k: -abs(z[k])):
        m, med = METRIC_BY_KEY[k], stats[k][0]
        out.append(Reason(k, m.label_zh, m.unit_zh, round(r[k], 2), round(med, 2),
                          round(100 * (r[k] - med) / med, 1) if med else 0.0,
                          round(z[k], 2), "up" if z[k] > 0 else "down", runs[k]))
    return out


class FixedThresholdDetector:
    """Comparison baseline: one "normal range" per metric per species, taken from a
    population of many healthy pets (the way a typical "alert when above X" product or a
    generic reference range works). Same escalation rules as the personal detector, so
    the only difference is *whose* normal the pet is compared with."""

    def __init__(self, population_rows: list[dict] | None = None, learning_days: int = 14,
                 config: DetectorConfig | None = None) -> None:
        if population_rows is None:
            from .simulate import random_population, simulate
            population_rows, _ = simulate(days=28, seed=99, pets=random_population(), episodes=[])
        self.learning_days = learning_days  # stay silent as long as the personal detector does
        self.cfg = config or DetectorConfig()
        by_sp: dict[str, list[dict]] = defaultdict(list)
        for r in population_rows:
            by_sp[r["species"]].append(r)
        self.norms = {}
        for sp, rs in by_sp.items():
            self.norms[sp] = {}
            for k in METRIC_KEYS:
                t = [transform(k, r[k]) for r in rs]
                self.norms[sp][k] = (float(np.median([r[k] for r in rs])), float(np.mean(t)), float(np.std(t)) or 1.0)

    def assess(self, rows: list[dict]) -> list[DayAssessment]:
        by_pet: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_pet[r["pet_id"]].append(r)
        out = []
        for pet_id, days in by_pet.items():
            days.sort(key=lambda r: r["date"])
            esc = Escalation(self.cfg)
            for i, r in enumerate(days):
                a = DayAssessment(r["date"], pet_id, r.get("pet_name", pet_id), r.get("species", ""), "learning")
                if i >= self.learning_days:
                    stats = self.norms[r.get("species", "")]
                    z = {k: (transform(k, r[k]) - stats[k][1]) / stats[k][2] for k in METRIC_KEYS}
                    a.level, runs = esc.update(z)
                    a.reasons = _reasons(r, stats, z, runs, self.cfg.watch_z, self.cfg.support_z)
                out.append(a)
        out.sort(key=lambda a: (a.pet_id, a.date))
        return out
