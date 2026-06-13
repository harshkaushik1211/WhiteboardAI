import sys
import os
import shutil
import logging
from pathlib import Path

# Setup basic logging to see XlitEngine initialization and warnings
logging.basicConfig(level=logging.INFO)

# Make sure backend is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── Windows Console Safe Print ───────────────────────────────────────────────
def safe_print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    text = sep.join(str(arg) for arg in args)
    try:
        file.write(text + end)
        file.flush()
    except UnicodeEncodeError:
        encoding = getattr(file, "encoding", "utf-8") or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding)
        file.write(safe_text + end)
        file.flush()

print = safe_print

def test_transliteration_accuracy():
    print("=" * 60)
    print("Testing Transliterator Accuracy and Normalization")
    print("=" * 60)
    from services.transliteration import transliterate_hinglish

    # Test cases: Input vs expected Devanagari words/phrases
    test_cases = [
        {
            "input": "Force ek push ya pull hota hai.",
            "expected_terms": ["फोर्स", "पुश", "पुल"]
        },
        {
            "input": "Photosynthesis plants ka food banane ka process hai.",
            "expected_terms": ["फोटोसिंथेसिस", "प्लांट्स", "फूड", "प्रोसेस"]
        },
        {
            "input": "React Frontend aur FastAPI Backend use karte hain.",
            "expected_terms": ["रिएक्ट", "फ्रंटेंड", "फास्ट", "एपीआई", "बैकएंड"]
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\nCase {i}: '{case['input']}'")
        output = transliterate_hinglish(case["input"])
        print(f"Output: '{output}'")
        
        # Check terms
        all_passed = True
        for term in case["expected_terms"]:
            if term not in output:
                print(f"  [FAIL] Expected term '{term}' not found in output!")
                all_passed = False
            else:
                print(f"  [PASS] Found term '{term}'")
        
        if all_passed:
            print("  [SUCCESS] All expected terms found.")
        else:
            raise AssertionError(f"Case {i} failed transliteration check!")

def test_transliteration_caching():
    print("\n" + "=" * 60)
    print("Testing Transliteration Caching")
    print("=" * 60)
    import time
    from services.transliteration import transliterate_hinglish
    from services.transliteration.indicxlit_service import _transliteration_cache

    input_text = "Docker aur Kubernetes microservices deploy karte hain."
    
    # 1st call (Cache Miss)
    t0 = time.perf_counter()
    res1 = transliterate_hinglish(input_text)
    t1 = time.perf_counter()
    time_miss = t1 - t0
    print(f"1st call (Miss): {time_miss:.4f}s")
    
    # Verify cache content
    assert input_text in _transliteration_cache, "Original input not stored in cache!"
    
    # 2nd call (Cache Hit)
    t2 = time.perf_counter()
    res2 = transliterate_hinglish(input_text)
    t3 = time.perf_counter()
    time_hit = t3 - t2
    print(f"2nd call (Hit): {time_hit:.4f}s")
    
    assert res1 == res2, "Cached output does not match original output!"
    # Hit should be sub-millisecond, whereas miss is ~50-100ms
    assert time_hit < time_miss, "Cache hit was not faster than cache miss!"
    print(f"  [PASS] Caching working as expected. Speedup factor: {time_miss / time_hit:.1f}x")

def test_fallback_behavior():
    print("\n" + "=" * 60)
    print("Testing Fallback Behavior on Exception")
    print("=" * 60)
    from services.transliteration import transliterate_hinglish
    import services.transliteration.indicxlit_service as service
    
    # Mock _get_engine to raise an exception
    orig_get_engine = service._get_engine
    def mock_get_engine():
        raise RuntimeError("Simulated model loading error")
    
    service._get_engine = mock_get_engine
    
    input_text = "Failure test input text here."
    # Temporarily clear cache for this text
    if input_text in service._transliteration_cache:
        del service._transliteration_cache[input_text]
        
    try:
        output = transliterate_hinglish(input_text)
        print(f"Fallback output: '{output}'")
        assert output == input_text, "Fallback did not return original text!"
        print("  [PASS] Graceful fallback on exception succeeded.")
    finally:
        # Restore original engine loader
        service._get_engine = orig_get_engine

if __name__ == "__main__":
    try:
        test_transliteration_accuracy()
        test_transliteration_caching()
        test_fallback_behavior()
        print("\n" + "=" * 60)
        print("ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        sys.exit(1)
