"""
XTTS Hindi Finetuned — Standalone Benchmark
============================================

Completely isolated from production WhiteboardAI.
No provider registration. No API changes. No schema changes.

Run from backend/ directory:
    python xtts_benchmark/benchmark_xtts.py

Requires:
    - reference/teacher_short.wav      (speaker reference voice)
    - reference/teacher_transcript.txt  (transcript of reference)
    - pip install -r xtts_benchmark/requirements.txt
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

# Safe print to prevent Windows console UnicodeEncodeError (cp1252 encoding limits)
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

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = SCRIPT_DIR / "reference"
OUTPUT_DIR = SCRIPT_DIR / "outputs"
REPORT_PATH = SCRIPT_DIR / "benchmark_report.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_WAV = REFERENCE_DIR / "teacher_short.wav"
REFERENCE_TRANSCRIPT = REFERENCE_DIR / "teacher_transcript.txt"

# ── Test Prompts ───────────────────────────────────────────────────────────

PROMPTS = {
    # Short samples (same as Indic Parler evaluation for direct comparison)
    "english_short": (
        "Imagine a football lying on the ground. "
        "It will not move unless a force is applied. "
        "This is the basic idea behind Newton's First Law."
    ),
    "hindi_short": (
        "कल्पना कीजिए कि एक फुटबॉल मैदान पर पड़ी है। "
        "जब तक उस पर कोई बल नहीं लगाया जाता, "
        "वह नहीं चलेगी। "
        "यही न्यूटन के प्रथम नियम का मूल विचार है।"
    ),
    "hinglish_short": (
        "Socho ek football ground par pada hai. "
        "Jab tak koi force apply nahi karega, "
        "woh move nahi karega. "
        "Yahi Newton ke First Law ka basic idea hai."
    ),

    # Long narration stress test (~60-90 seconds)
    # This directly mirrors the Indic Parler failure scenario: first words OK, then collapse.
    # XTTS must be tested for long-form stability.
    "english_long": (
        "Welcome to today's lesson on Newton's Laws of Motion. "
        "These three laws form the foundation of classical mechanics and explain how objects move. "
        "Newton's First Law, also called the Law of Inertia, states that an object at rest stays at rest, "
        "and an object in motion stays in motion, unless acted upon by an external force. "
        "Think of a ball rolling on a smooth floor. Without friction, it would roll forever. "
        "Newton's Second Law tells us that force equals mass times acceleration. "
        "This means a heavier object needs more force to accelerate at the same rate as a lighter one. "
        "If you push a car and a bicycle with the same force, the bicycle will accelerate much faster. "
        "Newton's Third Law states that for every action, there is an equal and opposite reaction. "
        "When you jump off a boat, you push the boat backward as you move forward. "
        "These three laws together explain virtually all motion we see in everyday life, "
        "from a cricket ball flying through the air, to a rocket launching into space. "
        "Understanding these laws is the key to understanding how the physical world works."
    ),
    "hinglish_long": (
        "Aaj hum Newton ke Laws of Motion ke baare mein padhenge. "
        "Ye teen laws classical mechanics ki neev hain, aur explain karte hain ki objects kaise move karte hain. "
        "Newton ka Pehla Law kehta hai ki ek ruki hui cheez ruki hi rahegi, "
        "aur ek chalti hui cheez chalti hi rahegi, jab tak koi external force apply nahi hota. "
        "Socho ek ball smooth floor par roll kar rahi hai. Bina friction ke, woh hamesha roll karti rahegi. "
        "Newton ka Doosra Law kehta hai ki Force barabar hai mass times acceleration ke. "
        "Matlab, ek bhaari cheez ko zyada force chahiye hoti hai same acceleration ke liye. "
        "Agar tum ek car aur bicycle ko same force se push karo, cycle bahut tezi se accelerate karegi. "
        "Newton ka Teesra Law kehta hai ki har action ka ek equal aur opposite reaction hota hai. "
        "Jab tum ek boat se kood te ho, tum boat ko peeche push karte ho aur khud aage jaate ho. "
        "Ye teen laws milkar explain karte hain virtually har motion jo hum daily life mein dekhte hain, "
        "cricket ball se lekar space rocket tak. "
        "In laws ko samajhna physical world ko samajhne ki key hai."
    ),
    "hindi_long": (
        "आज हम न्यूटन के गति के नियमों के बारे में पढ़ेंगे। "
        "ये तीन नियम शास्त्रीय यांत्रिकी की नींव हैं और समझाते हैं कि वस्तुएं कैसे चलती हैं। "
        "न्यूटन का पहला नियम कहता है कि एक विराम अवस्था में रखी वस्तु विराम में ही रहेगी, "
        "और एक चलती हुई वस्तु चलती ही रहेगी, जब तक कोई बाहरी बल नहीं लगाया जाता। "
        "सोचो एक गेंद एक चिकने फर्श पर लुढ़क रही है। बिना घर्षण के, वह हमेशा लुढ़कती रहेगी। "
        "न्यूटन का दूसरा नियम कहता है कि बल द्रव्यमान गुना त्वरण के बराबर होता है। "
        "इसका मतलब है कि एक भारी वस्तु को उसी दर पर त्वरित करने के लिए अधिक बल की आवश्यकता होती है। "
        "न्यूटन का तीसरा नियम कहता है कि हर क्रिया की एक समान और विपरीत प्रतिक्रिया होती है। "
        "जब आप एक नाव से कूदते हैं, तो आप नाव को पीछे धकेलते हैं और खुद आगे बढ़ते हैं। "
        "ये तीन नियम मिलकर दैनिक जीवन में हमारे द्वारा देखी जाने वाली लगभग सभी गतियों की व्याख्या करते हैं।"
    ),

    # Hinglish representation study
    "variant_a": (
        # Variant A: Pure Roman Hinglish
        "Force ek push ya pull hota hai jo kisi object par lagaya jata hai. "
        "Jab hum kisi cheez ko dhakelte hain, hum uske upar force apply karte hain. "
        "Force ki wajah se hi objects apni jagah se hilte hain."
    ),
    "variant_b": (
        # Variant B: Mixed Script (Roman + Devanagari)
        "Force एक push या pull होती है जो किसी object पर लगाई जाती है। "
        "Jab hum kisi चीज़ को push karte hain, hum उस पर force apply karte hain। "
        "Force ki wajah se hi objects अपनी जगह से हिलते हैं।"
    ),
    "variant_c": (
        # Variant C: Pure Hindi (Devanagari)
        "बल किसी वस्तु पर लगाया गया धक्का या खिंचाव होता है। "
        "जब हम किसी वस्तु को धकेलते हैं, हम उस पर बल लगाते हैं। "
        "बल की वजह से ही वस्तुएं अपने स्थान से हिलती हैं।"
    ),
}

# XTTS language codes
LANG_CODES = {
    "english_short": "en",
    "english_long": "en",
    "hindi_short": "hi",
    "hindi_long": "hi",
    "hinglish_short": "hi",
    "hinglish_long": "hi",
    "variant_a": "hi",
    "variant_b": "hi",
    "variant_c": "hi",
}

# ── RAM utility ────────────────────────────────────────────────────────────

def get_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0

# ── Main benchmark ─────────────────────────────────────────────────────────

def check_reference_files():
    """Verify reference voice and transcript exist before starting."""
    missing = []
    if not REFERENCE_WAV.exists():
        missing.append(str(REFERENCE_WAV))
    if not REFERENCE_TRANSCRIPT.exists():
        missing.append(str(REFERENCE_TRANSCRIPT))
    if missing:
        raise FileNotFoundError(
            f"\n\n[XTTS Benchmark] Reference files missing:\n"
            + "\n".join(f"  - {f}" for f in missing)
            + "\n\nPlease upload:\n"
            + "  1. xtts_benchmark/reference/teacher_short.wav  (6-10 second reference voice)\n"
            + "  2. xtts_benchmark/reference/teacher_transcript.txt  (transcript of the reference)\n"
            + "\nSee xtts_benchmark/README.md for instructions."
        )


def load_xtts_model():
    """Load XTTS-v2 model. Fails loudly on any error — no fallback."""
    print("Loading XTTS-v2 model...")
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

    try:
        from TTS.api import TTS
    except ImportError as e:
        raise ImportError(
            f"[XTTS Benchmark] Coqui TTS library not installed.\n"
            f"Run: pip install coqui-tts\n"
            f"(Uses Idiap community fork — Python 3.13 compatible)\n"
            f"Original error: {e}"
        ) from e

    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        print("XTTS-v2 loaded on CPU.")
        return tts
    except Exception as e:
        raise RuntimeError(
            f"[XTTS Benchmark] Failed to load XTTS-v2 model.\n"
            f"Stack trace:\n{traceback.format_exc()}"
        ) from e


def run_generation(tts, test_name: str, text: str, lang: str) -> dict:
    """Generate a single audio sample and return metrics."""
    out_path = OUTPUT_DIR / f"xtts_{test_name}.wav"
    print(f"\n[{test_name}] Generating {len(text)} chars in lang='{lang}'...")

    ram_start = get_ram_mb()
    t_start = time.perf_counter()

    try:
        tts.tts_to_file(
            text=text,
            speaker_wav=str(REFERENCE_WAV),
            language=lang,
            file_path=str(out_path),
        )
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": tb,
        }

    t_end = time.perf_counter()
    ram_end = get_ram_mb()

    # Probe output WAV
    try:
        import soundfile as sf
        data, sr = sf.read(str(out_path))
        audio_duration = len(data) / sr if sr > 0 else 0.0
        waveform_min = float(data.min())
        waveform_max = float(data.max())
        audio_shape = list(data.shape)
    except Exception as probe_err:
        audio_duration = 0.0
        waveform_min = waveform_max = 0.0
        audio_shape = []

    result = {
        "success": True,
        "output_path": str(out_path.resolve()),
        "language": lang,
        "text_length_chars": len(text),
        "generation_time_seconds": round(t_end - t_start, 2),
        "peak_ram_mb": round(ram_end, 2),
        "ram_delta_mb": round(ram_end - ram_start, 2),
        "audio_duration_seconds": round(audio_duration, 2),
        "waveform_diagnostics": {
            "shape": audio_shape,
            "min": waveform_min,
            "max": waveform_max,
        },
        # Manual clone fidelity — fill in after listening
        "clone_fidelity": {
            "speaker_similarity": None,   # Score 1-10 (1=poor, 10=identical)
            "clone_quality": None,        # Score 1-10
            "accent_quality": None,       # Score 1-10
            "naturalness": None,          # Score 1-10
            "pronunciation": None,        # Score 1-10
            "teacher_feel": None,         # Score 1-10
            "overall_score": None,        # Score 1-10
            "notes": "Fill after listening"
        }
    }

    print(
        f"  [OK] Done. Duration: {audio_duration:.2f}s, "
        f"Time: {result['generation_time_seconds']}s, "
        f"RAM: {result['peak_ram_mb']:.0f} MB"
    )
    return result


def run_benchmark():
    print("=" * 70)
    print("WhiteboardAI — XTTS Hindi Finetuned Quality Benchmark")
    print("=" * 70)
    print(f"Reference WAV:        {REFERENCE_WAV}")
    print(f"Reference transcript: {REFERENCE_TRANSCRIPT}")
    print(f"Output directory:     {OUTPUT_DIR}")
    print(f"Report path:          {REPORT_PATH}")
    print()

    # Step 1: validate reference files
    check_reference_files()

    # Step 2: read transcript
    reference_transcript = REFERENCE_TRANSCRIPT.read_text(encoding="utf-8").strip()
    print(f"Reference transcript: \"{reference_transcript}\"")

    # Step 3: load model
    tts = load_xtts_model()

    report = {
        "provider": "xtts_v2",
        "model": "tts_models/multilingual/multi-dataset/xtts_v2",
        "cpu_only": True,
        "reference_wav": str(REFERENCE_WAV.resolve()),
        "reference_transcript": reference_transcript,
        "results": {},
        "success": True,
    }

    # Step 4: run all generations
    for test_name, text in PROMPTS.items():
        lang = LANG_CODES[test_name]
        result = run_generation(tts, test_name, text, lang)
        report["results"][test_name] = result
        if not result["success"]:
            report["success"] = False

    # Step 5: provider comparison table (fill after listening)
    report["provider_comparison"] = {
        "note": "Fill after manual listening comparison with F5-TTS and Edge-TTS outputs.",
        "table": [
            {"provider": "Edge-TTS", "english": None, "hindi": None, "hinglish": None, "teacher_cloning": "N/A", "overall": None},
            {"provider": "F5-TTS", "english": None, "hindi": None, "hinglish": None, "teacher_cloning": None, "overall": None},
            {"provider": "XTTS-v2 Hindi Finetuned", "english": None, "hindi": None, "hinglish": None, "teacher_cloning": None, "overall": None},
        ]
    }

    # Step 6: write report
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"Benchmark complete. Report: {REPORT_PATH.resolve()}")
    print("=" * 70)

    # Print summary
    print("\nSummary:")
    for name, r in report["results"].items():
        if r["success"]:
            print(f"  [OK]   {name:25s}  {r['audio_duration_seconds']:5.1f}s audio  {r['generation_time_seconds']:6.1f}s gen")
        else:
            print(f"  [FAIL] {name:25s}  FAILED: {r.get('error', '?')[:60]}")

    return report


if __name__ == "__main__":
    try:
        report = run_benchmark()
        if not report["success"]:
            sys.exit(1)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(2)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
