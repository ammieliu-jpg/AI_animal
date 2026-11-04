"""Simulated daily behaviour for several pets, with known "something changed" episodes.

We have no months of real home-camera data, so this produces a reproducible dataset to
develop and evaluate module ② against. It must always be labelled as simulated data.

Parameter sources (order of magnitude only):
* Cats drink in many short bouts; typical intake ~40–60 ml/kg/day (vet references
  cited in docs/proposal-plan.md). Bout counts/durations here are illustrative.
* Adult cats rest/sleep ~12–16 h a day, seniors more.

Episodes are described only by *what changes in behaviour*; they are not diseases.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from .metrics import write_daily


@dataclass
class PetProfile:
    pet_id: str
    name: str
    species: str
    # mean bouts per day, mean seconds per bout
    drinking: tuple[float, float]
    eating: tuple[float, float]
    litter: tuple[float, float]
    active_min: float
    resting_h: float
    weekend_active_boost: float = 1.15  # owner at home -> more play
    scheduled_meals: bool = False       # fed fixed meals (count barely varies) vs free feeding


@dataclass
class Episode:
    pet_id: str
    start_day: int
    days: int
    name_zh: str
    # metric -> multiplier at full strength (per-bout duration multipliers use "<b>_bout")
    effects: dict[str, float]
    ramp_days: int = 0          # reach full strength gradually
    expect_alert: bool = True   # False = harmless one-off; ideally no "consult" reminder
    extra: dict = field(default_factory=dict)


def default_pets() -> list[PetProfile]:
    return [
        PetProfile("cat_1", "橘子", "cat", drinking=(10, 20), eating=(9, 90), litter=(4, 90),
                   active_min=110, resting_h=15.0),
        # Senior cat: naturally drinks more and rests more. A fixed, species-wide
        # threshold keeps flagging her on perfectly normal days.
        PetProfile("cat_2", "小黑", "cat", drinking=(17, 26), eating=(6, 120), litter=(5, 100),
                   active_min=50, resting_h=18.0, weekend_active_boost=1.05),
        PetProfile("dog_1", "Lucky", "dog", drinking=(8, 40), eating=(2, 240), litter=(3, 60),
                   active_min=180, resting_h=14.0, weekend_active_boost=1.3, scheduled_meals=True),
    ]


def random_population(n_per_species: int = 100, seed: int = 123) -> list[PetProfile]:
    """Many random, healthy pets: what a species-wide "normal range" is based on.
    Ranges are illustrative, wide enough to cover young and senior animals."""
    rng = np.random.default_rng(seed)
    u = rng.uniform
    pets = []
    for i in range(n_per_species):
        pets.append(PetProfile(f"popcat_{i}", f"cat{i}", "cat",
                               drinking=(u(8, 18), u(15, 30)), eating=(u(5, 12), u(60, 130)),
                               litter=(u(3, 6), u(60, 120)), active_min=u(40, 140),
                               resting_h=u(13, 18.5), weekend_active_boost=u(1.0, 1.2)))
        pets.append(PetProfile(f"popdog_{i}", f"dog{i}", "dog",
                               drinking=(u(5, 12), u(30, 50)), eating=(float(rng.integers(1, 4)), u(150, 300)),
                               litter=(u(2, 5), u(40, 80)), active_min=u(90, 240),
                               resting_h=u(12, 16), weekend_active_boost=u(1.0, 1.35), scheduled_meals=True))
    return pets


def default_episodes() -> list[Episode]:
    return [
        Episode("cat_1", 15, 1, "家裡來客人，比平常活潑", {"active_min": 1.45, "resting_h": 0.93},
                expect_alert=False),
        Episode("cat_1", 30, 4, "食慾下降、活動量減少",
                {"eating_count": 0.5, "eating_bout": 0.8, "active_min": 0.5, "resting_h": 1.12}),
        Episode("cat_2", 38, 14, "喝水與如廁次數逐漸增加",
                {"drinking_count": 1.9, "drinking_bout": 1.2, "litter_count": 1.6}, ramp_days=7),
        Episode("dog_1", 47, 3, "如廁次數突增、每次時間變短",
                {"litter_count": 2.8, "litter_bout": 0.4}),
    ]


def _strength(ep: Episode, day: int) -> float:
    k = day - ep.start_day
    if k < 0 or k >= ep.days:
        return 0.0
    if ep.ramp_days and k < ep.ramp_days:
        return (k + 1) / ep.ramp_days
    return 1.0


def _mult(episodes: list[Episode], pet_id: str, day: int, key: str) -> float:
    m = 1.0
    for ep in episodes:
        if ep.pet_id == pet_id and key in ep.effects:
            s = _strength(ep, day)
            m *= 1.0 + (ep.effects[key] - 1.0) * s
    return m


def _bouts(rng, mean_n: float, mean_s: float, n_mult: float, s_mult: float,
           fixed: bool = False) -> tuple[float, float]:
    if fixed:
        # Scheduled meals: the planned number, occasionally one more or one fewer.
        n = int(round(mean_n * n_mult)) + int(rng.choice([-1, 0, 0, 0, 0, 0, 0, 0, 0, 1]))
        n = max(0, n)
    else:
        n = int(rng.poisson(max(0.1, mean_n * n_mult * rng.lognormal(0, 0.08))))
    secs = rng.lognormal(np.log(mean_s * s_mult), 0.3, size=n).sum() if n else 0.0
    return float(n), float(secs / 60)


def simulate(days: int = 60, start: date = date(2026, 9, 1), seed: int = 7,
             pets: list[PetProfile] | None = None,
             episodes: list[Episode] | None = None) -> tuple[list[dict], list[Episode]]:
    rng = np.random.default_rng(seed)
    pets = pets or default_pets()
    episodes = default_episodes() if episodes is None else episodes
    rows = []
    for p in pets:
        for d in range(days):
            day = start + timedelta(days=d)
            weekend = day.weekday() >= 5
            row = {"date": day.isoformat(), "pet_id": p.pet_id, "pet_name": p.name, "species": p.species}
            for b in ("drinking", "eating", "litter"):
                mean_n, mean_s = getattr(p, b)
                n, mins = _bouts(rng, mean_n, mean_s,
                                 _mult(episodes, p.pet_id, d, f"{b}_count"),
                                 _mult(episodes, p.pet_id, d, f"{b}_bout"),
                                 fixed=(b == "eating" and p.scheduled_meals))
                row[f"{b}_count"], row[f"{b}_min"] = n, mins
            act = p.active_min * (p.weekend_active_boost if weekend else 1.0)
            row["active_min"] = float(max(0, rng.normal(act, act * 0.12)) * _mult(episodes, p.pet_id, d, "active_min"))
            rest = p.resting_h * (0.97 if weekend else 1.0)
            row["resting_h"] = float(min(23, max(0, rng.normal(rest, 0.6)) * _mult(episodes, p.pet_id, d, "resting_h")))
            rows.append(row)
    return rows, episodes


def write_simulation(out_dir: str | Path, days: int = 60, seed: int = 7) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, episodes = simulate(days=days, seed=seed)
    start = date.fromisoformat(rows[0]["date"])
    daily = out / "daily.csv"
    write_daily(rows, daily)
    truth = out / "episodes.csv"
    with truth.open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["pet_id", "start_date", "end_date", "name_zh", "expect_alert"])
        for ep in episodes:
            wr.writerow([ep.pet_id, (start + timedelta(days=ep.start_day)).isoformat(),
                         (start + timedelta(days=ep.start_day + ep.days - 1)).isoformat(),
                         ep.name_zh, int(ep.expect_alert)])
    return {"daily": daily, "episodes": truth}


def read_episodes(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig") as f:
        return [{**r, "expect_alert": r["expect_alert"] == "1"} for r in csv.DictReader(f)]
