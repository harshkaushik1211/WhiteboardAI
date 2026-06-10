"""Position retrieved SVG assets into educational scene layouts."""
import math
from typing import Dict, List, Optional, Tuple

from models.schemas import (
    Point,
    Position,
    RetrievedAsset,
    SceneElement,
    ScenePlanSchema,
    SemanticScenePlan,
    Size,
    VisualConnection,
)
from utils.timing import (
    CANVAS_CENTER_X,
    CANVAS_CENTER_Y,
    CANVAS_H,
    CANVAS_W,
    DEFAULT_SHAPE_H,
    DEFAULT_SHAPE_W,
    MIN_TEXT_W,
)

PRIMARY_W = 420
PRIMARY_H = 360
SECONDARY_W = 300
SECONDARY_H = 260
LABEL_H = 70


def _importance_size(importance: str) -> Tuple[float, float]:
    if importance == "primary":
        return PRIMARY_W, PRIMARY_H
    return SECONDARY_W, SECONDARY_H


def _bbox(x: float, y: float, w: float, h: float) -> Tuple[float, float, float, float]:
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def _overlaps(a, b, margin: float = 40) -> bool:
    return not (
        a[2] + margin < b[0]
        or b[2] + margin < a[0]
        or a[3] + margin < b[1]
        or b[3] + margin < a[1]
    )


class LayoutEngine:
    def compose(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> ScenePlanSchema:
        layout = semantic.layout_type or "flow_diagram"
        handlers = {
            "flow_diagram": self._layout_flow,
            "process_pipeline": self._layout_pipeline,
            "comparison": self._layout_comparison,
            "hierarchy": self._layout_hierarchy,
            "circular_process": self._layout_circular,
            "labeled_anatomy": self._layout_anatomy,
            "timeline": self._layout_timeline,
            "zoom_focus": self._layout_zoom_focus,
            "single_diagram": self._layout_single_diagram,
        }
        handler = handlers.get(layout, self._layout_flow)
        elements, positions = handler(semantic, retrieved, importance_map)
        if layout != "single_diagram":
            elements.extend(self._connection_arrows(semantic.connections, positions))
        headline = semantic.headline or (semantic.topic if semantic.scene_id == 1 else "")
        if headline:
            title_el = self._scene_headline(headline, semantic.scene_id)
            if title_el:
                elements.insert(0, title_el)

        default_camera = {"zoom": 1.0, "focusX": CANVAS_CENTER_X, "focusY": CANVAS_CENTER_Y}
        camera = semantic.camera if semantic.camera else default_camera

        return ScenePlanSchema(
            scene_id=semantic.scene_id,
            background="white",
            camera=camera,
            elements=elements,
        )

    def _layout_single_diagram(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        """One full diagram SVG, static per scene; camera pans/zooms in Remotion."""
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        if not retrieved:
            return elements, positions

        asset = retrieved[0]
        diagram_w = 980.0
        diagram_h = 980.0
        y_center = CANVAS_CENTER_Y + 30
        scene_id = semantic.scene_id if semantic.scene_id is not None else 1
        # First scene: colored stroke reveal; later scenes: full diagram + camera only
        diagram_anim = "stroke_reveal" if scene_id == 1 else "static"
        el = SceneElement(
            id="photosynthesis-diagram",
            type="svg",
            concept=asset.concept,
            asset_id=asset.asset_id,
            asset_library_path=asset.library_path,
            position=Position(x=CANVAS_CENTER_X, y=y_center),
            size=Size(w=diagram_w, h=diagram_h),
            animation=diagram_anim,
            delay=0.0,
            duration=0.0,
        )
        elements.append(el)
        positions[asset.concept.lower()] = Position(x=CANVAS_CENTER_X, y=y_center)
        return elements, positions

    def _layout_flow(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        n = len(retrieved)
        if n == 0:
            return [], {}

        start_x = 220 if n <= 3 else 160
        end_x = CANVAS_W - 220
        y = CANVAS_CENTER_Y
        spacing = (end_x - start_x) / max(n - 1, 1)

        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        placed: List[Tuple] = []

        for i, asset in enumerate(retrieved):
            imp = importance_map.get(asset.concept, "secondary")
            w, h = _importance_size(imp)
            x = start_x + i * spacing if n > 1 else CANVAS_CENTER_X
            x, y_adj = self._avoid_overlap(x, y, w, h, placed)
            placed.append(_bbox(x, y_adj, w, h))

            el = self._asset_element(asset, x, y_adj, w, h, imp, i)
            elements.append(el)
            positions[asset.concept.lower()] = Position(x=x, y=y_adj)
            label = self._label_below(asset.concept, x, y_adj, h, i)
            if label:
                elements.append(label)

        return elements, positions

    def _layout_pipeline(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        return self._layout_flow(semantic, retrieved, importance_map)

    def _layout_comparison(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        cols = [CANVAS_W * 0.32, CANVAS_W * 0.68]
        for i, asset in enumerate(retrieved[:2]):
            imp = importance_map.get(asset.concept, "primary")
            w, h = _importance_size(imp)
            x, y = cols[i], CANVAS_CENTER_Y
            el = self._asset_element(asset, x, y, w, h, imp, i)
            elements.append(el)
            positions[asset.concept.lower()] = Position(x=x, y=y)
            elements.append(self._label_below(asset.concept, x, y, h, i))
        extras = retrieved[2:]
        for j, asset in enumerate(extras):
            imp = "secondary"
            w, h = SECONDARY_W, SECONDARY_H
            x = CANVAS_CENTER_X
            y = CANVAS_H - 200 - j * 80
            elements.append(self._asset_element(asset, x, y, w, h, imp, j + 2))
            positions[asset.concept.lower()] = Position(x=x, y=y)
        return elements, positions

    def _layout_hierarchy(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        if not retrieved:
            return elements, positions

        primary = retrieved[0]
        imp = importance_map.get(primary.concept, "primary")
        w, h = _importance_size(imp)
        elements.append(self._asset_element(primary, CANVAS_CENTER_X, 320, w, h, imp, 0))
        positions[primary.concept.lower()] = Position(x=CANVAS_CENTER_X, y=320)

        children = retrieved[1:]
        n = len(children)
        span = min(CANVAS_W - 400, n * 280)
        start_x = CANVAS_CENTER_X - span / 2
        for i, asset in enumerate(children):
            x = start_x + (i + 0.5) * (span / max(n, 1))
            w, h = SECONDARY_W, SECONDARY_H
            elements.append(self._asset_element(asset, x, 720, w, h, "secondary", i + 1))
            positions[asset.concept.lower()] = Position(x=x, y=720)
            elements.append(self._label_below(asset.concept, x, 720, h, i + 1))

        return elements, positions

    def _layout_circular(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        n = len(retrieved)
        if n == 0:
            return elements, positions

        cx, cy = CANVAS_CENTER_X, CANVAS_CENTER_Y
        radius = 280 if n <= 4 else 340
        for i, asset in enumerate(retrieved):
            angle = (2 * math.pi * i / n) - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            imp = importance_map.get(asset.concept, "secondary")
            w, h = _importance_size(imp)
            elements.append(self._asset_element(asset, x, y, w, h, imp, i))
            positions[asset.concept.lower()] = Position(x=x, y=y)
            elements.append(self._label_below(asset.concept, x, y, h, i))

        return elements, positions

    def _layout_anatomy(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        if not retrieved:
            return elements, positions

        primary_idx = 0
        for i, asset in enumerate(retrieved):
            if importance_map.get(asset.concept) == "primary":
                primary_idx = i
                break

        primary = retrieved[primary_idx]
        pw, ph = PRIMARY_W + 40, PRIMARY_H + 40
        elements.append(self._asset_element(primary, CANVAS_CENTER_X, CANVAS_CENTER_Y, pw, ph, "primary", 0))
        positions[primary.concept.lower()] = Position(x=CANVAS_CENTER_X, y=CANVAS_CENTER_Y)

        satellites = [a for j, a in enumerate(retrieved) if j != primary_idx]
        n = len(satellites)
        radius = 380
        for i, asset in enumerate(satellites):
            angle = (2 * math.pi * i / max(n, 1)) - math.pi / 2
            x = CANVAS_CENTER_X + radius * math.cos(angle)
            y = CANVAS_CENTER_Y + radius * math.sin(angle)
            w, h = SECONDARY_W, SECONDARY_H
            elements.append(self._asset_element(asset, x, y, w, h, "secondary", i + 1))
            positions[asset.concept.lower()] = Position(x=x, y=y)
            elements.append(self._label_below(asset.concept, x, y, h, i + 1))

        return elements, positions

    def _layout_timeline(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        return self._layout_flow(semantic, retrieved, importance_map)

    def _layout_zoom_focus(
        self,
        semantic: SemanticScenePlan,
        retrieved: List[RetrievedAsset],
        importance_map: Dict[str, str],
    ) -> Tuple[List[SceneElement], Dict[str, Position]]:
        """Magnifying glass centered, leaf offset — zoom-on-detail scene."""
        elements: List[SceneElement] = []
        positions: Dict[str, Position] = {}
        if not retrieved:
            return elements, positions

        magnify = None
        leaf = None
        others: List[RetrievedAsset] = []
        for asset in retrieved:
            c = asset.concept.lower()
            if "magnif" in c or "zoom" in c:
                magnify = asset
            elif "leaf" in c:
                leaf = asset
            else:
                others.append(asset)

        if magnify:
            elements.append(
                self._asset_element(
                    magnify, CANVAS_CENTER_X - 120, CANVAS_CENTER_Y, 480, 420, "primary", 0
                )
            )
            positions[magnify.concept.lower()] = Position(x=CANVAS_CENTER_X - 120, y=CANVAS_CENTER_Y)

        if leaf:
            elements.append(
                self._asset_element(
                    leaf, CANVAS_CENTER_X + 320, CANVAS_CENTER_Y + 40, 380, 340, "secondary", 1
                )
            )
            positions[leaf.concept.lower()] = Position(x=CANVAS_CENTER_X + 320, y=CANVAS_CENTER_Y + 40)
            elements.append(self._label_below(leaf.concept, CANVAS_CENTER_X + 320, CANVAS_CENTER_Y + 40, 340, 1))

        for i, asset in enumerate(others):
            elements.append(
                self._asset_element(
                    asset,
                    CANVAS_CENTER_X - 400 + i * 200,
                    CANVAS_CENTER_Y + 200,
                    SECONDARY_W,
                    SECONDARY_H,
                    "secondary",
                    i + 2,
                )
            )
            positions[asset.concept.lower()] = Position(
                x=CANVAS_CENTER_X - 400 + i * 200, y=CANVAS_CENTER_Y + 200
            )

        return elements, positions

    def _avoid_overlap(
        self, x: float, y: float, w: float, h: float, placed: List[Tuple]
    ) -> Tuple[float, float]:
        box = _bbox(x, y, w, h)
        for _ in range(8):
            collision = False
            for p in placed:
                if _overlaps(box, p):
                    y += 60
                    box = _bbox(x, y, w, h)
                    collision = True
                    break
            if not collision:
                break
        return x, y

    def _asset_element(
        self,
        asset: RetrievedAsset,
        x: float,
        y: float,
        w: float,
        h: float,
        importance: str,
        index: int,
    ) -> SceneElement:
        delay = 0.5 + index * 1.2
        duration = 5.0 if importance == "primary" else 4.5
        return SceneElement(
            id=f"asset-{asset.concept.replace(' ', '-')}-{index}",
            type="svg",
            concept=asset.concept,
            asset_id=asset.asset_id,
            asset_library_path=asset.library_path,
            position=Position(x=x, y=y),
            size=Size(w=w, h=h),
            animation="stroke_reveal",
            delay=delay,
            duration=duration,
            label=asset.concept.replace("_", " ").title(),
            color="#1a1a2e",
        )

    def _label_below(
        self, concept: str, x: float, y: float, h: float, index: int
    ) -> Optional[SceneElement]:
        return SceneElement(
            id=f"label-{concept.replace(' ', '-')}-{index}",
            type="label",
            text=concept.replace("_", " ").title(),
            position=Position(x=x, y=y + h / 2 + 45),
            size=Size(w=MIN_TEXT_W, h=LABEL_H),
            animation="fade_in",
            delay=0.8 + index * 1.2,
            duration=2.0,
            color="#1a1a2e",
        )

    def _scene_headline(self, headline: str, scene_id: int) -> Optional[SceneElement]:
        if not headline:
            return None
        return SceneElement(
            id=f"scene-headline-{scene_id}",
            type="text",
            text=headline[:48],
            position=Position(x=CANVAS_CENTER_X, y=88),
            size=Size(w=900, h=100),
            animation="static",
            delay=0.0,
            duration=0.0,
            color="#1a1a2e",
        )

    def _connection_arrows(
        self,
        connections: List[VisualConnection],
        positions: Dict[str, Position],
    ) -> List[SceneElement]:
        arrows: List[SceneElement] = []
        for i, conn in enumerate(connections):
            f_key = conn.from_concept.lower()
            t_key = conn.to_concept.lower()
            if f_key not in positions or t_key not in positions:
                continue
            fp = positions[f_key]
            tp = positions[t_key]
            arrows.append(
                SceneElement(
                    id=f"conn-arrow-{i}",
                    type="arrow",
                    from_point=Point(x=fp.x + 100, y=fp.y),
                    to_point=Point(x=tp.x - 100, y=tp.y),
                    animation="stroke_reveal",
                    delay=2.2 + i * 0.9,
                    duration=4.0,
                    label=None,
                    color="#1a1a2e",
                )
            )
        return arrows


layout_engine = LayoutEngine()
