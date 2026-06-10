from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from models.schemas import RequiredVisual, RetrievedAsset
from services.concept_catalog import normalize_concept
from config import settings
from services.svg_indexer import ensure_paths_indexed, get_index, rebuild_index

REJECT_STYLES = {"filled", "3d", "colorful", "cartoon", "realistic"}
ALLOWED_STYLES = {"outline", "sketch", "raster"}


def _fuzz_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


def _partial_ratio(needle: str, haystack: str) -> float:
    needle, haystack = needle.lower(), haystack.lower()
    if needle in haystack:
        return 95.0
    return _fuzz_ratio(needle, haystack)


def validate_retrieval(
    entry: dict,
    concept: str,
    lesson_domain: Optional[str],
    semantic_score: float,
) -> tuple[bool, Optional[str]]:
    """Validate retrieval candidate. Returns (approved, rejection_reason)."""
    entry_category = entry.get("category", "")
    edu_domains = {"physics", "biology", "chemistry", "computer_science", "math"}
    
    # 1. Domain consistency: Cross-domain matches between different educational subjects are prohibited
    if lesson_domain and lesson_domain in edu_domains:
        if entry_category in edu_domains and entry_category != lesson_domain:
            return False, "domain_mismatch"
            
    # 2. Semantic similarity threshold (Review 4: >= 0.7)
    if semantic_score < 0.7:
        return False, "low_similarity_score"
        
    return True, None


@dataclass
class RetrievalOptions:
    preferred_visuals: List[str] = field(default_factory=list)
    allowed_asset_suffix: Optional[str] = None
    concept_asset_map: Dict[str, str] = field(default_factory=dict)
    allowed_paths: Optional[Set[str]] = None

    @classmethod
    def from_memory(cls, memory_hints: Optional[dict]) -> "RetrievalOptions":
        if not memory_hints:
            return cls()
        cam = memory_hints.get("concept_asset_map") or {}
        # Normalize map keys
        norm_map = {normalize_concept(k): v for k, v in cam.items()}
        allowed_paths = set(norm_map.values()) if norm_map else None
        diagram_asset = memory_hints.get("diagram_asset")
        if diagram_asset and not allowed_paths:
            allowed_paths = {diagram_asset.replace("\\", "/")}
        return cls(
            preferred_visuals=memory_hints.get("preferred_visuals", []),
            allowed_asset_suffix=memory_hints.get("allowed_asset_suffix"),
            concept_asset_map=norm_map,
            allowed_paths=allowed_paths,
        )


class SVGRetriever:
    def __init__(self):
        self._index = get_index()

    def reload(self) -> None:
        self._index = get_index()

    def _fresh_index(self, options: RetrievalOptions) -> List[dict]:
        """Reload index from disk; rebuild if topic asset paths are missing."""
        if options.allowed_paths:
            self._index = ensure_paths_indexed(list(options.allowed_paths))
        else:
            self._index = get_index()
        return self._index

    def _filter_index(self, entries: List[dict], options: RetrievalOptions) -> List[dict]:
        if options.allowed_paths:
            allowed = {p.replace("\\", "/") for p in options.allowed_paths}
            filtered = [
                e for e in entries if e.get("path", "").replace("\\", "/") in allowed
            ]
            if filtered:
                return filtered
            # Fallback: suffix filter (e.g. stale path set in memory)
            if options.allowed_asset_suffix:
                filtered = [
                    e
                    for e in entries
                    if e.get("path", "").endswith(options.allowed_asset_suffix)
                ]
                if filtered:
                    return filtered
            # Last resort: verify files on disk and rebuild index
            for rel in allowed:
                if not (settings.assets_path / rel).exists():
                    raise FileNotFoundError(
                        f"Missing asset file: {settings.assets_path / rel}. "
                        "Check concept_asset_map in semantic_memory.json."
                    )
            self._index = rebuild_index()
            entries = self._index
            filtered = [
                e for e in entries if e.get("path", "").replace("\\", "/") in allowed
            ]
            if filtered:
                return filtered
        if options.allowed_asset_suffix:
            suffix = options.allowed_asset_suffix
            return [e for e in entries if e.get("path", "").endswith(suffix)]
        return entries

    def _score_asset(
        self,
        entry: dict,
        visual: RequiredVisual,
        topic: str,
        options: RetrievalOptions,
        used_asset_ids: Set[str],
        scene_used_concepts: Set[str],
        lesson_domain: Optional[str] = None,
    ) -> float:
        if entry.get("style", "outline") not in ALLOWED_STYLES:
            if entry.get("style") in REJECT_STYLES:
                return -100.0

        concept = normalize_concept(visual.concept)
        canonical = normalize_concept(visual.concept)
        entry_concept = entry.get("concept", "").lower()
        entry_path = entry.get("path", "").replace("\\", "/")

        mapped = options.concept_asset_map.get(canonical) or options.concept_asset_map.get(concept)
        if mapped and entry_path == mapped.replace("\\", "/"):
            return 10.0  # User/memory hint mapping wins immediately
        elif options.concept_asset_map and mapped:
            return -100.0

        # 1. Base semantic similarity (0.0 to 1.0)
        if entry_concept == concept or entry_concept == canonical:
            semantic_similarity = 1.0
        else:
            semantic_similarity = _fuzz_ratio(canonical, entry_concept) / 100.0

        # Integrate keyword/tag match in semantic similarity
        query_keywords = {concept, canonical} | {normalize_concept(k) for k in visual.keywords}
        tag_matches = 0
        for tag in entry.get("tags", []):
            if tag.lower() in query_keywords:
                tag_matches += 1
        if tag_matches > 0:
            semantic_similarity = min(1.0, semantic_similarity + 0.05 * tag_matches)

        # 2. Domain bonus/penalty (Review 1)
        domain_bonus = 0.0
        entry_category = entry.get("category", "")
        edu_domains = {"physics", "biology", "chemistry", "computer_science", "math"}
        if lesson_domain and lesson_domain in edu_domains:
            if entry_category == lesson_domain:
                domain_bonus = 0.15
            elif entry_category in edu_domains:
                domain_bonus = -0.15

        # Combined score (semantic remains primary, domain remains secondary)
        score = semantic_similarity + domain_bonus

        # Suffix alignment
        if options.allowed_asset_suffix and entry_path.endswith(options.allowed_asset_suffix):
            score += 0.25

        # Preferred visual boost
        for pv in options.preferred_visuals:
            if pv.lower() == entry_concept:
                score += 0.08

        # Reuse and density penalties
        if entry["id"] in used_asset_ids:
            score -= 0.20
        if entry_concept in scene_used_concepts and visual.importance != "primary":
            score -= 0.15

        return score

    def retrieve_assets(
        self,
        required_visuals: List[RequiredVisual],
        topic: str,
        used_asset_ids: Set[str],
        preferred_visuals: Optional[List[str]] = None,
        retrieval_options: Optional[RetrievalOptions] = None,
        lesson_domain: Optional[str] = None,
    ) -> List[RetrievedAsset]:
        options = retrieval_options or RetrievalOptions(preferred_visuals=preferred_visuals or [])
        if preferred_visuals and not options.preferred_visuals:
            options.preferred_visuals = preferred_visuals

        entries = self._fresh_index(options)
        index = self._filter_index(entries, options)
        if not index and (options.allowed_paths or options.allowed_asset_suffix):
            raise RuntimeError(
                "No assets matched topic restrictions. "
                "Run: curl -X POST http://localhost:8000/assets/reindex "
                "and confirm *-svgrepo-com.svg files exist under assets/biology/."
            )

        results: List[RetrievedAsset] = []
        scene_concepts: Set[str] = set()

        for visual in required_visuals:
            best_entry = None
            best_score = -999.0

            for entry in index:
                s = self._score_asset(
                    entry, visual, topic, options, used_asset_ids, scene_concepts, lesson_domain
                )
                if s > best_score:
                    best_score = s
                    best_entry = entry

            # Run validation layer
            approved = False
            rejection_reason = None
            semantic_score = 0.0

            if best_entry and best_score > -50.0:
                concept = normalize_concept(visual.concept)
                canonical = normalize_concept(visual.concept)
                entry_concept = best_entry.get("concept", "").lower()
                entry_path = best_entry.get("path", "").replace("\\", "/")

                mapped = options.concept_asset_map.get(canonical) or options.concept_asset_map.get(concept)
                if mapped and entry_path == mapped.replace("\\", "/"):
                    semantic_score = 1.0
                elif entry_concept == concept or entry_concept == canonical:
                    semantic_score = 1.0
                else:
                    semantic_score = _fuzz_ratio(canonical, entry_concept) / 100.0
                    query_keywords = {concept, canonical} | {normalize_concept(k) for k in visual.keywords}
                    tag_matches = sum(1 for tag in best_entry.get("tags", []) if tag.lower() in query_keywords)
                    if tag_matches > 0:
                        semantic_score = min(1.0, semantic_score + 0.05 * tag_matches)

                approved, rejection_reason = validate_retrieval(best_entry, visual.concept, lesson_domain, semantic_score)
            else:
                rejection_reason = "no_candidate_found"

            if best_entry and approved:
                scene_concepts.add(best_entry["concept"].lower())
                used_asset_ids.add(best_entry["id"])
                results.append(
                    RetrievedAsset(
                        concept=visual.concept,
                        asset_id=best_entry["id"],
                        library_path=best_entry["path"],
                        score=best_score,
                        fallback=False,
                        approved=True,
                        rejection_reason=None,
                    )
                )
            else:
                # Fallback on rejection
                fallback = self._fallback_asset(visual.concept, used_asset_ids, index, options)
                fallback.approved = False
                fallback.rejection_reason = rejection_reason or "validation_failed"
                if best_entry:
                    # Log what was attempted so we can store it in the audit
                    fallback.concept = f"{visual.concept} (attempted: {best_entry['id']})"
                    fallback.score = best_score
                results.append(fallback)

        return results

    def _fallback_asset(
        self,
        concept: str,
        used_asset_ids: Set[str],
        index: List[dict],
        options: RetrievalOptions,
    ) -> RetrievedAsset:
        canonical = normalize_concept(concept)
        mapped = options.concept_asset_map.get(canonical)
        if mapped:
            for entry in index:
                if entry.get("path", "").replace("\\", "/") == mapped.replace("\\", "/"):
                    used_asset_ids.add(entry["id"])
                    return RetrievedAsset(
                        concept=concept,
                        asset_id=entry["id"],
                        library_path=entry["path"],
                        score=1.0,
                        fallback=False,
                        approved=True,
                    )

        unknown = "icons/unknown-concept.svg"
        for entry in index:
            if entry["path"] == unknown or entry["concept"] == "unknown-concept":
                used_asset_ids.add(entry["id"])
                return RetrievedAsset(
                    concept=concept,
                    asset_id=entry["id"],
                    library_path=entry["path"],
                    score=0.0,
                    fallback=True,
                    approved=True,
                )
        return RetrievedAsset(
            concept=concept,
            asset_id="fallback_unknown",
            library_path=unknown,
            score=0.0,
            fallback=True,
            approved=True,
        )


svg_retriever = SVGRetriever()
