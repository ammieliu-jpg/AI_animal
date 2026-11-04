"""Build the final notification for each pet: message + level + disclaimer."""

from __future__ import annotations

import logging

from . import template
from .rules import DISCLAIMER, check_message

log = logging.getLogger(__name__)

LEVEL_EMOJI = {"learning": "⚪", "normal": "🟢", "watch": "🟡", "consult": "🟠"}


def compose(a: dict, daily: dict | None = None, writer=None) -> dict:
    """``writer``: an ``llm.ClaudeWriter`` (optional). Without it, or if it fails the
    wording rules, the template message is used."""
    msg, source, notes = None, "template", []
    if writer is not None and a["level"] != "learning":
        try:
            msg, notes = writer.write(a, daily)
            if msg:
                source = "llm"
        except Exception as e:  # network, auth, rate limit…: never block the reminder
            log.warning("LLM unavailable, using template: %s", e)
            notes = [f"LLM 無法使用：{type(e).__name__}"]
    if msg is None:
        msg = template.build(a, daily)
        problems = check_message(msg)
        if problems:  # should never happen; the template is tested
            raise ValueError(f"template message breaks the rules: {problems}")
    return {
        "date": a["date"],
        "pet_id": a["pet_id"],
        "pet_name": a["pet_name"],
        "level": a["level"],
        "level_zh": a.get("level_zh", ""),
        "emoji": LEVEL_EMOJI.get(a["level"], ""),
        **msg,
        "disclaimer": DISCLAIMER,
        "source": source,
        "notes": notes,
    }
