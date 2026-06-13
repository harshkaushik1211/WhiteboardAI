"""Text chunker for XTTS-v2.

XTTS has a hard token limit of ~400 tokens per generation call.
Long narration must be split into safe chunks before synthesis.

Strategy:
    1. Split on sentence boundaries (period, ?, !, Devanagari danda ।)
    2. Accumulate sentences into chunks until char budget is reached.
    3. Return list of non-empty chunk strings.

Char budget of 150 is conservative for Devanagari text (which is denser
in tokens per character than ASCII).  Roman Hindi text uses a budget of
180 chars to match token density.
"""

from __future__ import annotations

import re
from typing import List


# Maximum characters per XTTS generation call.
# Empirically safe limit that avoids the 400-token hard cap.
_DEVANAGARI_BUDGET = 150   # Devanagari chars → ~350 tokens
_ROMAN_BUDGET = 180        # Roman chars    → ~350 tokens (tokens are fewer per char)


def _is_devanagari(text: str) -> bool:
    """Return True if the text contains Devanagari script characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on sentence-ending punctuation."""
    # Handles: . ? ! ।  followed by space or end of string
    raw = re.split(r"(?<=[.?!।])\s+", text.strip())
    # Filter empties, preserve trailing punctuation
    return [s.strip() for s in raw if s.strip()]


def chunk_text(text: str, max_chars: int | None = None) -> List[str]:
    """Split *text* into XTTS-safe chunks.

    Args:
        text:      Full narration text (any script).
        max_chars: Override the character budget.  If None, the budget
                   is chosen automatically based on script detection.

    Returns:
        A list of text strings, each safe to pass to XTTS ``tts_to_file``.
        At minimum one chunk is returned.
    """
    if not text or not text.strip():
        return []

    budget = max_chars or (_DEVANAGARI_BUDGET if _is_devanagari(text) else _ROMAN_BUDGET)
    sentences = _split_sentences(text)

    if not sentences:
        # Fallback: hard-split on budget
        return [text[i : i + budget] for i in range(0, len(text), budget)]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # If a single sentence exceeds budget, force-split it
        if sentence_len > budget:
            # Flush current buffer first
            if current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            # Hard split the long sentence
            for i in range(0, sentence_len, budget):
                chunks.append(sentence[i : i + budget])
            continue

        if current_len + sentence_len + (1 if current else 0) > budget:
            # Flush and start new chunk
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = sentence_len
        else:
            current.append(sentence)
            current_len += sentence_len + (1 if len(current) > 1 else 0)

    # Flush remaining
    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]
