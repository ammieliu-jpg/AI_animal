"""COCO-pretrained YOLO (ONNX export) restricted to cats and dogs.

Expected model output: ``[1, 4 + num_classes, N]`` (YOLOv8 / YOLO11 export format,
e.g. ``yolo export model=yolo11n.pt format=onnx``). COCO class ids: cat = 15, dog = 16.

The weights are not shipped with this repo. Download/export them on your own machine
and record their licence in the proposal appendix (注意事項第 16 點).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..types import BBox, Detection

COCO_PET_CLASSES = {15: "cat", 16: "dog"}


class OnnxYoloDetector:
    def __init__(
        self,
        model_path: str | Path,
        input_size: int = 640,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.5,
        classes: dict[int, str] | None = None,
    ) -> None:
        import onnxruntime as ort  # imported lazily so the package works without it

        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.classes = classes or COCO_PET_CLASSES

    def _letterbox(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        h, w = frame.shape[:2]
        s = self.input_size / max(h, w)
        nh, nw = int(round(h * s)), int(round(w * s))
        resized = cv2.resize(frame, (nw, nh))
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        top, left = (self.input_size - nh) // 2, (self.input_size - nw) // 2
        canvas[top:top + nh, left:left + nw] = resized
        return canvas, s, (left, top)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        img, scale, (pad_x, pad_y) = self._letterbox(frame)
        blob = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        out = self.session.run(None, {self.input_name: blob})[0]
        return self.postprocess(out, scale, pad_x, pad_y, frame.shape[1], frame.shape[0])

    def postprocess(
        self, out: np.ndarray, scale: float, pad_x: float, pad_y: float, frame_w: int, frame_h: int
    ) -> list[Detection]:
        preds = out[0].T  # [N, 4 + C]
        boxes_xywh = preds[:, :4]
        class_scores = preds[:, 4:]
        ids = np.array(sorted(self.classes))
        sub = class_scores[:, ids]
        best = sub.argmax(axis=1)
        conf = sub[np.arange(len(sub)), best]
        keep = conf >= self.conf_threshold
        if not keep.any():
            return []
        boxes_xywh, conf, best = boxes_xywh[keep], conf[keep], best[keep]

        cx, cy, bw, bh = boxes_xywh.T
        x1 = ((cx - bw / 2) - pad_x) / scale
        y1 = ((cy - bh / 2) - pad_y) / scale
        x2 = ((cx + bw / 2) - pad_x) / scale
        y2 = ((cy + bh / 2) - pad_y) / scale
        rects = [[float(a), float(b), float(c - a), float(d - b)] for a, b, c, d in zip(x1, y1, x2, y2)]
        idx = cv2.dnn.NMSBoxes(rects, conf.astype(float).tolist(), self.conf_threshold, self.iou_threshold)
        dets = []
        for i in np.array(idx).flatten():
            box = BBox(
                float(np.clip(x1[i], 0, frame_w)), float(np.clip(y1[i], 0, frame_h)),
                float(np.clip(x2[i], 0, frame_w)), float(np.clip(y2[i], 0, frame_h)),
            )
            dets.append(Detection(bbox=box, score=float(conf[i]), label=self.classes[int(ids[best[i]])]))
        dets.sort(key=lambda d: d.score, reverse=True)
        return dets
