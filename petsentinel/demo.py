"""One command for the whole Demo: video -> behaviour -> personal baseline -> reminders.

Output folder (portable, open ``index.html`` in a browser):

    index.html            overview page linking everything below (good for screen recording)
    vision/               module ①: events.csv, overview.jpg, annotated.mp4 (only with --video)
    sim/                  simulated 60-day history (clearly marked as simulated)
    anomaly/              module ②: alerts.json, trend_<pet>.png, evaluation.json
    notify/               module ③: notifications.json, preview.html, vet_report_<pet>.html

A short clip is not a full day, so it is *not* mixed into the daily history: the clip
shows how behaviour is recognised, the simulated history shows what happens over weeks.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path


def _e(s) -> str:
    return html.escape(str(s))


def _pick_demo_date(assessments) -> str:
    """The day with the most pets at 'consult', then 'watch'; latest on ties."""
    score: dict[str, tuple[int, int]] = {}
    for a in assessments:
        c, w = score.get(a.date, (0, 0))
        score[a.date] = (c + (a.level == "consult"), w + (a.level == "watch"))
    return max(score, key=lambda d: (score[d], d))


def run_vision(video: str, zones: str, out: Path, detector: str = "motion", model: str | None = None,
               fps: float = 5.0) -> dict:
    import cv2

    from pet_vision.detectors import MotionDetector, OnnxYoloDetector
    from pet_vision.pipeline import process_video, write_outputs
    from pet_vision.zones import load_zones

    cap = cv2.VideoCapture(video)
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    det = OnnxYoloDetector(model) if detector == "onnx" else MotionDetector(fps=fps)
    result = process_video(video, load_zones(zones, size), det, sample_fps=fps,
                           annotate_path=out / "annotated.mp4", overview_path=out / "overview.jpg")
    write_outputs(result, out)
    return {"pets": result.pet_ids, "events": [
        {"pet_id": e.pet_id, "behavior_zh": e.behavior.label_zh, "start_s": e.start_s, "end_s": e.end_s,
         "zone": e.zone or ""} for e in result.events]}


def run_demo(out_dir: str, video: str | None = None, zones: str | None = None, detector: str = "motion",
             model: str | None = None, days: int = 60, seed: int = 7, date: str | None = None,
             llm: bool = False, log=print) -> Path:
    from pet_anomaly.detector import FixedThresholdDetector, PersonalBaselineDetector
    from pet_anomaly.evaluate import evaluate
    from pet_anomaly.metrics import read_daily
    from pet_anomaly.report import plot_pet, write_alerts
    from pet_anomaly.simulate import read_episodes, write_simulation
    from pet_notify.compose import compose
    from pet_notify.html import preview_page, vet_report

    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    vision = None
    if video:
        if not zones:
            raise SystemExit("--zones is required with --video")
        log("① 視覺模組：分析影片…")
        (out / "vision").mkdir()
        vision = run_vision(video, zones, out / "vision", detector, model)
        log(f"   {len(vision['pets'])} 隻寵物、{len(vision['events'])} 段行為")

    log("② 異常偵測：產生模擬的每日紀錄並建立個體基線…")
    sim = write_simulation(out / "sim", days=days, seed=seed)
    rows = read_daily(sim["daily"])
    episodes = read_episodes(sim["episodes"])
    assessments = PersonalBaselineDetector().assess(rows)
    write_alerts(assessments, out / "anomaly" / "alerts.json")
    pets = sorted({r["pet_id"] for r in rows})
    for p in pets:
        plot_pet(rows, assessments, p, out / "anomaly" / f"trend_{p}.png", episodes, simulated=True)
    ev = {"personal_baseline": evaluate(assessments, episodes),
          "fixed_threshold": evaluate(FixedThresholdDetector().assess(rows), episodes)}
    (out / "anomaly" / "evaluation.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")

    date = date or _pick_demo_date(assessments)
    log(f"③ 白話提醒：{date}")
    writer = None
    if llm:
        from pet_notify.llm import ClaudeWriter
        writer = ClaudeWriter()
    daily = {(r["pet_id"], r["date"]): r for r in rows}
    today = [a for a in assessments if a.date == date]
    notes = [compose(a.to_dict(), daily.get((a.pet_id, a.date)), writer) for a in today]
    (out / "notify").mkdir()
    (out / "notify" / "notifications.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "notify" / "preview.html").write_text(preview_page(notes, simulated=True), encoding="utf-8")
    alerts = [a.to_dict() for a in assessments]
    reports = []
    for a in today:
        if a.level == "consult":
            name = f"vet_report_{a.pet_id}.html"
            (out / "notify" / name).write_text(
                vet_report(rows, alerts, assessments, a.pet_id, date, simulated=True), encoding="utf-8")
            reports.append((a.pet_name, name))

    (out / "index.html").write_text(_index(vision, pets, rows, ev, notes, reports, date), encoding="utf-8")
    log(f"\n完成 -> {out / 'index.html'}")
    return out / "index.html"


def _index(vision, pets, rows, ev, notes, reports, date) -> str:
    names = {r["pet_id"]: r["pet_name"] for r in rows}
    pb, ft = ev["personal_baseline"], ev["fixed_threshold"]
    if vision:
        ev_rows = "".join(f"<tr><td>{_e(e['pet_id'])}</td><td>{_e(e['behavior_zh'])}</td><td>{e['start_s']:.1f}–{e['end_s']:.1f} 秒</td>"
                          f"<td>{_e(e['zone'])}</td></tr>" for e in vision["events"])
        vision_html = f"""<img src="vision/overview.jpg" alt="影片分析總覽">
      <p class="cap">影片平均挑出的 6 個畫面：偵測框、寵物編號、目前行為。完整標註影片：<a href="vision/annotated.mp4">annotated.mp4</a></p>
      <table><thead><tr><th>寵物</th><th>行為</th><th>時間</th><th>區域</th></tr></thead><tbody>{ev_rows}</tbody></table>"""
    else:
        vision_html = "<p class='cap'>這次沒有提供影片（加上 <code>--video</code> 與 <code>--zones</code> 即可加入影片分析）。</p>"
    charts = "".join(f"<figure><img src='anomaly/trend_{p}.png' alt='{_e(names[p])} 趨勢圖'><figcaption>{_e(names[p])}</figcaption></figure>"
                     for p in pets)
    cards = "".join(f"<li style='--c:{ {'consult':'#e07a2e','watch':'#d9a521','normal':'#3f9d6b'}.get(n['level'],'#999') }'>"
                    f"<b>{_e(n['emoji'])} {_e(n['pet_name'])}：{_e(n['title'])}</b><br>{_e(n['body'])}</li>" for n in notes)
    rep = "".join(f"<a class='btn' href='notify/{_e(f)}'>📋 {_e(n)} 的就醫觀察紀錄</a>" for n, f in reports)
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>毛孩日常哨兵 Demo</title>
<style>
body {{ margin:0; background:#f4f1ec; color:#1f2328; font-family:"Microsoft JhengHei","PingFang TC","Noto Sans TC",system-ui,sans-serif; line-height:1.6; }}
main {{ max-width:1000px; margin:0 auto; padding:24px 16px 60px; }}
h1 {{ margin:0; font-size:28px; }} .sub {{ color:#5f6b76; margin:4px 0 20px; }}
section {{ background:#fff; border-radius:14px; padding:20px 22px; margin:18px 0; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
h2 {{ margin:0 0 10px; font-size:20px; }} h2 small {{ color:#5f6b76; font-weight:400; font-size:14px; }}
img {{ max-width:100%; border-radius:8px; border:1px solid #e3ddd3; }}
figure {{ margin:12px 0; }} figcaption, .cap {{ color:#5f6b76; font-size:13px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; margin-top:8px; }}
th, td {{ border-bottom:1px solid #e3ddd3; padding:6px 8px; text-align:left; }} th {{ background:#f6f3ee; }}
.flow {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; font-weight:600; }}
.flow span {{ background:#fff; border-radius:999px; padding:6px 14px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
ul.notes {{ list-style:none; padding:0; }} ul.notes li {{ border-left:5px solid var(--c); background:#faf8f4; padding:8px 12px; margin:8px 0; border-radius:6px; }}
.btn {{ display:inline-block; margin:6px 8px 0 0; padding:8px 14px; border-radius:8px; background:#2f5f8f; color:#fff; text-decoration:none; }}
.warn {{ background:#fff7e6; border-radius:8px; padding:8px 12px; font-size:13px; color:#7a5a12; }}
</style></head><body><main>
<h1>🐾 毛孩日常哨兵</h1>
<p class="sub">上班時也能察覺貓犬「跟平常不一樣」的 AI 照護提醒　·　預防保健</p>
<div class="flow"><span>📹 居家攝影機</span>→<span>① 看懂行為</span>→<span>② 和自己的平常比</span>→<span>③ 白話提醒</span>→<span>📋 就醫觀察紀錄</span></div>

<section><h2>① 看懂行為 <small>影片 → 吃、喝、如廁、休息、活動</small></h2>{vision_html}</section>

<section><h2>② 和自己的平常比 <small>個體化基線（模擬 60 天資料）</small></h2>
  <p class="warn">以下為模擬資料：放入已知的行為變化作為標準答案，用來驗證方法，不代表真實世界的準確率。</p>
  <table><thead><tr><th></th><th>個體化基線（本方案）</th><th>一般族群固定範圍</th></tr></thead><tbody>
  <tr><td>抓到的真實變化</td><td><b>{_e(pb['real_episodes_found'])}</b></td><td>{_e(ft['real_episodes_found'])}</td></tr>
  <tr><td>平均幾天後提醒「建議諮詢」</td><td>{_e(pb['mean_consult_delay_days'])} 天</td><td>{_e(ft['mean_consult_delay_days'])} 天</td></tr>
  <tr><td>普通日誤發「建議諮詢」</td><td>{pb['false_consult_days']} / {pb['ordinary_days']} 天</td><td>{ft['false_consult_days']} / {ft['ordinary_days']} 天</td></tr>
  </tbody></table>
  {charts}
</section>

<section><h2>③ 白話提醒 <small>{_e(date)} 的手機通知</small></h2>
  <ul class="notes">{cards}</ul>
  <a class="btn" href="notify/preview.html">📱 手機樣式預覽（含免責聲明）</a>{rep}
  <p class="cap">提醒等級由 ② 決定；文字只描述觀察到的變化，並通過禁用詞檢查（不診斷、不提病名、不建議用藥或換飼料），每則都附上規定的免責聲明。</p>
</section>
</main></body></html>"""
