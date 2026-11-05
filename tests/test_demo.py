from petsentinel.demo import run_demo


def test_demo_runs_end_to_end_without_video(tmp_path):
    index = run_demo(str(tmp_path / "demo"), days=60, seed=7, log=lambda *a: None)
    html = index.read_text(encoding="utf-8")
    assert "毛孩日常哨兵" in html and "模擬資料" in html
    out = index.parent
    assert (out / "anomaly" / "alerts.json").exists()
    assert (out / "notify" / "preview.html").exists()
    assert list((out / "anomaly").glob("trend_*.png"))
    assert list((out / "notify").glob("vet_report_*.html"))  # the chosen day has a consult
