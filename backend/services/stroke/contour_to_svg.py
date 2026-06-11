"""Crop → edge detection → contour extraction → SVG path strings."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import cv2
import numpy as np

from config import settings


def _path_length_from_points(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        dx = float(points[i][0] - points[i - 1][0])
        dy = float(points[i][1] - points[i - 1][1])
        total += math.hypot(dx, dy)
    return max(total, 1.0)


def _contour_to_path_d(points: np.ndarray, offset_x: int, offset_y: int) -> str:
    if len(points) < 2:
        return ""
    parts = []
    for i, pt in enumerate(points):
        x = int(pt[0]) + offset_x
        y = int(pt[1]) + offset_y
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd}{x},{y}")
    return " ".join(parts)


def extract_svg_paths_from_crop(
    crop_bgr: np.ndarray,
    offset_x: int,
    offset_y: int,
) -> List[Dict]:
    """
    Edge-detect ink in a cropped region and return SVG path dicts in canvas coords.
    """
    if crop_bgr.size == 0:
        return []

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    edges = cv2.Canny(
        blurred,
        settings.contour_canny_low,
        settings.contour_canny_high,
    )
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )
    ink = (thresh < 10).astype(np.uint8) * 255
    combined = cv2.bitwise_or(edges, ink)

    contours, _ = cv2.findContours(combined, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    paths: List[Dict] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < settings.contour_min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        epsilon = max(1.0, settings.contour_approx_epsilon * peri)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 2:
            continue
        pts = approx.reshape(-1, 2)
        d = _contour_to_path_d(pts, offset_x, offset_y)
        if not d:
            continue
        length = _path_length_from_points(pts)
        paths.append(
            {
                "d": d,
                "length": round(length, 2),
                "area": int(area),
            }
        )

    paths.sort(key=lambda p: (p["d"].split(",")[1] if "," in p["d"] else "0", p["area"]))
    return paths


def build_ink_image(img_thresh: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_thresh, cv2.COLOR_GRAY2BGR)
