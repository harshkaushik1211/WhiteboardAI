"""Build and load semantic SVG asset index."""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from config import settings

SKIP_PARTS = {"index", "svg-templates", "semantic_memory.json"}
INDEX_PATH = settings.assets_path / "index" / "assets_index.json"

# Concept aliases for tagging
CONCEPT_TAGS: Dict[str, List[str]] = {
    "lungs": ["biology", "respiration", "lungs", "human organ", "breathing"],
    "mitochondria": ["biology", "cell", "mitochondria", "energy", "respiration"],
    "oxygen": ["biology", "chemistry", "oxygen", "o2", "molecule"],
    "glucose": ["biology", "sugar", "glucose", "energy"],
    "cell": ["biology", "cell", "organism"],
    "atp": ["biology", "energy", "atp", "mitochondria"],
    "bloodstream": ["biology", "blood", "circulation", "respiration"],
    "leaf": ["biology", "photosynthesis", "plant"],
    "plant": ["biology", "photosynthesis", "plant", "tree"],
    "magnify": ["biology", "photosynthesis", "zoom", "magnify", "magnifier"],
    "search-magnify-magnifier-glass": ["biology", "zoom", "magnify"],
    "photosynthesis_diagram": ["biology", "photosynthesis", "diagram", "plant"],
    "chloroplast": ["biology", "photosynthesis", "plant", "cell"],
    "car": ["physics", "motion", "vehicle", "newton"],
    "ball": ["physics", "motion", "newton"],
    "force": ["physics", "force", "arrow", "newton"],
    "array": ["math", "computer_science", "array", "binary search"],
    "client": ["computer_science", "network", "tcp", "client"],
    "server": ["computer_science", "network", "tcp", "server"],
    "handshake": ["computer_science", "tcp", "network", "protocol"],
    "packet": ["computer_science", "network", "data"],
}


def _infer_concept(filename: str) -> str:
    stem = filename.replace(".svg", "")
    for suffix in ("-svgrepo-com", "-svgrepo"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem.replace("_", " ").strip()


def _infer_category(rel_path: Path) -> str:
    parts = rel_path.parts
    if len(parts) >= 2:
        return parts[0]
    return "icons"


def rebuild_index() -> List[dict]:
    assets_root = settings.assets_path
    entries: List[dict] = []

    asset_paths = sorted(assets_root.rglob("*.svg")) + sorted(assets_root.rglob("*.png"))
    for svg_path in asset_paths:
        rel = svg_path.relative_to(assets_root)
        if any(p in SKIP_PARTS for p in rel.parts):
            continue
        if rel.parts[0] in SKIP_PARTS:
            continue

        concept = _infer_concept(svg_path.stem)
        if "photosynthesis-diagram" in svg_path.stem:
            concept = "photosynthesis_diagram"
        category = _infer_category(rel)
        tags = list(CONCEPT_TAGS.get(concept, [category, concept]))
        asset_id = f"{category}_{svg_path.stem}".replace("/", "_").replace(" ", "_")
        style = "raster" if svg_path.suffix.lower() == ".png" else "outline"

        entries.append({
            "id": asset_id,
            "concept": concept,
            "tags": tags,
            "style": style,
            "category": category,
            "path": str(rel).replace("\\", "/"),
            "domain": category,
            "concepts": list({concept} | set(tags)),
        })

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def load_index(force_rebuild: bool = False) -> List[dict]:
    if force_rebuild or not INDEX_PATH.exists():
        return rebuild_index()
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def get_index(force_reload: bool = False) -> List[dict]:
    """Load index from disk, rebuilding if missing or force_reload."""
    if force_reload or not INDEX_PATH.exists():
        return rebuild_index()
    return load_index()


def ensure_paths_indexed(paths: List[str]) -> List[dict]:
    """Rebuild index if any library paths are missing from the current index."""
    normalized = {p.replace("\\", "/") for p in paths}
    index = load_index() if INDEX_PATH.exists() else []
    indexed_paths = {e.get("path", "").replace("\\", "/") for e in index}
    missing = normalized - indexed_paths
    if missing:
        for rel in missing:
            full = settings.assets_path / rel
            if not full.exists():
                raise FileNotFoundError(f"Asset file not found: {full}")
        return rebuild_index()
    return index


if __name__ == "__main__":
    import sys
    force = "--rebuild" in sys.argv
    entries = rebuild_index() if force else get_index()
    print(f"Index: {len(entries)} assets -> {INDEX_PATH}")
