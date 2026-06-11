"""
Enhanced stroke pipeline:

Image → OpenAI Vision bboxes → ink contour paths per object → ordered SVG strokes
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from config import settings
from services.stroke.contour_to_svg import (
    assign_paths_to_bbox,
    extract_ink_paths_from_image,
    order_paths_for_drawing,
)
from services.stroke.vision_bbox_detector import detect_object_bboxes

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

    # Extract all ink paths once from the full image, then assign to vision objects.
    full_paths = extract_ink_paths_from_image(img, 0, 0)
    logger.info("Extracted %d ink paths from full image", len(full_paths))

    all_paths: List[Dict] = []
    objects: List[Dict] = []
    object_labels: List[str] = []
    debug_objects: List[Dict] = []
    for vobj in vision_objects:
        obj_paths = assign_paths_to_bbox(full_paths, vobj.x, vobj.y, vobj.w, vobj.h)

        if not obj_paths:
            continue

        path_start = len(all_paths)
        for p in obj_paths:
            p["label"] = vobj.label
            all_paths.append(p)
        path_end = len(all_paths)

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

    # Paths not inside any bbox — append at the end in draw order.
    used_d = {p["d"] for p in all_paths}
    leftover = [p for p in full_paths if p["d"] not in used_d]
    if leftover:
        leftover = order_paths_for_drawing(leftover)
        path_start = len(all_paths)
        for p in leftover:
            p["label"] = "detail"
            all_paths.append(p)
        objects.append(
            {
                "label": "detail",
                "bbox": [0, 0, width, height],
                "path_start": path_start,
                "path_end": len(all_paths),
                "path_count": len(all_paths) - path_start,
            }
        )
        object_labels.append("detail")

    if not all_paths:
        logger.warning("No ink paths extracted; using full-image paths")
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
                    "total_stroke_length": round(
                        sum(p.get("length", 0) for p in all_paths), 1
                    ),
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
        "total_stroke_length": round(sum(p.get("length", 0) for p in all_paths), 1),
        "cells": [],
        "split_len": settings.png_stroke_split_len,
    }
