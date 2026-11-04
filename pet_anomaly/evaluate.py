"""Score detectors against the simulated episodes (ground truth)."""

from __future__ import annotations

from datetime import date, timedelta

from .detector import DayAssessment


def _d(s: str) -> date:
    return date.fromisoformat(s)


def evaluate(assessments: list[DayAssessment], episodes: list[dict], after_days: int = 3) -> dict:
    """
    * Each real episode: found or missed, and how many days after it started the first
      ``consult`` reminder came.
    * Harmless one-off episodes: whether they wrongly triggered ``consult``.
    * Ordinary days (outside every episode, plus ``after_days`` of recovery): how many
      got ``consult`` (false alarms) or ``watch`` reminders.
    """
    by_key = {(a.pet_id, a.date): a for a in assessments}
    busy: set[tuple[str, str]] = set()
    ep_results = []
    for ep in episodes:
        s, e = _d(ep["start_date"]), _d(ep["end_date"])
        span = [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1 + after_days)]
        busy.update((ep["pet_id"], d) for d in span)
        levels = [(d, by_key[(ep["pet_id"], d)].level) for d in span if (ep["pet_id"], d) in by_key]
        first_consult = next((d for d, lv in levels if lv == "consult"), None)
        first_watch = next((d for d, lv in levels if lv in ("watch", "consult")), None)
        ep_results.append({
            "pet_id": ep["pet_id"], "name_zh": ep["name_zh"], "expect_alert": ep["expect_alert"],
            "consult_found": first_consult is not None,
            "consult_delay_days": (_d(first_consult) - s).days if first_consult else None,
            "watch_delay_days": (_d(first_watch) - s).days if first_watch else None,
        })

    normal = [a for a in assessments if a.level != "learning" and (a.pet_id, a.date) not in busy]
    real = [r for r in ep_results if r["expect_alert"]]
    harmless = [r for r in ep_results if not r["expect_alert"]]
    delays = [r["consult_delay_days"] for r in real if r["consult_found"]]
    return {
        "episodes": ep_results,
        "real_episodes_found": f"{sum(r['consult_found'] for r in real)}/{len(real)}",
        "mean_consult_delay_days": round(sum(delays) / len(delays), 1) if delays else None,
        "harmless_episodes_escalated": sum(r["consult_found"] for r in harmless),
        "ordinary_days": len(normal),
        "false_consult_days": sum(a.level == "consult" for a in normal),
        "watch_days_on_ordinary_days": sum(a.level == "watch" for a in normal),
    }
