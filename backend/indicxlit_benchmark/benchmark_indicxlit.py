import os
import sys
import json
import time
import re
import traceback
from pathlib import Path

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

# ── Dataclasses Monkey-Patch (Required for Python 3.11+ / Fairseq / Windows) ────
import dataclasses

_orig_get_field = dataclasses._get_field

def _patched_get_field(cls, a_name, a_type, default_kw_only):
    default = getattr(cls, a_name, dataclasses.MISSING)
    if default is not dataclasses.MISSING:
        if isinstance(default, dataclasses.Field):
            orig_val = default.default
            if orig_val is not dataclasses.MISSING and getattr(orig_val, "__class__", None) is not None and getattr(orig_val.__class__, "__hash__", None) is None:
                default.default = "MOCKED_HASHABLE"
                try:
                    f = _orig_get_field(cls, a_name, a_type, default_kw_only)
                    f.default = orig_val
                    return f
                finally:
                    default.default = orig_val
        else:
            orig_val = default
            if getattr(orig_val, "__class__", None) is not None and getattr(orig_val.__class__, "__hash__", None) is None:
                setattr(cls, a_name, "MOCKED_HASHABLE")
                try:
                    f = _orig_get_field(cls, a_name, a_type, default_kw_only)
                    f.default = orig_val
                    return f
                finally:
                    setattr(cls, a_name, orig_val)
    return _orig_get_field(cls, a_name, a_type, default_kw_only)

dataclasses._get_field = _patched_get_field

# ── Path Configurations ───────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEACHER_WAV = BACKEND_DIR / "assets" / "teacher_voice" / "teacher_short.wav"
REPORT_PATH = SCRIPT_DIR / "benchmark_report.json"

# Ensure fairseq is in Python path for local editable import
FAIRSEQ_SRC = SCRIPT_DIR / "fairseq_src"
if FAIRSEQ_SRC.exists() and str(FAIRSEQ_SRC) not in sys.path:
    sys.path.insert(0, str(FAIRSEQ_SRC))

# ── Stress Test Vocabulary ────────────────────────────────────────────────────
STRESS_TEST_VOCAB = {
    "Force": ["फोर्स"],
    "Momentum": ["मोमेंटम"],
    "Velocity": ["वेलोसिटी"],
    "Acceleration": ["एक्सेलेरेशन", "ऐक्सेलेरेशन"],
    "Photosynthesis": ["फोटोसिंथेसिस"],
    "Respiration": ["रेस्पिरेशन"],
    "Mitochondria": ["माइटोकॉन्ड्रिया", "माइटोकोंड्रिया"],
    "Backend": ["बैकएंड", "बैकऐंड", "बैक-एंड"],
    "Frontend": ["फ्रंटएंड", "फ्रंटऐंड", "फ्रंट-एंड", "फ्रंटेंड"],
    "Docker": ["डॉकर"],
    "Kubernetes": ["कुबेरनेट्स", "कुबर्नटीस", "कुबरनेट्स", "कुबेरनेटेस"],
    "FastAPI": ["फास्टएपीआई", "फ़ास्टएपीआई", "फास्ट एपीआई"],
    "React": ["रिएक्ट", "रिऐक्ट"],
    "MongoDB": ["मोंगोडीबी", "मोंगो डीबी", "मंगोडीबी", "मोंगोदब", "मोंगो दब", "मोंगो दीब", "मोंगोदेब", "मोंगोडब"],
    "API": ["एपीआई", "ए.पी.आई."],
    "Database": ["डेटाबेस", "डाटाबेस"],
    "Microservices": ["माइक्रोसर्विसेज", "माइक्रो-सर्विसेज"]
}

# Bad translations indicating translation model behavior
BAD_TRANSLATIONS = [
    "बल", "संवेग", "वेग", "त्वरण", "प्रकाश संश्लेषण", "श्वसन", "सूत्रकणिका", 
    "पृष्ठभाग", "अग्रभाग", "डेटासंचय", "सूक्ष्मसेवाएं", "अनुरोध"
]

# ── Conversational Sentences ──────────────────────────────────────────────────
CONVERSATIONAL_SAMPLES = {
    "physics_sample": {
        "input": "Newton ka first law kehta hai ki agar koi object rest mein hai to woh rest mein hi rahega. Force apply karne par hi motion change hota hai. Velocity aur Acceleration iske basic parameters hain.",
        "keywords": ["Force", "Velocity", "Acceleration"]
    },
    "biology_sample": {
        "input": "Photosynthesis plants mein energy produce karne ka ek primary process hai. Cellular Respiration ke dauran Mitochondria ATP energy generate karta hai.",
        "keywords": ["Photosynthesis", "Respiration", "Mitochondria"]
    },
    "cs_sample": {
        "input": "React Frontend ke liye ek dynamic user interface library hai, jabki FastAPI Backend api framework hai. Docker aur Kubernetes microservices architecture ko deploy karte hain.",
        "keywords": ["React", "Frontend", "FastAPI", "Backend", "Docker", "Kubernetes", "API", "Microservices"]
    },
    "long_narration_sample": {
        "input": "Chaliye aaj hum microservices architecture aur database design ke baare mein baat karte hain. Jab aap ek complex system design karte hain, to multiple API routes create karne hote hain aur MongoDB ya PostgreSQL jaise Database systems ka use kiya jata hai. Microservices ki wajah se backend scalable banta hai, lekin isme API latency aur configuration management ke challenges aate hain. Socho, agar hum har service ko containerize karein, to isse system security aur deployment dynamic ho jata hai. Force, Momentum aur Velocity physics ke basic concepts hain jise hum computer modeling se optimize kar sakte hain.",
        "keywords": ["Microservices", "Database", "API", "MongoDB", "Database", "Backend", "API", "Force", "Momentum", "Velocity"]
    }
}

# Helper functions for compound words handling
def normalize_word(word):
    # Split camelCase words (e.g. FastAPI -> Fast API)
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', word)

def transliterate_word_helper(engine, word):
    normalized = normalize_word(word)
    if " " in normalized:
        parts = normalized.split()
        cand_lists = [engine.translit_word(p, topk=5).get("hi", []) for p in parts]
        import itertools
        combined_candidates = []
        for combo in itertools.product(*cand_lists):
            combined_candidates.append(" ".join(combo))
            combined_candidates.append("".join(combo))
        return combined_candidates[:5]
    else:
        return engine.translit_word(word, topk=5).get("hi", [])

# ── Transliteration Evaluator ─────────────────────────────────────────────────
def evaluate_transliteration():
    print("Loading AI4Bharat IndicXlit engine...")
    from ai4bharat.transliteration import XlitEngine
    engine = XlitEngine("hi", beam_width=10, rescore=True)

    # 1. Evaluate Stress Test Vocabulary (Isolated)
    stress_results = {}
    stress_matched_count = 0

    print("\nRunning Isolated Educational Vocabulary Stress Test...")
    for word, expected_list in STRESS_TEST_VOCAB.items():
        candidates = transliterate_word_helper(engine, word)
        
        # Check if any expected candidate is in the top-5 transliterations
        matched = False
        matched_term = None
        for cand in candidates:
            if cand in expected_list:
                matched = True
                matched_term = cand
                break
        
        if matched:
            stress_matched_count += 1
            print(f"  [PASS] {word} -> Expected: {expected_list}, Got top matched: {matched_term}")
        else:
            print(f"  [FAIL] {word} -> Expected: {expected_list}, Got candidates: {candidates}")

        stress_results[word] = {
            "expected": expected_list,
            "candidates": candidates,
            "matched": matched,
            "matched_term": matched_term
        }

    stress_test_phonetic_score = (stress_matched_count / len(STRESS_TEST_VOCAB)) * 100
    stress_test_technical_score = stress_test_phonetic_score

    # 2. Evaluate Conversational Sentences
    conv_results = {}
    total_leakage_chars = 0
    total_chars = 0
    translation_detected = False

    conv_matched_count = 0
    conv_total_keywords = 0

    print("\nRunning Conversational Sentences Transliteration...")
    for key, data in CONVERSATIONAL_SAMPLES.items():
        text_input = data["input"]
        keywords = data["keywords"]

        # Preprocess sentence to split camelCase terms
        normalized_input = normalize_word(text_input)

        res = engine.translit_sentence(normalized_input)
        output_text = res.get("hi", "")

        # Check for bad translations using word-level matching split on whitespace
        clean_words = [re.sub(r"[^\w\s\u0900-\u097F]", "", w) for w in output_text.split()]
        for bad in BAD_TRANSLATIONS:
            if bad in clean_words:
                print(f"  [WARNING] Translation detected in {key}: found exact word '{bad}'")
                translation_detected = True

        # Check for Roman script leakage (excluding digits and punctuation)
        roman_chars = re.findall(r'[a-zA-Z]', output_text)
        total_leakage_chars += len(roman_chars)
        total_chars += len(output_text)

        # Evaluate keyword preservation in output sentence
        kw_matches = []
        for kw in keywords:
            expected_list = STRESS_TEST_VOCAB.get(kw, [])
            found = False
            found_term = None
            for exp in expected_list:
                if exp in output_text:
                    found = True
                    found_term = exp
                    break
            
            kw_matches.append({
                "word": kw,
                "expected": expected_list,
                "found": found,
                "found_term": found_term
            })
            conv_total_keywords += 1
            if found:
                conv_matched_count += 1
            else:
                print(f"  [MISSING KEYWORD] Sentence '{key}' missing keyword '{kw}' (Expected Devanagari equivalent not found in: '{output_text}')")

        conv_results[key] = {
            "input": text_input,
            "output": output_text,
            "keyword_eval": kw_matches,
            "roman_chars_leaked": len(roman_chars)
        }
        print(f"  [{key}] Output: {output_text}")

    conv_phonetic_score = (conv_matched_count / conv_total_keywords) * 100 if conv_total_keywords > 0 else 100.0
    conv_technical_score = conv_phonetic_score

    # 3. Calculate Final Scores with 40% Stress Test / 60% Conversational weighting
    final_phonetic_preservation = (0.40 * stress_test_phonetic_score) + (0.60 * conv_phonetic_score)
    final_technical_preservation = (0.40 * stress_test_technical_score) + (0.60 * conv_technical_score)

    roman_character_leakage_percent = (total_leakage_chars / total_chars) * 100 if total_chars > 0 else 0.0

    print(f"\nEvaluation Metrics:")
    print(f"  Phonetic Preservation Score: {final_phonetic_preservation:.2f}%")
    print(f"  Technical Term Preservation Score: {final_technical_preservation:.2f}%")
    print(f"  Roman Character Leakage Percent: {roman_character_leakage_percent:.2f}%")
    print(f"  Translation Detected: {translation_detected}")

    return {
        "translation_detected": translation_detected,
        "phonetic_preservation_score": round(final_phonetic_preservation, 2),
        "technical_term_preservation_score": round(final_technical_preservation, 2),
        "roman_character_leakage_percent": round(roman_character_leakage_percent, 2),
        "stress_results": stress_results,
        "conv_results": conv_results
    }

# ── XTTS Validation Audio Generator ───────────────────────────────────────────
def get_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0

def generate_validation_audios(conv_results):
    print("\n" + "=" * 70)
    print("XTTS-v2 Validation Audio Generation using Teacher Voice Clone")
    print("=" * 70)
    
    if not TEACHER_WAV.exists():
        print(f"[ERROR] Reference voice file not found at: {TEACHER_WAV}")
        print("Bypassing XTTS audio generation since reference WAV is missing.")
        return False

    print(f"Using Reference WAV: {TEACHER_WAV.resolve()}")

    # Apply runtime patch to prevent TTS from requiring torchcodec on PyTorch >= 2.9
    try:
        import transformers.utils.import_utils as iu
        orig = iu.is_torch_greater_or_equal
        def patched_is_torch_greater_or_equal(library_version, accept_dev=False):
            if library_version == "2.9":
                return False
            return orig(library_version, accept_dev)
        iu.is_torch_greater_or_equal = patched_is_torch_greater_or_equal
    except Exception as patch_err:
        print(f"Warning: Failed to patch transformers version check: {patch_err}")

    # Patch torchaudio load and save using soundfile to bypass torchcodec FFmpeg dependencies on Windows
    try:
        import torchaudio
        import soundfile as sf
        import torch

        def patched_torchaudio_load(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, **kwargs):
            data, sr = sf.read(uri, dtype='float32')
            tensor = torch.from_numpy(data)
            if tensor.ndim == 1:
                tensor = tensor.unsqueeze(0)
            elif channels_first:
                tensor = tensor.T
            return tensor, sr

        def patched_torchaudio_save(filepath, src, sample_rate, channels_first=True, **kwargs):
            data = src.detach().cpu().numpy()
            if channels_first and data.ndim > 1:
                data = data.T
            sf.write(filepath, data, sample_rate)

        torchaudio.load = patched_torchaudio_load
        torchaudio.save = patched_torchaudio_save
        print("Successfully patched torchaudio.load and torchaudio.save using soundfile.")
    except Exception as audio_patch_err:
        print(f"Warning: Failed to patch torchaudio load/save: {audio_patch_err}")

    # Load Coqui TTS
    try:
        from TTS.api import TTS
    except ImportError as e:
        print(f"[ERROR] Coqui TTS is not installed: {e}")
        return False

    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        print("XTTS-v2 loaded successfully on CPU.")
    except Exception as e:
        print(f"[ERROR] Failed to load XTTS-v2 model: {e}")
        return False

    audio_results = {}
    for key, data in conv_results.items():
        devanagari_text = data["output"]
        out_wav = OUTPUT_DIR / f"{key}.wav"
        print(f"\nGenerating audio for {key}...")
        
        t_start = time.perf_counter()
        ram_start = get_ram_mb()

        try:
            tts.tts_to_file(
                text=devanagari_text,
                speaker_wav=str(TEACHER_WAV),
                language="hi",
                file_path=str(out_wav)
            )
            t_end = time.perf_counter()
            ram_end = get_ram_mb()
            
            # Read duration
            audio_duration = 0.0
            try:
                wav_data, sr = sf.read(str(out_wav))
                audio_duration = len(wav_data) / sr
            except Exception:
                pass

            audio_results[key] = {
                "generated": True,
                "output_path": str(out_wav.resolve()),
                "generation_time_seconds": round(t_end - t_start, 2),
                "audio_duration_seconds": round(audio_duration, 2),
                "peak_ram_mb": round(ram_end, 2)
            }
            print(f"  [OK] Audio saved to {out_wav.name} (Duration: {audio_duration:.2f}s, Time: {t_end - t_start:.2f}s)")
        except Exception as gen_err:
            print(f"  [ERROR] Failed to generate audio for {key}: {gen_err}")
            audio_results[key] = {
                "generated": False,
                "error": str(gen_err)
            }

    return audio_results

# ── Main Runner ──────────────────────────────────────────────────────────────
def run_benchmark():
    print("=" * 70)
    print("WhiteboardAI — AI4Bharat IndicXlit Transliteration Quality Evaluation")
    print("=" * 70)

    # 1. Run transliteration benchmarks
    eval_res = evaluate_transliteration()

    # 2. Run XTTS validation voice synthesis
    audio_results = generate_validation_audios(eval_res["conv_results"])

    # 3. Assess Success Gate
    # Integration recommendation is allowed only if:
    # {
    #   "translation_detected": false,
    #   "phonetic_preservation_score": 95,
    #   "technical_term_preservation_score": 95,
    #   "roman_character_leakage_percent": 0,
    #   "xtts_ready": true
    # }
    success_gate = (
        not eval_res["translation_detected"] and
        eval_res["phonetic_preservation_score"] >= 95 and
        eval_res["technical_term_preservation_score"] >= 95 and
        eval_res["roman_character_leakage_percent"] == 0 and
        audio_results is not False
    )

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_under_evaluation": "AI4Bharat IndicXlit",
        "eval_scores": {
            "translation_detected": eval_res["translation_detected"],
            "phonetic_preservation_score": eval_res["phonetic_preservation_score"],
            "technical_term_preservation_score": eval_res["technical_term_preservation_score"],
            "roman_character_leakage_percent": eval_res["roman_character_leakage_percent"],
            "xtts_ready": success_gate
        },
        "vocabulary_stress_test": eval_res["stress_results"],
        "conversational_eval": eval_res["conv_results"],
        "xtts_audio_validation": audio_results if audio_results else "Failed or bypassed"
    }

    # Write report file
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"Benchmark finished successfully. Report saved to: {REPORT_PATH.resolve()}")
    print(f"XTTS Ready Status: {'PASSED' if success_gate else 'FAILED'}")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
