"""Tests for contour extraction helpers."""
import numpy as np
import cv2

from services.stroke.contour_to_svg import (
    extract_svg_paths_from_crop,
    order_paths_for_drawing,
    path_start,
)
from services.stroke.vision_bbox_detector import _clamp_bbox_pixels


def test_clamp_bbox_pixels():
    x, y, w, h = _clamp_bbox_pixels(100, 200, 400, 600, 1920, 1080, 0.05)
    assert w > 0 and h > 0
    assert x >= 0 and y >= 0


def test_extract_paths_from_synthetic_crop():
    crop = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2.rectangle(crop, (20, 20), (80, 80), (0, 0, 0), 2)
    paths = extract_svg_paths_from_crop(crop, offset_x=10, offset_y=10)
    assert len(paths) >= 1
    assert "d" in paths[0]
    assert paths[0]["length"] > 0


def test_order_paths_for_drawing():
    paths = [
        {"d": "M10,10 L50,10", "length": 40},
        {"d": "M50,10 L50,50", "length": 40},
    ]
    ordered = order_paths_for_drawing(paths)
    assert path_start(ordered[0]["d"]) == (10.0, 10.0)
