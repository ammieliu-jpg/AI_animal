import json

import numpy as np
import pytest

from pet_vision.behavior import BehaviorClassifier
from pet_vision.detectors.onnx_yolo import OnnxYoloDetector
from pet_vision.events import build_events, summarize
from pet_vision.types import BBox, Behavior, Detection, FrameState
from pet_vision.zones import Zone, load_zones

WATER = Zone("water", "water", [(100, 100), (140, 100), (140, 130), (100, 130)])
LITTER = Zone("litter", "litter", [(400, 100), (550, 100), (550, 250), (400, 250)])


def det(x1, y1, x2, y2, **kw):
    return Detection(BBox(x1, y1, x2, y2), score=1.0, **kw)


# --- zones ---------------------------------------------------------------

def test_zone_contains_and_coverage():
    assert WATER.contains(120, 115)
    assert not WATER.contains(90, 115)
    assert WATER.coverage_by(BBox(90, 90, 150, 140)) == pytest.approx(1.0)
    assert WATER.coverage_by(BBox(120, 100, 200, 200)) == pytest.approx(0.5)


def test_load_zones_rect_and_rescale(tmp_path):
    p = tmp_path / "z.json"
    p.write_text(json.dumps({"frame_size": [100, 100],
                             "zones": [{"name": "w", "kind": "water", "rect": [10, 10, 20, 20]}]}))
    (z,) = load_zones(p, frame_size=(200, 300))
    assert z.bounds == BBox(20, 30, 40, 60)


def test_zone_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Zone("x", "bed", [(0, 0), (1, 0), (1, 1)])


# --- per-frame behaviour -------------------------------------------------

def test_absent_when_no_detection():
    assert BehaviorClassifier([WATER]).classify(0, []).behavior == Behavior.ABSENT


def test_drinking_when_still_over_bowl():
    clf = BehaviorClassifier([WATER])
    for i in range(6):
        st = clf.classify(i * 0.2, [det(90, 80, 160, 140)])
    assert st.behavior == Behavior.DRINKING
    assert st.zone == "water"


def test_walking_past_bowl_is_active():
    clf = BehaviorClassifier([WATER])
    for i in range(6):
        x = 60 + i * 20  # 100 px/s, box diagonal ~92 px  ->  ~1.1 diag/s
        st = clf.classify(i * 0.2, [det(x, 80, x + 70, 140)])
    assert st.behavior == Behavior.ACTIVE


def test_resting_vs_active_away_from_zones():
    still, moving = BehaviorClassifier([WATER]), BehaviorClassifier([WATER])
    for i in range(6):
        a = still.classify(i * 0.2, [det(300, 300, 360, 340)])
        b = moving.classify(i * 0.2, [det(300 + i * 15, 300, 360 + i * 15, 340)])
    assert a.behavior == Behavior.RESTING
    assert b.behavior == Behavior.ACTIVE


def test_nose_keypoint_takes_priority():
    clf = BehaviorClassifier([WATER])
    # Body box far from the bowl, but the nose is in it (e.g. long-necked dog).
    st = clf.classify(0, [det(150, 50, 260, 140, keypoints={"nose": (120, 115)})])
    assert st.behavior == Behavior.DRINKING


def test_litter_uses_body_centre():
    clf = BehaviorClassifier([LITTER])
    assert clf.classify(0, [det(440, 150, 520, 200)]).behavior == Behavior.LITTER
    clf.reset()
    assert clf.classify(0, [det(360, 150, 420, 200)]).behavior == Behavior.RESTING


def test_stationary_hold_is_resting_even_in_zone():
    st = BehaviorClassifier([LITTER]).classify(0, [det(440, 150, 520, 200, stationary_hold=True)])
    assert st.behavior == Behavior.RESTING


# --- events --------------------------------------------------------------

def _states(seq, fps):
    return [FrameState(i / fps, b, 0.9) for i, b in enumerate(seq)]


def test_short_blip_is_absorbed():
    fps = 5
    seq = [Behavior.ACTIVE] * 20 + [Behavior.DRINKING] * 5 + [Behavior.ACTIVE] * 20  # 1 s blip
    events = build_events(_states(seq, fps), fps)
    assert [e.behavior for e in events] == [Behavior.ACTIVE]


def test_real_drinking_event_kept_with_duration():
    fps = 5
    seq = [Behavior.ACTIVE] * 20 + [Behavior.DRINKING] * 40 + [Behavior.RESTING] * 50
    events = build_events(_states(seq, fps), fps)
    assert [e.behavior for e in events] == [Behavior.ACTIVE, Behavior.DRINKING, Behavior.RESTING]
    assert events[1].duration_s == pytest.approx(8.0, abs=0.5)
    s = summarize(events)
    assert s["drinking"]["count"] == 1
    assert s["drinking"]["label_zh"] == "喝水"


def test_noise_frames_are_smoothed():
    fps = 5
    seq = [Behavior.EATING] * 30
    seq[10] = seq[20] = Behavior.ACTIVE
    events = build_events(_states(seq, fps), fps)
    assert len(events) == 1 and events[0].behavior == Behavior.EATING


# --- ONNX post-processing (no model file needed) -------------------------

def test_onnx_postprocess_keeps_only_pets():
    d = object.__new__(OnnxYoloDetector)
    d.conf_threshold, d.iou_threshold = 0.3, 0.5
    d.classes = {15: "cat", 16: "dog"}
    out = np.zeros((1, 84, 3), dtype=np.float32)
    out[0, :4, 0] = [100, 100, 40, 40]; out[0, 4 + 15, 0] = 0.9   # cat
    out[0, :4, 1] = [102, 101, 40, 40]; out[0, 4 + 15, 1] = 0.6   # duplicate cat -> NMS
    out[0, :4, 2] = [300, 300, 50, 50]; out[0, 4 + 0, 2] = 0.95   # person -> ignored
    dets = d.postprocess(out, scale=1.0, pad_x=0, pad_y=0, frame_w=640, frame_h=640)
    assert len(dets) == 1
    assert dets[0].label == "cat"
    assert dets[0].bbox == BBox(80, 80, 120, 120)


# --- end to end on the synthetic clip ------------------------------------

def test_pipeline_on_synthetic_clip(tmp_path):
    from pet_vision.detectors import MotionDetector
    from pet_vision.evaluate import evaluate, load_segments
    from pet_vision.pipeline import process_video, write_outputs
    from pet_vision.synth import generate

    paths = generate(tmp_path, fps=10)
    zones = load_zones(paths["zones"])
    result = process_video(paths["video"], zones, MotionDetector(fps=5), sample_fps=5)
    report = evaluate(result.events, load_segments(paths["ground_truth"]))
    assert report["frame_accuracy"] >= 0.9, report
    found = {e.behavior for e in result.events}
    assert {Behavior.DRINKING, Behavior.EATING, Behavior.LITTER, Behavior.RESTING} <= found
    out = write_outputs(result, tmp_path / "out")
    assert out["events"].read_text(encoding="utf-8").startswith("pet_id,behavior")
