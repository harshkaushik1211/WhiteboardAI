"""Ink image → ordered SVG stroke paths for line-by-line whiteboard animation."""
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


def _parse_path_points(d: str) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for token in d.split():
        if token.startswith("M") or token.startswith("L"):
            coord = token[1:]
            if "," in coord:
                x, y = coord.split(",", 1)
                pts.append((float(x), float(y)))
    return pts


def path_centroid(d: str) -> Tuple[float, float]:
    pts = _parse_path_points(d)
    if not pts:
        return 0.0, 0.0
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    n = len(pts)
    return sx / n, sy / n


def path_start(d: str) -> Tuple[float, float]:
    pts = _parse_path_points(d)
    return pts[0] if pts else (0.0, 0.0)


def path_end(d: str) -> Tuple[float, float]:
    pts = _parse_path_points(d)
    return pts[-1] if pts else (0.0, 0.0)


def _reverse_path_d(d: str) -> str:
    pts = _parse_path_points(d)
    if len(pts) < 2:
        return d
    parts = []
    for i, (x, y) in enumerate(reversed(pts)):
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd}{int(round(x))},{int(round(y))}")
    return " ".join(parts)


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _is_bbox_rectangle_path(d: str) -> bool:
    """Skip closed rectangle outlines used as fallbacks."""
    if not d.rstrip().endswith("Z"):
        return False
    pts = _parse_path_points(d)
    return len(pts) <= 5


def order_paths_for_drawing(paths: List[Dict]) -> List[Dict]:
    """Greedy nearest-neighbor ordering — mimics continuous pen movement."""
    if len(paths) <= 1:
        return paths

    remaining = list(paths)
    remaining.sort(key=lambda p: (path_start(p["d"])[1], path_start(p["d"])[0]))

    ordered: List[Dict] = []
    current = remaining.pop(0)
    ordered.append(current)
    pen = path_end(current["d"])

    while remaining:
        best_idx = 0
        best_dist = float("inf")
        best_reverse = False

        for i, cand in enumerate(remaining):
            s = path_start(cand["d"])
            e = path_end(cand["d"])
            ds = _dist(pen, s)
            de = _dist(pen, e)
            if ds < best_dist:
                best_dist = ds
                best_idx = i
                best_reverse = False
            if de < best_dist:
                best_dist = de
                best_idx = i
                best_reverse = True

        nxt = remaining.pop(best_idx)
        if best_reverse:
            nxt = {**nxt, "d": _reverse_path_d(nxt["d"])}
        ordered.append(nxt)
        pen = path_end(nxt["d"])

    return ordered


def _ink_mask_from_bgr(crop_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )
    ink = (thresh < 10).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)
    return ink


def extract_svg_paths_from_crop(
    crop_bgr: np.ndarray,
    offset_x: int,
    offset_y: int,
) -> List[Dict]:
    """Extract drawable stroke paths from a crop of the whiteboard image."""
    if crop_bgr.size == 0:
        return []

    ink = _ink_mask_from_bgr(crop_bgr)
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    paths: List[Dict] = []
    min_len = max(12, settings.contour_min_area)

    for cnt in contours:
        peri = cv2.arcLength(cnt, False)
        if peri < min_len:
            continue

        area = cv2.contourArea(cnt)
        if area < settings.contour_min_area:
            continue

        epsilon = max(0.8, settings.contour_approx_epsilon * peri * 0.5)
        approx = cv2.approxPolyDP(cnt, epsilon, False)
        if len(approx) < 2:
            continue

        pts = approx.reshape(-1, 2)
        d = _contour_to_path_d(pts, offset_x, offset_y)
        if not d or _is_bbox_rectangle_path(d):
            continue

        length = _path_length_from_points(pts)
        paths.append(
            {
                "d": d,
                "length": round(length, 2),
                "area": int(area),
            }
        )

    return order_paths_for_drawing(paths)


def extract_ink_paths_from_image(
    img_bgr: np.ndarray,
    offset_x: int = 0,
    offset_y: int = 0,
) -> List[Dict]:
    """Extract all stroke paths from a full scene image."""
    return extract_svg_paths_from_crop(img_bgr, offset_x, offset_y)


def assign_paths_to_bbox(
    paths: List[Dict],
    x: int,
    y: int,
    w: int,
    h: int,
) -> List[Dict]:
    """Return paths whose centroid falls inside the bbox."""
    x1, y1 = x, y
    x2, y2 = x + w, y + h
    out: List[Dict] = []
    for p in paths:
        cx, cy = path_centroid(p["d"])
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            out.append(p)
    return order_paths_for_drawing(out)


def build_ink_image(img_thresh: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_thresh, cv2.COLOR_GRAY2BGR)
