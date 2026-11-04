"""Deterministic messages: work offline, cost nothing, and are the fallback whenever
the LLM is unavailable or its output fails the wording rules."""

from __future__ import annotations


def fmt(value: float, unit: str) -> str:
    if unit == "次":
        # Usual values are medians and can be x.5; show them as such, not rounded away.
        return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"
    return f"{value:.1f}"


def reason_phrase(r: dict) -> str:
    """e.g. 「喝水次數 37 次，平常約 16 次（多 131%）」"""
    unit = r["unit_zh"]
    more_less = "多" if r["direction"] == "up" else "少"
    return (f"{r['label_zh']} {fmt(r['today'], unit)} {unit}，平常約 {fmt(r['usual'], unit)} {unit}"
            f"（{more_less} {abs(r['change_pct']):.0f}%）")


def build(a: dict, daily: dict | None = None) -> dict:
    """Message for one day assessment (``alerts.json`` item). ``daily`` is that day's
    metrics row, used for the "all normal" summary."""
    name = a["pet_name"]
    level = a["level"]
    reasons = a.get("reasons", [])

    if level == "learning":
        n = a.get("baseline_days", 0) + 1
        return {
            "title": f"正在認識{name}的日常",
            "body": f"系統正在學習{name}平常的作息（第 {min(n, 14)}/14 天），這段期間先不發提醒。",
            "next_step": "照平常方式照顧就好",
        }

    if level == "normal":
        if daily:
            body = (f"今天喝水 {fmt(daily['drinking_count'], '次')} 次、進食 {fmt(daily['eating_count'], '次')} 次、"
                    f"活動約 {daily['active_min']:.0f} 分鐘，和平常差不多。")
        else:
            body = "今天的喝水、進食、如廁和活動都和平常差不多。"
        return {"title": f"{name}今天和平常一樣", "body": body, "next_step": "回家後記得陪牠玩一下"}

    if level == "watch":
        if reasons:
            body = f"{reason_phrase(reasons[0])}。偶爾一天不同很常見，先多留意就好。"
        else:
            body = "今天幾項行為的組合和平常不太一樣，單一項目變化不大。"
        return {
            "title": f"{name}今天有點不一樣",
            "body": body,
            "next_step": "回家後看看牠的精神和食慾",
        }

    # consult
    days = max((r.get("days_in_row", 1) for r in reasons), default=1)
    main = reasons[0] if reasons else None
    title = (f"{name}{main['label_zh']}連續 {days} 天偏{'多' if main['direction'] == 'up' else '少'}"
             if main else f"{name}最近幾天和平常不同")
    parts = [reason_phrase(r) for r in reasons[:2]]
    body = "；".join(parts) + f"。這樣的變化已持續 {days} 天。" if parts else "最近幾天多項行為持續和平常不同。"
    return {
        "title": title[:24],
        "body": body,
        "next_step": "建議近期聯絡獸醫，並帶上就醫觀察紀錄",
    }
