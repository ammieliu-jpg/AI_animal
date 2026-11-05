import csv
import shutil

from openpyxl import load_workbook

from pet_vision.batch import Counts, _cover, run_batch, score_video, write_templates
from pet_vision.synth import generate
from pet_vision.types import Behavior, Event


def test_cover_merges_overlaps():
    assert _cover([(0, 2), (1, 3), (5, 6)], 0, 10) == 4
    assert _cover([(0, 2)], 1, 5) == 1


def test_score_video_counts():
    labels = [{"behavior": "drinking", "start_s": "10", "end_s": "20"},
              {"behavior": "eating", "start_s": "30", "end_s": "40"}]
    events = [Event("p", Behavior.DRINKING, 11, 19, 0.9),   # covers 80 % -> found, correct
              Event("p", Behavior.EATING, 50, 55, 0.9)]     # wrong place -> eating missed, wrong event
    c, rows = score_video(labels, events, 60)
    assert (c["drinking"].found, c["drinking"].correct) == (1, 1)
    assert (c["eating"].found, c["eating"].correct, c["eating"].predicted) == (0, 0, 1)
    assert c["drinking"].rates()["segment_recall"] == 1.0
    assert Counts().rates()["segment_recall"] is None  # nothing labelled: no made-up number


def test_batch_on_synthetic_clip(tmp_path):
    folder = tmp_path / "videos"
    write_templates(folder)
    g = generate(tmp_path / "syn", fps=10)
    shutil.copy(g["video"], folder / "syn.mp4")
    shutil.copy(g["zones"], folder / "syn_zones.json")
    shutil.copy(g["video"], folder / "no_source.mp4")  # must be excluded, not guessed
    shutil.copy(g["video"], folder / "nothing.mp4")    # labelled as "nothing happens": all events are false alarms
    shutil.copy(g["zones"], folder / "nothing_zones.json")
    with (folder / "sources.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["video", "source_url", "license", "downloaded_on", "species", "n_pets", "lighting", "camera",
                    "labels_done", "note"])
        w.writerow(["syn.mp4", "local://synthetic", "self-made", "2026-11-05", "cat", "1", "day", "side", "yes", "合成測試"])
        w.writerow(["nothing.mp4", "local://synthetic", "self-made", "2026-11-05", "cat", "1", "day", "side", "yes", "沒有吃喝"])
    with (folder / "labels.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["video", "behavior", "start_s", "end_s", "note"])
        for r in csv.DictReader(open(g["ground_truth"], encoding="utf-8")):
            if r["behavior"] in ("drinking", "eating", "litter"):
                w.writerow(["syn.mp4", r["behavior"], r["start_s"], r["end_s"], ""])
    path = run_batch(folder, tmp_path / "out", log=lambda *a: None)
    wb = load_workbook(path)
    assert set(wb.sheetnames) == {"總覽", "每支影片", "分組結果", "標註比對", "系統預測事件", "影片來源"}
    rows = {r[0]: r for r in wb["每支影片"].iter_rows(min_row=2, values_only=True)}
    assert rows["syn.mp4"][1] == "計入"
    assert rows["no_source.mp4"][1].startswith("不計入")
    assert rows["nothing.mp4"][1] == "計入"
    assert rows["nothing.mp4"][12] == "0/1"  # one drinking event predicted, none correct
    found = [r for r in wb["標註比對"].iter_rows(min_row=2, values_only=True)]
    assert len(found) == 3 and all(r[5] == "是" for r in found)
