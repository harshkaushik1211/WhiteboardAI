"""
Object-wise stroke order for whiteboard PNGs (storyboard-ai grid walk, no SAM).

Uses connected components to split ink blobs into objects, then nearest-neighbor
grid traversal per object for a natural hand-drawn reveal order.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

from config import settings


def _euc_dist(arr: np.ndarray, point: np.ndarray) -> np.ndarray:
    square_sub = (arr - point) ** 2
    return np.sqrt(np.sum(square_sub, axis=1))


def _bbox_for_cells(
    cells: List[Tuple[int, int]],
    split_len: int,
    width: int,
    height: int,
    pad: int = 4,
) -> List[int]:
    if not cells:
        return [0, 0, width, height]
    rows = [c[0] for c in cells]
    cols = [c[1] for c in cells]
    x0 = max(0, min(cols) * split_len - pad)
    y0 = max(0, min(rows) * split_len - pad)
    x1 = min(width, (max(cols) + 1) * split_len + pad)
    y1 = min(height, (max(rows) + 1) * split_len + pad)
    return [int(x0), int(y0), int(max(1, x1 - x0)), int(max(1, y1 - y0))]


def ink_image_path_for_sketch(rel_image_path: str) -> str:
    p = Path(rel_image_path)
    return str(p.parent / f"{p.stem}-ink.png")


def _grid_cells_for_mask(
    img_thresh: np.ndarray,
    object_mask: np.ndarray | None,
    resize_ht: int,
    resize_wd: int,
    split_len: int,
    black_pixel_threshold: int,
) -> List[Tuple[int, int]]:
    """Return grid (row, col) indices in nearest-neighbor draw order."""
    img_copy = img_thresh.copy()
    if object_mask is not None:
        img_copy[object_mask == 0] = 255

    n_cuts_vertical = int(np.ceil(resize_ht / split_len))
    n_cuts_horizontal = int(np.ceil(resize_wd / split_len))

    pad_h = n_cuts_vertical * split_len - resize_ht
    pad_w = n_cuts_horizontal * split_len - resize_wd
    if pad_h > 0 or pad_w > 0:
        img_copy = cv2.copyMakeBorder(
            img_copy, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=255
        )

    grid_of_cuts = np.array(np.split(img_copy, n_cuts_horizontal, axis=-1))
    grid_of_cuts = np.array(np.split(grid_of_cuts, n_cuts_vertical, axis=-2))

    cut_having_black = (grid_of_cuts < black_pixel_threshold).astype(np.uint8)
    cut_having_black = np.sum(np.sum(cut_having_black, axis=-1), axis=-1)
    cut_black_indices = np.array(np.where(cut_having_black > 0)).T

    if len(cut_black_indices) == 0:
        return []

    order: List[Tuple[int, int]] = []
    selected_ind = 0
    indices = cut_black_indices.copy()

    while len(indices) > 0:
        selected = indices[selected_ind]
        order.append((int(selected[0]), int(selected[1])))
        indices = np.delete(indices, selected_ind, axis=0)
        if len(indices) > 0:
            dists = _euc_dist(indices, selected)
            selected_ind = int(np.argmin(dists))

    return order


def extract_stroke_data(
    image_path: Path,
    output_path: Path | None = None,
    width: int | None = None,
    height: int | None = None,
    split_len: int | None = None,
    min_component_area: int | None = None,
    black_pixel_threshold: int = 10,
) -> Dict:
    """
    Build stroke manifest: ordered grid cells per connected ink object.
    """
    width = width or settings.png_stroke_width
    height = height or settings.png_stroke_height
    split_len = split_len or settings.png_stroke_split_len
    min_component_area = min_component_area or settings.png_stroke_min_area

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    img = cv2.resize(img, (width, height))
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_thresh = cv2.adaptiveThreshold(
        img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    ink = (img_thresh < black_pixel_threshold).astype(np.uint8) * 255
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        ink, connectivity=8
    )

    components: List[Tuple[float, float, int, int]] = []
    for label_id in range(1, num_labels):
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_component_area:
            continue
        cx, cy = centroids[label_id]
        components.append((cy, cx, label_id, area))

    components.sort(key=lambda t: (t[0], t[1]))

    all_cells: List[List[int]] = []
    objects: List[Dict[str, int]] = []

    for _cy, _cx, label_id, area in components:
        obj_mask = (labels == label_id).astype(np.uint8) * 255
        cells = _grid_cells_for_mask(
            img_thresh, obj_mask, height, width, split_len, black_pixel_threshold
        )
        if not cells:
            continue
        start = len(all_cells)
        all_cells.extend([[r, c] for r, c in cells])
        bbox = _bbox_for_cells(cells, split_len, width, height)
        objects.append(
            {"start": start, "end": len(all_cells), "area": area, "bbox": bbox}
        )

    if not all_cells:
        cells = _grid_cells_for_mask(
            img_thresh, None, height, width, split_len, black_pixel_threshold
        )
        all_cells = [[r, c] for r, c in cells]
        bbox = _bbox_for_cells(
            [(c[0], c[1]) for c in all_cells], split_len, width, height
        )
        objects = [{"start": 0, "end": len(all_cells), "area": 0, "bbox": bbox}]

    ink_bgr = cv2.cvtColor(img_thresh, cv2.COLOR_GRAY2BGR)
    rel_ink = ink_image_path_for_sketch(f"assets/{image_path.name}")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ink_path = output_path.parent / f"{image_path.stem}-ink.png"
        cv2.imwrite(str(ink_path), ink_bgr)

    data = {
        "width": width,
        "height": height,
        "split_len": split_len,
        "cells": all_cells,
        "objects": objects,
        "cell_count": len(all_cells),
        "object_count": len(objects),
        "ink_image": rel_ink,
    }

    if output_path is not None:
        output_path.write_text(json.dumps(data), encoding="utf-8")

    return data


def stroke_json_path_for_sketch(rel_image_path: str) -> str:
    """assets/scene-1-sketch.png -> assets/scene-1-sketch-strokes.json"""
    p = Path(rel_image_path)
    return str(p.parent / f"{p.stem}-strokes.json")


def normalize_sketch_png(image_path: Path) -> Tuple[int, int]:
    """Resize color sketch on disk to stroke canvas size so ink/color/cells align."""
    width = settings.png_stroke_width
    height = settings.png_stroke_height
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(image_path), img)
    return width, height


def extract_strokes_for_project_image(project_id: str, rel_image_path: str) -> str:
    from utils.file_manager import project_dir

    proj = project_dir(project_id)
    image_path = proj / rel_image_path
    normalize_sketch_png(image_path)
    rel_stroke = stroke_json_path_for_sketch(rel_image_path)
    out_path = proj / rel_stroke
    extract_stroke_data(image_path, out_path)
    return rel_stroke


def backfill_stroke_assets_for_project(project_id: str) -> int:
    """Regenerate *-strokes.json and *-ink.png for existing sketch PNGs."""
    from utils.file_manager import project_dir

    proj = project_dir(project_id)
    count = 0
    for png in sorted(proj.glob("assets/scene-*-sketch.png")):
        rel = str(png.relative_to(proj))
        extract_strokes_for_project_image(project_id, rel)
        count += 1
    return count
