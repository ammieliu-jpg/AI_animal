"""Batch evaluation of module ① on a folder of videos, against hand-made labels.

Folder layout (``videos/``)::

    videos/
      sources.csv          one row per video: where it came from (required)
      labels.csv           hand-labelled behaviour segments (required for scoring)
      cat_drinking_01.mp4
      cat_drinking_01_zones.json   bowls / litter box for that video (see `prepare`)
      ...

Every number in the report comes from comparing the system's output with
``labels.csv``. Videos without a source row, without labels or without zones are
listed as excluded instead of being silently skipped or guessed.

Scoring, per behaviour (drinking / eating / litter), pets not distinguished:

Videos listed with ``labels_done = yes`` and no label rows are scored as "nothing
happens here", which measures false alarms.

* **segment recall** — a labelled segment counts as found when predicted events of the
  same behaviour cover at least half of it;
* **event precision** — a predicted event counts as correct when at least half of it lies
  inside labelled segments of the same behaviour;
* **time precision / recall** — measured on a 0.2-second grid.

Pet detection rate = share of sampled frames inside labelled segments (the pet is known
to be visible there) that have at least one detection.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
BEHAVIORS = ["drinking", "eating", "litter"]
BEHAVIOR_ZH = {"drinking": "喝水", "eating": "進食", "litter": "如廁"}
SOURCE_COLS = ["video", "source_url", "license", "downloaded_on", "species", "n_pets", "lighting", "camera",
               "labels_done", "note"]
LABEL_COLS = ["video", "behavior", "start_s", "end_s", "note"]
GRID = 0.2


# ----------------------------------------------------------------- templates
def write_templates(folder: Path) -> list[Path]:
    """Create empty sources.csv / labels.csv (with one example row each, marked)."""
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    s = folder / "sources.csv"
    if not s.exists():
        with s.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(SOURCE_COLS)
            w.writerow(["範例_請刪除.mp4", "https://www.pexels.com/video/…（影片頁面網址）", "Pexels License",
                        "2026-11-05", "cat", "1", "day", "top-down", "yes", "這一列是範例，請刪除"])
        made.append(s)
    lab = folder / "labels.csv"
    if not lab.exists():
        with lab.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(LABEL_COLS)
            w.writerow(["範例_請刪除.mp4", "drinking", "3.0", "9.5", "這一列是範例，請刪除"])
        made.append(lab)
    return made


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]


# ----------------------------------------------------------------- prepare
def prepare(folder: Path, model: str | None = None) -> list[str]:
    """Snapshot with grid for every video; with an ONNX model also draft zones from detected bowls.

    COCO has a "bowl" class (id 45) but cannot tell food from water, so drafted bowls are
    written as ``food`` — change ``kind`` to ``water`` where needed. Litter boxes are not a
    COCO class and must be added by hand. Existing zone files are never overwritten.
    """
    import cv2

    from .cli import main as cli_main

    notes = []
    snap_dir = folder / "_snapshots"
    snap_dir.mkdir(exist_ok=True)
    det = None
    if model:
        from .detectors import OnnxYoloDetector
        det = OnnxYoloDetector(model, conf_threshold=0.3, classes={45: "bowl"})
    for v in sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT):
        snap = snap_dir / f"{v.stem}.jpg"
        cli_main(["snapshot", str(v), "--at", "1", "--out", str(snap)])
        zf = folder / f"{v.stem}_zones.json"
        if zf.exists():
            notes.append(f"{v.name}: 已有區域檔，未覆蓋")
            continue
        if det is None:
            notes.append(f"{v.name}: 需要手動建立 {zf.name}")
            continue
        cap = cv2.VideoCapture(str(v))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        bowls = []
        for t in (0.5, 2.0, 4.0):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                bowls += det.detect(frame)
        cap.release()
        zones, kept = [], []
        for d in sorted(bowls, key=lambda d: -d.score):
            b = d.bbox
            if any(abs(b.center[0] - k.center[0]) < b.w / 2 and abs(b.center[1] - k.center[1]) < b.h / 2 for k in kept):
                continue
            kept.append(b)
            zones.append({"name": f"bowl_{len(zones) + 1}", "kind": "food",
                          "rect": [round(b.x1), round(b.y1), round(b.x2), round(b.y2)]})
        if zones:
            zf.write_text(json.dumps({"frame_size": [w, h], "zones": zones, "_note":
                                      "由 YOLO 自動偵測碗產生的草稿：請確認位置，水碗把 kind 改成 water，砂盆需手動加入"},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
            notes.append(f"{v.name}: 自動找到 {len(zones)} 個碗 → {zf.name}（請檢查）")
        else:
            notes.append(f"{v.name}: 沒找到碗，需要手動建立 {zf.name}")
    return notes


# ----------------------------------------------------------------- scoring
def _cover(segs: list[tuple[float, float]], a: float, b: float) -> float:
    """Length of [a, b] covered by the union of segs."""
    pts = sorted((max(a, s), min(b, e)) for s, e in segs if e > a and s < b)
    total, cur_s, cur_e = 0.0, None, None
    for s, e in pts:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def _grid(segs, end: float) -> set[int]:
    return {i for i in range(int(end / GRID) + 1) if any(s <= i * GRID < e for s, e in segs)}


@dataclass
class Counts:
    labelled: int = 0
    found: int = 0
    predicted: int = 0
    correct: int = 0
    t_label: int = 0
    t_pred: int = 0
    t_both: int = 0

    def add(self, o: "Counts") -> None:
        for k in self.__dataclass_fields__:
            setattr(self, k, getattr(self, k) + getattr(o, k))

    def rates(self) -> dict:
        def r(a, b):
            return round(a / b, 3) if b else None
        p, rc = r(self.t_both, self.t_pred), r(self.t_both, self.t_label)
        return {"segment_recall": r(self.found, self.labelled), "event_precision": r(self.correct, self.predicted),
                "time_precision": p, "time_recall": rc,
                "time_f1": round(2 * p * rc / (p + rc), 3) if p and rc else (0.0 if p is not None and rc is not None else None)}


def score_video(labels: list[dict], events, end: float) -> tuple[dict[str, Counts], list[dict]]:
    per, rows = {}, []
    for b in BEHAVIORS:
        L = [(float(x["start_s"]), float(x["end_s"])) for x in labels if x["behavior"] == b]
        P = [(e.start_s, e.end_s) for e in events if e.behavior.value == b]
        c = Counts(labelled=len(L), predicted=len(P))
        for (s, e), lab in zip(L, [x for x in labels if x["behavior"] == b]):
            cov = _cover(P, s, e) / (e - s) if e > s else 0.0
            ok = cov >= 0.5
            c.found += ok
            rows.append({"behavior": b, "start_s": s, "end_s": e, "covered": round(cov, 2), "found": ok,
                         "note": lab.get("note", "")})
        c.correct = sum(_cover(L, s, e) / (e - s) >= 0.5 for s, e in P if e > s)
        gl, gp = _grid(L, end), _grid(P, end)
        c.t_label, c.t_pred, c.t_both = len(gl), len(gp), len(gl & gp)
        per[b] = c
    return per, rows


@dataclass
class VideoReport:
    video: str
    status: str
    source: dict = field(default_factory=dict)
    duration_s: float = 0.0
    pets_detected: int = 0
    detection_rate: float | None = None
    counts: dict = field(default_factory=dict)
    segments: list = field(default_factory=list)
    events: list = field(default_factory=list)


def run_batch(folder: Path, out: Path, detector_name: str = "motion", model: str | None = None,
              fps: float = 5.0, annotate: bool = False, log=print) -> Path:
    import cv2

    from .detectors import MotionDetector, OnnxYoloDetector
    from .pipeline import process_video
    from .zones import load_zones

    out.mkdir(parents=True, exist_ok=True)
    sources = {r["video"]: r for r in _read_csv(folder / "sources.csv") if r.get("video")}
    labels_all = defaultdict(list)
    for r in _read_csv(folder / "labels.csv"):
        if r.get("video") and r.get("behavior") in BEHAVIORS and r.get("start_s") and r.get("end_s"):
            labels_all[r["video"]].append(r)

    reports: list[VideoReport] = []
    videos = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT)
    for i, v in enumerate(videos, 1):
        src = sources.get(v.name, {})
        problems = []
        if not src.get("source_url") or not src.get("license"):
            problems.append("缺來源或授權")
        # labels_done=yes: the video was watched and has no eating/drinking/litter at all.
        # Such videos still count: every predicted event in them is a false alarm.
        if not labels_all.get(v.name) and src.get("labels_done", "").lower() not in ("yes", "y", "是"):
            problems.append("缺標註")
        zf = folder / f"{v.stem}_zones.json"
        if not zf.exists():
            problems.append("缺區域檔")
        if problems:
            reports.append(VideoReport(v.name, "不計入：" + "、".join(problems), src))
            log(f"[{i}/{len(videos)}] {v.name}: 不計入（{'、'.join(problems)}）")
            continue
        log(f"[{i}/{len(videos)}] {v.name}: 分析中…")
        cap = cv2.VideoCapture(str(v))
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        dur = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        cap.release()
        det = OnnxYoloDetector(model) if detector_name == "onnx" else MotionDetector(fps=fps)
        vdir = out / v.stem
        vdir.mkdir(exist_ok=True)
        res = process_video(v, load_zones(zf, size), det, sample_fps=fps,
                            annotate_path=vdir / "annotated.mp4" if annotate else None,
                            overview_path=vdir / "overview.jpg")
        labels = labels_all[v.name]
        counts, segs = score_video(labels, res.events, dur)
        seen = {round(s.t, 2) for ss in res.tracks.values() for s in ss if s.detection is not None}
        L = [(float(x["start_s"]), float(x["end_s"])) for x in labels]
        inside = [k / res.fps for k in range(int(dur * res.fps) + 1) if any(s <= k / res.fps < e for s, e in L)]
        hit = sum(round(t, 2) in seen for t in inside)
        reports.append(VideoReport(
            v.name, "計入", src, round(dur, 1), len(res.pet_ids),
            round(hit / len(inside), 3) if inside else None, counts, segs,
            [{"pet_id": e.pet_id, "behavior": e.behavior.value, "start_s": e.start_s, "end_s": e.end_s,
              "zone": e.zone or ""} for e in res.events]))

    path = write_report(reports, out, detector_name, model, fps)
    log(f"\n報表 -> {path}")
    return path


# ----------------------------------------------------------------- report
def _tags(r: VideoReport) -> dict:
    s = r.source
    return {"species": s.get("species", ""), "n_pets": s.get("n_pets", ""), "lighting": s.get("lighting", ""),
            "camera": s.get("camera", "")}


def summarize(reports: list[VideoReport]) -> dict:
    used = [r for r in reports if r.status == "計入"]
    total = {b: Counts() for b in BEHAVIORS}
    for r in used:
        for b in BEHAVIORS:
            total[b].add(r.counts[b])
    det = [r.detection_rate for r in used if r.detection_rate is not None]
    groups = {}
    for key in ("species", "lighting", "camera", "n_pets"):
        g = defaultdict(lambda: {b: Counts() for b in BEHAVIORS})
        for r in used:
            for b in BEHAVIORS:
                g[_tags(r)[key] or "(未填)"][b].add(r.counts[b])
        groups[key] = {k: {b: v[b].rates() | {"labelled": v[b].labelled} for b in BEHAVIORS} for k, v in g.items()}
    return {"videos_total": len(reports), "videos_used": len(used),
            "mean_detection_rate": round(sum(det) / len(det), 3) if det else None,
            "by_behavior": {b: total[b].rates() | {"labelled": total[b].labelled, "found": total[b].found,
                                                   "predicted": total[b].predicted, "correct": total[b].correct}
                            for b in BEHAVIORS},
            "by_group": groups}


def write_report(reports: list[VideoReport], out: Path, detector_name: str, model: str | None, fps: float) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    summ = summarize(reports)
    (out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2), encoding="utf-8")
    wb = Workbook()
    head_fill, head_font = PatternFill("solid", fgColor="3A3F45"), Font(bold=True, color="FFFFFF")

    def sheet(title, header, rows, widths=None):
        ws = wb.create_sheet(title)
        ws.append(header)
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
        for r in rows:
            ws.append(r)
        for i, wdt in enumerate(widths or [], 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = wdt
        ws.freeze_panes = "A2"
        return ws

    ws = wb.active
    ws.title = "總覽"
    info = [
        ("產生時間", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("偵測器", f"{detector_name}" + (f"（{Path(model).name}）" if model else "")),
        ("取樣頻率", f"{fps} 張／秒"),
        ("影片數（計入／全部）", f"{summ['videos_used']} / {summ['videos_total']}"),
        ("平均寵物偵測率", summ["mean_detection_rate"]),
        ("資料說明", "所有數字皆由程式比對 labels.csv（人工標註）與系統輸出計算；來源見「影片來源」分頁。"),
        ("判定規則", "標註片段被同類預測事件覆蓋 ≥50% 算找到；預測事件 ≥50% 落在同類標註內算正確；時間指標以 0.2 秒為單位。不區分是哪一隻寵物。"),
    ]
    for k, v in info:
        ws.append([k, v])
    ws.append([])
    ws.append(["行為", "標註片段數", "找到", "片段召回率", "預測事件數", "正確", "事件精確率", "時間精確率", "時間召回率", "時間 F1"])
    hdr = ws.max_row
    for c in ws[hdr]:
        c.fill, c.font = head_fill, head_font
    for b in BEHAVIORS:
        x = summ["by_behavior"][b]
        ws.append([BEHAVIOR_ZH[b], x["labelled"], x["found"], x["segment_recall"], x["predicted"], x["correct"],
                   x["event_precision"], x["time_precision"], x["time_recall"], x["time_f1"]])
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 70
    for row in ws.iter_rows(min_row=1, max_row=len(info)):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    sheet("每支影片", ["影片", "狀態", "物種", "隻數", "光線", "鏡頭", "長度(秒)", "偵測到幾隻", "寵物偵測率"]
          + [f"{BEHAVIOR_ZH[b]} 找到/標註" for b in BEHAVIORS] + [f"{BEHAVIOR_ZH[b]} 正確/預測" for b in BEHAVIORS],
          [[r.video, r.status, *_tags(r).values(), r.duration_s or None, r.pets_detected or None, r.detection_rate]
           + [f"{r.counts[b].found}/{r.counts[b].labelled}" if r.counts else "" for b in BEHAVIORS]
           + [f"{r.counts[b].correct}/{r.counts[b].predicted}" if r.counts else "" for b in BEHAVIORS]
           for r in reports], [34, 26, 8, 6, 8, 10, 10, 10, 11, 12, 12, 12, 12, 12, 12])
    sheet("分組結果", ["分組依據", "組別", "行為", "標註片段數", "片段召回率", "事件精確率", "時間 F1"],
          [[key, grp, BEHAVIOR_ZH[b], v[b]["labelled"], v[b]["segment_recall"], v[b]["event_precision"], v[b]["time_f1"]]
           for key, gs in summ["by_group"].items() for grp, v in gs.items() for b in BEHAVIORS if v[b]["labelled"]],
          [12, 16, 8, 12, 12, 12, 10])
    sheet("標註比對", ["影片", "行為", "開始(秒)", "結束(秒)", "被預測覆蓋比例", "找到", "標註備註"],
          [[r.video, BEHAVIOR_ZH[s["behavior"]], s["start_s"], s["end_s"], s["covered"], "是" if s["found"] else "否", s["note"]]
           for r in reports for s in r.segments], [34, 8, 10, 10, 16, 8, 30])
    sheet("系統預測事件", ["影片", "寵物", "行為", "開始(秒)", "結束(秒)", "區域"],
          [[r.video, e["pet_id"], e["behavior"], e["start_s"], e["end_s"], e["zone"]] for r in reports for e in r.events],
          [34, 10, 10, 10, 10, 16])
    sheet("影片來源", SOURCE_COLS, [[r.source.get(c, "") if c != "video" else r.video for c in SOURCE_COLS] for r in reports],
          [34, 60, 16, 14, 8, 6, 8, 10, 30])
    path = out / "batch_report.xlsx"
    wb.save(path)
    return path
