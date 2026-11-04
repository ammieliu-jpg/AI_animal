import csv
from datetime import date, timedelta

import numpy as np

from pet_anomaly.detector import DetectorConfig, FixedThresholdDetector, PersonalBaselineDetector
from pet_anomaly.evaluate import evaluate
from pet_anomaly.metrics import METRIC_KEYS, daily_from_events, read_daily, write_daily
from pet_anomaly.simulate import read_episodes, simulate, write_simulation

FAST = DetectorConfig(use_iforest=False)


def _steady_pet(days=40, seed=0, weekend_boost=1.0, shift=None):
    """One cat with mild noise; ``shift`` = (start_day, metric, multiplier)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(days):
        day = date(2026, 9, 1) + timedelta(days=d)
        r = {"date": day.isoformat(), "pet_id": "cat_1", "pet_name": "t", "species": "cat",
             "drinking_count": float(rng.poisson(12)), "drinking_min": rng.normal(4, 0.4),
             "eating_count": float(rng.poisson(8)), "eating_min": rng.normal(12, 1.2),
             "litter_count": float(rng.poisson(4)), "litter_min": rng.normal(6, 0.6),
             "active_min": rng.normal(100, 8) * (weekend_boost if day.weekday() >= 5 else 1.0),
             "resting_h": rng.normal(15, 0.4)}
        if shift and d >= shift[0]:
            r[shift[1]] *= shift[2]
        rows.append(r)
    return rows


def _levels(rows):
    return [a.level for a in PersonalBaselineDetector(FAST).assess(rows)]


def test_first_two_weeks_are_learning():
    lv = _levels(_steady_pet())
    assert lv[:14] == ["learning"] * 14
    assert "learning" not in lv[14:]


def test_steady_pet_gets_no_consult():
    for seed in range(5):
        assert "consult" not in _levels(_steady_pet(seed=seed))


def test_sustained_change_reaches_consult_quickly():
    lv = _levels(_steady_pet(shift=(25, "drinking_min", 2.0)))
    assert "consult" not in lv[:25]
    assert "consult" in lv[25:28]  # within 3 days


def test_one_day_spike_stays_at_watch():
    rows = _steady_pet()
    rows[25]["active_min"] *= 1.8
    lv = _levels(rows)
    assert lv[25] == "watch"
    assert "consult" not in lv


def test_weekend_routine_is_learned():
    # Owner home at weekends: +35 % activity. Personal baseline should not complain.
    lv = _levels(_steady_pet(days=56, weekend_boost=1.35))
    assert lv[28:].count("watch") + lv[28:].count("consult") <= 2


def test_reasons_are_readable():
    a = PersonalBaselineDetector(FAST).assess(_steady_pet(shift=(25, "drinking_min", 2.0)))[27]
    r = a.reasons[0]
    assert r.metric == "drinking_min" and r.direction == "up" and r.change_pct > 50
    assert a.to_dict()["level_zh"] == "建議諮詢獸醫"


def test_simulation_and_evaluation(tmp_path):
    paths = write_simulation(tmp_path, days=60, seed=7)
    rows = read_daily(paths["daily"])
    assert len(rows) == 3 * 60 and set(METRIC_KEYS) <= set(rows[0])
    eps = read_episodes(paths["episodes"])
    personal = evaluate(PersonalBaselineDetector(FAST).assess(rows), eps)
    fixed = evaluate(FixedThresholdDetector().assess(rows), eps)
    found = int(personal["real_episodes_found"].split("/")[0])
    assert found >= 2
    assert found >= int(fixed["real_episodes_found"].split("/")[0])


def test_daily_from_events(tmp_path):
    p = tmp_path / "events.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["pet_id", "behavior", "behavior_zh", "start_s", "end_s", "duration_s", "zone", "confidence"])
        w.writerow(["cat_1", "drinking", "喝水", 0, 30, 30, "water", 0.9])
        w.writerow(["cat_1", "drinking", "喝水", 100, 160, 60, "water", 0.9])
        w.writerow(["cat_1", "resting", "休息", 200, 3800, 3600, "", 0.9])
        w.writerow(["cat_2", "eating", "進食", 0, 120, 120, "food", 0.9])
    rows = {r["pet_id"]: r for r in daily_from_events(p, "2026-11-05")}
    assert rows["cat_1"]["drinking_count"] == 2 and rows["cat_1"]["drinking_min"] == 1.5
    assert rows["cat_1"]["resting_h"] == 1.0
    assert rows["cat_2"]["eating_min"] == 2.0
    write_daily(list(rows.values()), tmp_path / "daily.csv")
    assert len(read_daily(tmp_path / "daily.csv")) == 2


def test_fixed_threshold_misjudges_a_senior_cat():
    """A senior cat who always drinks a lot: the species-wide range keeps flagging her,
    her personal baseline does not."""
    rows = _steady_pet(days=40)
    for r in rows:
        r["drinking_count"] = r["drinking_count"] * 2.2
        r["drinking_min"] = r["drinking_min"] * 2.6
    fixed = [a.level for a in FixedThresholdDetector().assess(rows)][14:]
    personal = _levels(rows)[14:]
    assert fixed.count("normal") < personal.count("normal")
