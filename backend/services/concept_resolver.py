"""Concept Resolver Service implementing 5-stage concept resolution pipeline."""
import re
from difflib import SequenceMatcher
from typing import Optional

from models.schemas import ResolutionResult
from services.concept_catalog import CANONICAL_CONCEPTS, ONTOLOGY_ALIASES


def _normalize(text: str) -> str:
    """Normalize concept string for comparison.
    
    Converts to lowercase, strips, replaces underscores and hyphens with spaces,
    and collapses multiple spaces into a single space.
    """
    if not text:
        return ""
    text = text.lower().strip().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)


def resolve_concept(concept: str, lesson_domain: Optional[str] = None) -> ResolutionResult:
    """Resolve a natural language concept to a canonical ontology concept.
    
    Performs 5 stages of resolution:
    1. Exact Match (case-insensitive, normalized against target domain canonical concepts)
    2. Alias Match (against target domain aliases in ONTOLOGY_ALIASES)
    3. Ontology Match (word-boundary sub-phrase match in target domain)
    4. Semantic Match (SequenceMatcher ratio >= 0.7 restricted to target domain)
    5. Fallback (returns 'unknown-concept' with confidence 0.0)
    """
    if not concept:
        return ResolutionResult(
            original_concept="",
            canonical_concept="unknown-concept",
            confidence=0.0,
            resolution_type="fallback",
            lesson_domain=lesson_domain or "unknown",
        )

    # Normalize the input concept
    norm_concept = _normalize(concept)

    # Normalize target domain
    domain = lesson_domain.lower().strip() if lesson_domain else ""
    if domain == "math":
        domain = "mathematics"
    elif domain in ("computer science", "cs"):
        domain = "computer_science"

    # Stage 1: Exact Match (Normalized)
    if domain in CANONICAL_CONCEPTS:
        for canon in CANONICAL_CONCEPTS[domain]:
            if _normalize(canon) == norm_concept:
                return ResolutionResult(
                    original_concept=concept,
                    canonical_concept=canon,
                    confidence=1.0,
                    resolution_type="exact_match",
                    lesson_domain=domain,
                )
    else:
        # Try exact match across all domains if domain is empty/invalid
        for d, canons in CANONICAL_CONCEPTS.items():
            for canon in canons:
                if _normalize(canon) == norm_concept:
                    return ResolutionResult(
                        original_concept=concept,
                        canonical_concept=canon,
                        confidence=1.0,
                        resolution_type="exact_match",
                        lesson_domain=d,
                    )

    # Stage 2: Alias Match
    if domain in ONTOLOGY_ALIASES:
        for alias, canon in ONTOLOGY_ALIASES[domain].items():
            if _normalize(alias) == norm_concept:
                return ResolutionResult(
                    original_concept=concept,
                    canonical_concept=canon,
                    confidence=1.0,
                    resolution_type="alias_match",
                    lesson_domain=domain,
                )
    else:
        # Try alias match across all domains if domain is empty/invalid
        for d, aliases in ONTOLOGY_ALIASES.items():
            for alias, canon in aliases.items():
                if _normalize(alias) == norm_concept:
                    return ResolutionResult(
                        original_concept=concept,
                        canonical_concept=canon,
                        confidence=1.0,
                        resolution_type="alias_match",
                        lesson_domain=d,
                    )

    # Stage 3: Ontology Match (Sub-phrase word boundary match)
    if domain in CANONICAL_CONCEPTS:
        # Sort by length descending to prefer longer/more specific concepts
        sorted_canons = sorted(CANONICAL_CONCEPTS[domain], key=len, reverse=True)
        for canon in sorted_canons:
            norm_canon = _normalize(canon)
            pattern = r"\b" + re.escape(norm_canon) + r"\b"
            if re.search(pattern, norm_concept):
                return ResolutionResult(
                    original_concept=concept,
                    canonical_concept=canon,
                    confidence=0.9,
                    resolution_type="ontology_match",
                    lesson_domain=domain,
                )
    else:
        # Try sub-phrase match across all domains
        all_canons = []
        for d, canons in CANONICAL_CONCEPTS.items():
            for canon in canons:
                all_canons.append((canon, d))
        all_canons.sort(key=lambda x: len(x[0]), reverse=True)
        for canon, d in all_canons:
            norm_canon = _normalize(canon)
            pattern = r"\b" + re.escape(norm_canon) + r"\b"
            if re.search(pattern, norm_concept):
                return ResolutionResult(
                    original_concept=concept,
                    canonical_concept=canon,
                    confidence=0.9,
                    resolution_type="ontology_match",
                    lesson_domain=d,
                )

    # Stage 4: Semantic Match (SequenceMatcher ratio >= 0.7 restricted to target domain)
    if domain in CANONICAL_CONCEPTS:
        best_ratio = 0.0
        best_canon = None
        for canon in CANONICAL_CONCEPTS[domain]:
            norm_canon = _normalize(canon)
            ratio = SequenceMatcher(None, norm_concept, norm_canon).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_canon = canon
        if best_ratio >= 0.7:
            return ResolutionResult(
                original_concept=concept,
                canonical_concept=best_canon,
                confidence=round(best_ratio, 2),
                resolution_type="semantic_match",
                lesson_domain=domain,
            )

    # Stage 5: Fallback
    return ResolutionResult(
        original_concept=concept,
        canonical_concept="unknown-concept",
        confidence=0.0,
        resolution_type="fallback",
        lesson_domain=domain or "unknown",
    )
