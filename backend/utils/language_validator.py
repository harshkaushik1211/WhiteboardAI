import re

# Unicode range for Devanagari script: U+0900 to U+097F
DEVANAGARI_PATTERN = re.compile(r'[\u0900-\u097F]')

def contains_devanagari(text: str) -> bool:
    """Returns True if the text contains any Devanagari (Hindi) characters."""
    if not text:
        return False
    return bool(DEVANAGARI_PATTERN.search(text))
