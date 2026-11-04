import json
from types import SimpleNamespace

import pytest

from pet_anomaly.detector import PersonalBaselineDetector
from pet_anomaly.simulate import simulate
from pet_notify import template
from pet_notify.compose import compose
from pet_notify.html import preview_page, vet_report
from pet_notify.llm import ClaudeWriter, facts
from pet_notify.rules import DISCLAIMER, check_message, violations


@pytest.fixture(scope="module")
def sim():
    rows, _ = simulate(seed=7)
    assessments = PersonalBaselineDetector().assess(rows)
    return rows, assessments


def test_banned_terms_are_caught():
    assert violations("小黑可能是腎臟有問題") == ["腎"]
    assert violations("建議換飼料") == ["換飼料"]
    assert violations("小黑今天喝水比平常多") == []
    assert check_message({"title": "a", "body": "保證沒事", "next_step": "b"})


def test_template_messages_pass_rules_for_every_day(sim):
    rows, assessments = sim
    daily = {(r["pet_id"], r["date"]): r for r in rows}
    for a in assessments:
        msg = template.build(a.to_dict(), daily[(a.pet_id, a.date)])
        assert check_message(msg) == [], (a.date, a.pet_id, msg)


def test_consult_message_says_what_and_how_long(sim):
    _, assessments = sim
    a = next(x for x in assessments if x.level == "consult" and x.pet_id == "cat_2").to_dict()
    msg = template.build(a)
    assert "喝水" in msg["title"] and "天" in msg["title"]
    assert "獸醫" in msg["next_step"]


def test_compose_always_attaches_disclaimer(sim):
    _, assessments = sim
    n = compose(assessments[30].to_dict())
    assert n["disclaimer"] == DISCLAIMER and n["source"] == "template"


class FakeClient:
    """Stands in for anthropic.Anthropic(): returns queued JSON answers, records requests."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        ans = self.answers.pop(0)
        if ans == "REFUSE":
            return SimpleNamespace(stop_reason="refusal", content=[])
        if isinstance(ans, Exception):
            raise ans
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(ans, ensure_ascii=False))])


GOOD = {"title": "小黑最近喝水變多了", "body": "這三天喝水次數約 30 次，平常約 16 次。", "next_step": "建議近期聯絡獸醫"}
BAD = {"title": "小黑可能腎臟不好", "body": "喝水變多可能是糖尿病。", "next_step": "建議換飼料"}


def _consult(sim):
    return next(x for x in sim[1] if x.level == "consult").to_dict()


def test_llm_message_used_when_it_follows_rules(sim):
    client = FakeClient([GOOD])
    n = compose(_consult(sim), writer=ClaudeWriter(client=client))
    assert n["source"] == "llm" and n["title"] == GOOD["title"]
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["fallbacks"] == "default"


def test_llm_rule_break_is_retried_then_accepted(sim):
    client = FakeClient([BAD, GOOD])
    n = compose(_consult(sim), writer=ClaudeWriter(client=client))
    assert n["source"] == "llm" and len(client.requests) == 2
    assert "禁用詞" in client.requests[1]["messages"][0]["content"]


def test_llm_falls_back_to_template(sim):
    for answers in ([BAD, BAD], ["REFUSE"], [RuntimeError("no network")]):
        n = compose(_consult(sim), writer=ClaudeWriter(client=FakeClient(answers)))
        assert n["source"] == "template"
        assert check_message(n) == []


def test_llm_only_sees_module2_facts(sim):
    f = facts(_consult(sim))
    assert set(f) <= {"pet_name", "species", "date", "level", "level_zh", "changes", "unusual_combination",
                      "today_summary"}
    assert f["level"] == "consult" and f["changes"]


def test_html_outputs(sim):
    rows, assessments = sim
    notes = [compose(a.to_dict()) for a in assessments[40:43]]
    page = preview_page(notes, simulated=True)
    assert page.count(DISCLAIMER) == 3 and "模擬資料" in page
    alerts = [a.to_dict() for a in assessments]
    report = vet_report(rows, alerts, assessments, "cat_2", "2026-10-14", simulated=True)
    assert "就醫觀察紀錄" in report and DISCLAIMER in report and "data:image/png;base64," in report
    assert violations(report.split("<h2>說明</h2>")[0]) == []
