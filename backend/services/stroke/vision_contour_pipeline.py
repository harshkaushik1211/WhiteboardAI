"""
Enhanced stroke pipeline (replaces SAM3):

Image → OpenAI Vision bboxes → crop → edge detect → contours → SVG paths
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from config import settings
from services.stroke.contour_to_svg import build_ink_image, extract_svg_paths_from_crop
from services.stroke.vision_bbox_detector import VisionObject, detect_object_bboxes

logger = logging.getLogger("vision_contour_pipeline")


async def extract_vision_contour_stroke_data(
    image_path: Path,
    width: int,
    height: int,
    object_hints: Optional[List[str]] = None,
    visual_description: str = "",
    debug_output_path: Optional[Path] = None,
) -> Dict:
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    img = cv2.resize(img, (width, height))

    vision_objects = await detect_object_bboxes(
        str(image_path),
        width,
        height,
        visual_description=visual_description,
        object_hints=object_hints,
    )

    all_paths: List[Dict] = []
    objects: List[Dict] = []
    object_labels: List[str] = []
    debug_objects: List[Dict] = []

    for vobj in vision_objects:
        crop = img[vobj.y : vobj.y + vobj.h, vobj.x : vobj.x + vobj.w]
        obj_paths = extract_svg_paths_from_crop(crop, vobj.x, vobj.y)

        if not obj_paths:
            obj_paths = _fallback_rect_path_for_bbox(vobj)

        path_start = len(all_paths)
        for p in obj_paths:
            p["label"] = vobj.label
            all_paths.append(p)
        path_end = len(all_paths)

        if path_start >= path_end:
            continue

        objects.append(
            {
                "label": vobj.label,
                "bbox": [vobj.x, vobj.y, vobj.w, vobj.h],
                "path_start": path_start,
                "path_end": path_end,
                "path_count": path_end - path_start,
            }
        )
        object_labels.append(vobj.label)
        debug_objects.append(
            {
                "label": vobj.label,
                "bbox": [vobj.x, vobj.y, vobj.w, vobj.h],
                "path_count": path_end - path_start,
            }
        )

    if not all_paths:
        logger.warning("No contour paths extracted; using full-image fallback")
        full_paths = extract_svg_paths_from_crop(img, 0, 0)
        if not full_paths:
            full_paths = _fallback_rect_path_for_bbox(
                VisionObject("drawing", 0, 0, width, height)
            )
        all_paths = [{**p, "label": "drawing"} for p in full_paths]
        objects = [
            {
                "label": "drawing",
                "bbox": [0, 0, width, height],
                "path_start": 0,
                "path_end": len(all_paths),
                "path_count": len(all_paths),
            }
        ]
        object_labels = ["drawing"]

    if debug_output_path:
        debug_output_path.parent.mkdir(parents=True, exist_ok=True)
        debug_output_path.write_text(
            json.dumps(
                {
                    "backend": "vision_contour",
                    "image_path": str(image_path),
                    "objects": debug_objects,
                    "path_count": len(all_paths),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return {
        "width": width,
        "height": height,
        "stroke_mode": "svg_contour",
        "segmentation_backend": "vision_contour",
        "paths": all_paths,
        "objects": objects,
        "path_count": len(all_paths),
        "object_count": len(objects),
        "object_labels": object_labels,
        "cells": [],
        "split_len": settings.png_stroke_split_len,
    }


def _fallback_rect_path_for_bbox(vobj: VisionObject) -> List[Dict]:
    """Rectangle outline when edge detection finds no contours in crop."""
    x0, y0 = vobj.x, vobj.y
    x1, y1 = vobj.x + vobj.w, vobj.y + vobj.h
    d = f"M{x0},{y0} L{x1},{y0} L{x1},{y1} L{x0},{y1} Z"
    length = 2 * (vobj.w + vobj.h)
    return [{"d": d, "length": float(length), "area": vobj.w * vobj.h}]
