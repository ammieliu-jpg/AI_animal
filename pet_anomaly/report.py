"""Outputs of module ②: alerts.json (input for module ③) and trend charts."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .detector import DayAssessment
from .metrics import METRIC_BY_KEY

LEVEL_COLORS = {"watch": "#f2c14e", "consult": "#e8833a"}
CHART_METRICS = ["drinking_count", "eating_min", "litter_count", "active_min"]
CJK_FONTS = ["Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "Heiti TC",
             "WenQuanYi Zen Hei", "DejaVu Sans"]


def write_alerts(assessments: list[DayAssessment], path: str | Path, only_latest: bool = False) -> Path:
    """JSON list of day assessments. ``only_latest`` keeps each pet's most recent day
    (what a daily notification would use)."""
    items = assessments
    if only_latest:
        latest: dict[str, DayAssessment] = {}
        for a in assessments:
            if a.pet_id not in latest or a.date > latest[a.pet_id].date:
                latest[a.pet_id] = a
        items = list(latest.values())
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([a.to_dict() for a in items], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def plot_pet(rows: list[dict], assessments: list[DayAssessment], pet_id: str, path: str | Path,
             episodes: list[dict] | None = None, simulated: bool = False, dpi: int = 130) -> Path:
    import logging

    import matplotlib
    matplotlib.use("Agg")
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # quiet missing-font fallbacks
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False

    days = sorted((r for r in rows if r["pet_id"] == pet_id), key=lambda r: r["date"])
    ass = {a.date: a for a in assessments if a.pet_id == pet_id}
    x = [datetime.fromisoformat(r["date"]) for r in days]
    name = days[0].get("pet_name", pet_id)

    fig, axes = plt.subplots(len(CHART_METRICS), 1, figsize=(10, 2.1 * len(CHART_METRICS) + 0.8),
                             sharex=True)
    for ax, k in zip(axes, CHART_METRICS):
        m = METRIC_BY_KEY[k]
        for r, d in zip(days, x):
            lv = ass[r["date"]].level if r["date"] in ass else "learning"
            if lv in LEVEL_COLORS:
                ax.axvspan(d - timedelta(hours=12), d + timedelta(hours=12), color=LEVEL_COLORS[lv],
                           alpha=0.35, lw=0)
        bx = [d for r, d in zip(days, x) if ass.get(r["date"]) and ass[r["date"]].band]
        if bx:
            bands = [ass[r["date"]].band[k] for r in days if ass.get(r["date"]) and ass[r["date"]].band]
            ax.set_ylim(bottom=0, top=max(max(r[k] for r in days), max(b[2] for b in bands)) * 1.08)
            ax.fill_between(bx, [b[1] for b in bands], [b[2] for b in bands], color="#8fb3d9", alpha=0.3,
                            lw=0, label="這隻寵物的平常範圍")
            ax.plot(bx, [b[0] for b in bands], color="#4a78a8", lw=1, ls="--", label="平常值")
        ax.plot(x, [r[k] for r in days], color="#222", lw=1.4, marker="o", ms=2.5, label="每日紀錄")
        ax.set_ylabel(f"{m.label_zh}\n({m.unit_zh})", fontsize=9)
        ax.grid(alpha=0.25)
        for ep in episodes or []:
            if ep["pet_id"] == pet_id:
                s, e = datetime.fromisoformat(ep["start_date"]), datetime.fromisoformat(ep["end_date"])
                ax.axvspan(s - timedelta(hours=12), e + timedelta(hours=12), fill=False, hatch="///",
                           ec="#888", lw=0)
    learn = [d for r, d in zip(days, x) if ass.get(r["date"]) and ass[r["date"]].level == "learning"]
    if learn:
        axes[0].annotate("建立基線中", xy=(learn[len(learn) // 2], 1.02), xycoords=("data", "axes fraction"),
                         ha="center", fontsize=8, color="#666")
    axes[0].legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    title = f"{name}（{pet_id}）每日行為趨勢"
    if simulated:
        title += "　※模擬資料"
    fig.suptitle(title, fontsize=13)
    from matplotlib.patches import Patch
    handles = [Patch(color=LEVEL_COLORS["watch"], alpha=0.5, label="提醒：留意"),
               Patch(color=LEVEL_COLORS["consult"], alpha=0.5, label="提醒：建議諮詢獸醫")]
    if episodes:
        handles.append(Patch(fill=False, hatch="///", ec="#888", label="模擬中放入的變化（標準答案）"))
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
