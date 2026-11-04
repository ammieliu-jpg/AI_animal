"""Static HTML outputs: a phone-style notification preview (for the Demo) and a
printable 「就醫觀察紀錄」 the owner can show the vet. Both are self-contained files."""

from __future__ import annotations

import base64
import html
import tempfile
from datetime import date, timedelta
from pathlib import Path

from .template import reason_phrase

LEVEL_COLOR = {"learning": "#9aa3ad", "normal": "#3f9d6b", "watch": "#d9a521", "consult": "#e07a2e"}

_BASE_CSS = """
:root { --fg:#1f2328; --muted:#5f6b76; --bg:#f4f1ec; --card:#fff; --line:#e3ddd3; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font-family:"Microsoft JhengHei","PingFang TC","Noto Sans TC",system-ui,sans-serif; line-height:1.55; }
"""


def _e(s) -> str:
    return html.escape(str(s))


def preview_page(notifications: list[dict], title: str = "毛孩日常哨兵", simulated: bool = False) -> str:
    cards = []
    for n in notifications:
        color = LEVEL_COLOR.get(n["level"], "#888")
        cards.append(f"""
      <article class="card" style="--accent:{color}">
        <header><span class="pet">{_e(n['pet_name'])}</span>
          <span class="badge">{_e(n['emoji'])} {_e(n['level_zh'])}</span></header>
        <h2>{_e(n['title'])}</h2>
        <p>{_e(n['body'])}</p>
        <p class="next">👉 {_e(n['next_step'])}</p>
        <p class="disclaimer">{_e(n['disclaimer'])}</p>
        <footer>{_e(n['date'])}　·　{'AI 撰寫' if n['source'] == 'llm' else '系統範本'}</footer>
      </article>""")
    sim = '<p class="sim">※ 本頁資料為模擬資料</p>' if simulated else ""
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{_BASE_CSS}
.phone {{ max-width:390px; margin:24px auto; padding:18px 14px 28px; background:#fbfaf7;
         border:1px solid var(--line); border-radius:28px; box-shadow:0 10px 30px rgba(0,0,0,.08); }}
.top {{ display:flex; justify-content:space-between; align-items:baseline; padding:4px 6px 12px; }}
.top h1 {{ font-size:18px; margin:0; }} .top span {{ color:var(--muted); font-size:13px; }}
.card {{ background:var(--card); border-radius:16px; padding:14px 16px; margin:12px 0;
        border-left:6px solid var(--accent); box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.card header {{ display:flex; justify-content:space-between; align-items:center; font-size:13px; color:var(--muted); }}
.badge {{ color:var(--accent); font-weight:700; }}
.pet {{ font-weight:700; color:var(--fg); }}
.card h2 {{ font-size:17px; margin:6px 0 4px; }}
.card p {{ margin:4px 0; font-size:14.5px; }}
.next {{ font-weight:600; }}
.disclaimer {{ margin-top:10px !important; font-size:11.5px !important; color:var(--muted);
              background:#f6f3ee; border-radius:8px; padding:6px 8px; }}
.card footer {{ font-size:11.5px; color:var(--muted); margin-top:6px; }}
.sim {{ text-align:center; color:var(--muted); font-size:12px; }}
</style></head>
<body><main class="phone">
  <div class="top"><h1>🐾 {_e(title)}</h1><span>今日提醒</span></div>
  {''.join(cards)}
  {sim}
</main></body></html>"""


def _chart_png(rows, assessments, pet_id, start: str, end: str, simulated: bool) -> str:
    from pet_anomaly.report import plot_pet

    sub = [r for r in rows if start <= r["date"] <= end]
    with tempfile.TemporaryDirectory() as d:
        p = plot_pet(sub, assessments, pet_id, Path(d) / "c.png", simulated=simulated)
        return base64.b64encode(p.read_bytes()).decode()


def vet_report(rows: list[dict], alerts: list[dict], assessments, pet_id: str, end_date: str,
               days: int = 14, simulated: bool = False) -> str:
    """``alerts``: alerts.json items; ``assessments``: the same as DayAssessment objects (for the chart)."""
    from pet_anomaly.metrics import METRICS

    end = date.fromisoformat(end_date)
    start = (end - timedelta(days=days - 1)).isoformat()
    pet_rows = sorted((r for r in rows if r["pet_id"] == pet_id and start <= r["date"] <= end_date),
                      key=lambda r: r["date"])
    pet_alerts = [a for a in alerts if a["pet_id"] == pet_id and start <= a["date"] <= end_date]
    if not pet_rows:
        raise ValueError(f"no data for {pet_id} between {start} and {end_date}")
    latest = next((a for a in reversed(pet_alerts) if a.get("band")), None)
    name, species = pet_rows[0].get("pet_name", pet_id), pet_rows[0].get("species", "")
    last3 = pet_rows[-3:]

    trs = []
    for m in METRICS:
        usual = latest["band"][m.key][0] if latest else None
        recent = sum(r[m.key] for r in last3) / len(last3)
        change = f"{100 * (recent - usual) / usual:+.0f}%" if usual else "—"
        flag = ""
        if latest:
            lo, hi = latest["band"][m.key][1], latest["band"][m.key][2]
            flag = " class='off'" if recent < lo or recent > hi else ""
        daily_vals = "、".join(f"{r[m.key]:.0f}" if m.unit_zh == "次" else f"{r[m.key]:.1f}" for r in pet_rows)
        trs.append(f"<tr{flag}><td>{_e(m.label_zh)}（{_e(m.unit_zh)}）</td>"
                   f"<td>{'' if usual is None else f'{usual:.1f}'}</td><td>{recent:.1f}</td><td>{change}</td>"
                   f"<td class='vals'>{daily_vals}</td></tr>")

    log_items = []
    for a in pet_alerts:
        if a["level"] in ("watch", "consult"):
            why = "；".join(reason_phrase(r) for r in a.get("reasons", [])[:2]) or "多項指標的組合和平常不同"
            log_items.append(f"<li><b style='color:{LEVEL_COLOR[a['level']]}'>{_e(a['date'])}　{_e(a['level_zh'])}</b>"
                             f"　{_e(why)}</li>")
    log_html = "<ul>" + "".join(log_items) + "</ul>" if log_items else "<p>這段期間沒有提醒。</p>"
    chart = _chart_png(rows, assessments, pet_id, (end - timedelta(days=44)).isoformat(), end_date, simulated)
    species_zh = {"cat": "貓", "dog": "狗"}.get(species, species)
    from .rules import DISCLAIMER
    sim = "<p class='sim'>※ 本紀錄使用模擬資料</p>" if simulated else ""
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(name)} 就醫觀察紀錄</title>
<style>{_BASE_CSS}
main {{ max-width:860px; margin:24px auto; background:var(--card); padding:28px 32px; border-radius:12px;
       box-shadow:0 2px 10px rgba(0,0,0,.06); }}
h1 {{ margin:0 0 4px; font-size:24px; }} h2 {{ font-size:17px; margin:22px 0 8px; border-bottom:1px solid var(--line); padding-bottom:4px; }}
.meta {{ color:var(--muted); font-size:14px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th, td {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }}
th {{ background:#f6f3ee; font-weight:600; }}
tr.off td {{ background:#fdf0e4; }}
td.vals {{ color:var(--muted); font-size:12.5px; }}
img {{ width:100%; border:1px solid var(--line); border-radius:8px; }}
.note, .sim {{ color:var(--muted); font-size:13px; }}
.disclaimer {{ background:#f6f3ee; border-radius:8px; padding:10px 12px; font-size:13px; color:var(--muted); }}
@media print {{ body {{ background:#fff; }} main {{ box-shadow:none; margin:0; }} }}
</style></head>
<body><main>
  <h1>🐾 {_e(name)} 就醫觀察紀錄</h1>
  <p class="meta">{_e(species_zh)}　·　觀察期間 {_e(start)} ～ {_e(end_date)}（{days} 天）　·　資料來源：居家攝影機自動統計</p>
  <p class="note">以下為系統自動統計的行為數據，以及和這隻寵物自己平常模式的比較，供獸醫參考。系統只負責整理數據，評估請交由獸醫師。</p>
  <h2>行為統計</h2>
  <table><thead><tr><th>項目</th><th>平常值</th><th>最近 3 天平均</th><th>變化</th><th>每日紀錄（由舊到新）</th></tr></thead>
  <tbody>{''.join(trs)}</tbody></table>
  <p class="note">底色標示：最近 3 天平均超出這隻寵物的平常範圍。</p>
  <h2>提醒紀錄</h2>
  {log_html}
  <h2>近期趨勢</h2>
  <img alt="{_e(name)} 每日行為趨勢圖" src="data:image/png;base64,{chart}">
  <h2>說明</h2>
  <p class="disclaimer">{_e(DISCLAIMER)}</p>
  {sim}
</main></body></html>"""
