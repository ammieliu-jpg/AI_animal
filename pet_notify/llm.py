"""Claude writes the daily message; the wording rules still have the last word.

Flow per message:
1. Send the facts (as JSON) with a system prompt that states the rules.
2. Ask for structured JSON output (title / body / next_step).
3. Check the result with ``rules.check_message``. If it breaks a rule, ask once more
   with the problems listed; if it still fails (or the API is unavailable / refuses),
   fall back to the deterministic template.

The model never sees anything but numbers already computed by module ②, and is told to
use only those numbers — it adds wording, not judgement. The reminder *level* is
decided by module ②, never by the model.
"""

from __future__ import annotations

import json

from .rules import MAX_LEN, check_message

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = f"""你是寵物照護 App「毛孩日常哨兵」的提醒小幫手。飼主白天在上班，會在手機上快速瞄一眼你的訊息。
你會收到一隻寵物今天的行為觀察結果（JSON），由居家攝影機自動統計、再由系統和這隻寵物自己的平常模式比較而來。

請用台灣常用的繁體中文，寫一則簡短、溫和、具體的提醒：
- title：{MAX_LEN['title']} 字以內，說出重點。
- body：{MAX_LEN['body']} 字以內，用資料裡的數字描述「觀察到什麼變化、持續幾天」。
- next_step：{MAX_LEN['next_step']} 字以內，一個飼主今天就能做的具體行動。

語氣依提醒等級（level）而定，等級已由系統決定，不可自行提高或降低：
- normal：輕鬆報平安。
- watch：提到哪裡不一樣，請飼主回家後多留意，不要製造緊張。
- consult：清楚說明變化已持續幾天，建議近期聯絡獸醫，並帶上 App 裡的「就醫觀察紀錄」。不要淡化。

必須遵守（這是法規與比賽規定）：
- 只描述觀察到的行為與數字，不推測原因。不提任何疾病、器官、症狀名稱，不寫「可能是…」。
- 不做診斷，不建議用藥、治療或更換飲食，不推薦任何產品或品牌。
- 不保證結果，不說「沒事」「不用擔心」「不用看醫生」。
- 只使用資料裡出現的數字，不要自己編數字。
- 不要寫免責聲明，App 會自動附上。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "next_step": {"type": "string"},
    },
    "required": ["title", "body", "next_step"],
    "additionalProperties": False,
}


def facts(a: dict, daily: dict | None = None) -> dict:
    """The only information the model gets."""
    out = {
        "pet_name": a["pet_name"],
        "species": {"cat": "貓", "dog": "狗"}.get(a.get("species", ""), a.get("species", "")),
        "date": a["date"],
        "level": a["level"],
        "level_zh": a.get("level_zh", ""),
        "changes": [
            {"item": r["label_zh"], "today": r["today"], "usual": r["usual"], "unit": r["unit_zh"],
             "change_pct": r["change_pct"], "direction": "比平常多" if r["direction"] == "up" else "比平常少",
             "days_in_a_row": r["days_in_row"]}
            for r in a.get("reasons", [])[:3]
        ],
        "unusual_combination": a.get("unusual_combination", False),
    }
    if daily:
        out["today_summary"] = {k: daily[k] for k in ("drinking_count", "eating_count", "litter_count", "active_min")
                                if k in daily}
    return out


class ClaudeWriter:
    def __init__(self, client=None, model: str = MODEL, effort: str = "low") -> None:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort  # short, rule-bound copywriting: low effort is enough

    def _ask(self, content: str) -> dict | None:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=2000,
            # If a safety classifier declines, the API retries on Anthropic's recommended
            # fallback model inside the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            return None
        text = next((b.text for b in response.content if b.type == "text"), None)
        return json.loads(text) if text else None

    def write(self, a: dict, daily: dict | None = None) -> tuple[dict | None, list[str]]:
        """Returns (message or None, problems from the last attempt)."""
        base = "今天的觀察資料如下：\n" + json.dumps(facts(a, daily), ensure_ascii=False, indent=2)
        msg = self._ask(base)
        problems = check_message(msg) if msg else ["模型沒有回覆"]
        if msg and problems:
            retry = base + "\n\n上一版提醒有這些問題，請修正後重寫：\n- " + "\n- ".join(problems)
            msg = self._ask(retry)
            problems = check_message(msg) if msg else ["模型沒有回覆"]
        return (msg if msg and not problems else None), problems
