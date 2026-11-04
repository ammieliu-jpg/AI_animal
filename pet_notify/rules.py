"""Wording rules that every message must pass, whoever wrote it (template or LLM).

Source: 注意事項 第 33–35 點 — the product may only organise information, remind and
support decisions. It must never diagnose, name a disease, suggest treatment, guarantee
an outcome, or talk the owner out of seeing a vet; and every personalised message must
show the official disclaimer where the owner reads it.
"""

from __future__ import annotations

import re

# 注意事項第 35 點, verbatim.
DISCLAIMER = (
    "本作品提供之資訊僅供輔助參考，不能取代獸醫師之診斷、治療或專業建議。"
    "貓犬之健康與營養需求可能因個體狀況而異，如有健康疑慮或需要調整飲食與照護方式，請諮詢合格獸醫師。"
)

# Terms that turn an observation into a medical claim, a treatment, a guarantee or a
# product pitch. Kept deliberately broad: a false positive only means a safer rewrite.
BANNED_TERMS: list[str] = [
    # diagnosis
    "診斷", "確診", "罹患", "患有", "得了", "疾病", "病症", "症狀", "病徵", "病情", "病變",
    # organs / named conditions
    "腎", "糖尿", "甲狀腺", "泌尿", "膀胱", "結石", "尿道", "感染", "發炎", "炎症", "癌", "腫瘤",
    "中毒", "肝", "心臟病", "胰", "腸胃炎", "脫水",
    # treatment
    "治療", "治癒", "療效", "療程", "處方", "藥", "打針", "手術", "預防",
    # certainty / guarantees / discouraging care
    "一定是", "肯定是", "確定是", "保證", "不用看醫生", "不需要就醫", "不必就醫", "沒有大礙", "不用擔心",
    # diet changes / products
    "換飼料", "調整飲食", "改吃", "處方飼料", "皇家", "Royal Canin", "royal canin",
]

_PATTERN = re.compile("|".join(re.escape(t) for t in BANNED_TERMS))


def violations(text: str) -> list[str]:
    """Banned terms found in ``text`` (empty list = OK)."""
    return sorted(set(_PATTERN.findall(text)))


MAX_LEN = {"title": 24, "body": 110, "next_step": 50}


def check_message(msg: dict) -> list[str]:
    """All problems with a message dict (title / body / next_step)."""
    problems = []
    for field, limit in MAX_LEN.items():
        text = msg.get(field, "")
        if not text:
            problems.append(f"{field} 是空的")
        elif len(text) > limit:
            problems.append(f"{field} 超過 {limit} 字（{len(text)} 字）")
        bad = violations(text)
        if bad:
            problems.append(f"{field} 含禁用詞：{'、'.join(bad)}")
    return problems
