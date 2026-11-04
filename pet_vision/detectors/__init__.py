"""Pet detectors.

* :class:`MotionDetector` — no model weights needed. Works for a fixed indoor camera
  with a single pet (background subtraction). Good for prototyping and the Demo.
* :class:`OnnxYoloDetector` — runs a COCO-pretrained YOLO model exported to ONNX and
  keeps only the ``cat`` / ``dog`` classes. Download / export the weights yourself and
  check their licence (Ultralytics weights are AGPL-3.0).
"""

from .base import Detector
from .motion import MotionDetector
from .onnx_yolo import OnnxYoloDetector

__all__ = ["Detector", "MotionDetector", "OnnxYoloDetector"]
