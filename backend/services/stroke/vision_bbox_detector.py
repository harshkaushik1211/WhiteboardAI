"""OpenAI Vision: detect logical objects and bounding boxes (storyboard-ai step 1)."""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config import settings

logger = logging.getLogger("vision_bbox_detector")

BBOX_SYSTEM = """You detect drawable object groups in educational whiteboard sketches.
Return valid JSON only:
{
  "objects": [
    {"label": "short name", "bbox": [ymin, xmin, ymax, xmax]}
  ]
}
Rules:
- bbox values are normalized 0-1000 (image top-left origin: y down, x right)
- List 3-5 largest logical groups (not tiny details)
- Group related parts (e.g. "bicycle" not separate wheels)
- Exclude hands, pens, whiteboard frame, empty background
- ymin < ymax and xmin < xmax"""


@dataclass
class VisionObject:
    label: str
    # pixel coords on canvas: x, y, w, h
    x: int
    y: int
    w: int
    h: int


def _vision_encode_image(path: Path, max_side: int) -> Tuple[str, int, int]:
    """JPEG thumbnail for vision API — much smaller than full-res PNG base64."""
    img = cv2.imread(str(path))
    if img is None:
        raw = path.read_bytes()
        return base64.b64encode(raw).decode("ascii"), 0, 0

    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    ok, buf = cv2.imencode(
        ".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
    )
    if not ok:
        return base64.b64encode(path.read_bytes()).decode("ascii"), w, h
    return base64.b64encode(buf.tobytes()).decode("ascii"), w, h


def _scale_bbox_to_canvas(
    x: int, y: int, w: int, h: int, thumb_w: int, thumb_h: int, width: int, height: int
) -> Tuple[int, int, int, int]:
    if thumb_w <= 0 or thumb_h <= 0:
        return x, y, w, h
    sx = width / thumb_w
    sy = height / thumb_h
    return int(x * sx), int(y * sy), max(8, int(w * sx)), max(8, int(h * sy))


def _clamp_bbox_pixels(
    ymin: float,
    xmin: float,
    ymax: float,
    xmax: float,
    width: int,
    height: int,
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    """Convert 0-1000 normalized bbox to pixel x,y,w,h with padding."""
    y0 = int(ymin / 1000.0 * height)
    x0 = int(xmin / 1000.0 * width)
    y1 = int(ymax / 1000.0 * height)
    x1 = int(xmax / 1000.0 * width)

    if y0 > y1:
        y0, y1 = y1, y0
    if x0 > x1:
        x0, x1 = x1, x0

    pad_x = int((x1 - x0) * padding_ratio)
    pad_y = int((y1 - y0) * padding_ratio)
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(width, x1 + pad_x)
    y1 = min(height, y1 + pad_y)

    w = max(8, x1 - x0)
    h = max(8, y1 - y0)
    return x0, y0, w, h


def _fallback_from_hints(
    object_hints: Optional[List[str]],
    visual_description: str,
    width: int,
    height: int,
) -> List[VisionObject]:
    """Single full-canvas object when vision is unavailable."""
    labels: List[str] = []
    if object_hints:
        labels = [h.strip().lower() for h in object_hints if h and h.strip()][:5]
    if not labels and visual_description:
        labels = ["drawing"]
    if not labels:
        labels = ["drawing"]

    n = len(labels)
    if n == 1:
        return [VisionObject(label=labels[0], x=0, y=0, w=width, h=height)]

    cols = 2 if n > 2 else n
    rows = (n + cols - 1) // cols
    cell_w = width // cols
    cell_h = height // rows
    out: List[VisionObject] = []
    for i, label in enumerate(labels):
        row, col = divmod(i, cols)
        out.append(
            VisionObject(
                label=label,
                x=col * cell_w,
                y=row * cell_h,
                w=cell_w,
                h=cell_h,
            )
        )
    return out


async def detect_object_bboxes(
    image_path: str,
    width: int,
    height: int,
    visual_description: str = "",
    object_hints: Optional[List[str]] = None,
) -> List[VisionObject]:
    path = Path(image_path)
    if not path.exists():
        return _fallback_from_hints(object_hints, visual_description, width, height)

    if not settings.openai_api_key:
        logger.warning("No OPENAI_API_KEY; using keyword fallback bboxes")
        return _fallback_from_hints(object_hints, visual_description, width, height)

    try:
        from services.llm_service import llm_service

        max_side = max(256, settings.vision_image_max_side)
        image_b64, thumb_w, thumb_h = _vision_encode_image(path, max_side)
        mime = "image/jpeg" if thumb_w > 0 else (
            "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        )
        hints = ", ".join(object_hints) if object_hints else "none"
        vision_w = thumb_w or width
        vision_h = thumb_h or height
        user_text = (
            f"Image size: {vision_w}x{vision_h} pixels.\n"
            f"Visual description: {visual_description or 'educational whiteboard sketch'}\n"
            f"Script keywords: {hints}\n"
            f"Return up to {settings.vision_max_objects} objects with bboxes."
        )

        response = await llm_service.client.chat.completions.create(
            model=settings.segmentation_vision_model,
            messages=[
                {"role": "system", "content": BBOX_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=512,
        )
        content = response.choices[0].message.content or "{}"
        data = llm_service._parse_json(content)
        raw_objects = data.get("objects") or []

        results: List[VisionObject] = []
        for item in raw_objects[: settings.vision_max_objects]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "object")).strip().lower() or "object"
            bbox = item.get("bbox") or item.get("box")
            if not bbox or len(bbox) < 4:
                continue
            ymin, xmin, ymax, xmax = [float(v) for v in bbox[:4]]
            x, y, w, h = _clamp_bbox_pixels(
                ymin, xmin, ymax, xmax, vision_w, vision_h, settings.vision_bbox_padding
            )
            x, y, w, h = _scale_bbox_to_canvas(
                x, y, w, h, vision_w, vision_h, width, height
            )
            results.append(VisionObject(label=label, x=x, y=y, w=w, h=h))

        if results:
            logger.info("Vision detected %d objects: %s", len(results), [o.label for o in results])
            return results
    except Exception as exc:
        logger.warning("Vision bbox detection failed: %s", exc)

    return _fallback_from_hints(object_hints, visual_description, width, height)
