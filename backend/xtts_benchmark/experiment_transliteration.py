"""
Hinglish Transliteration Experiment (Evaluation Only)
======================================================
Completely isolated experiment script.
Does NOT modify WhiteboardAI production code.

Run from backend/ directory:
    python xtts_benchmark/experiment_transliteration.py
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

# Safe print utility for Windows console encoding compatibility
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
REPORT_PATH = SCRIPT_DIR / "transliteration_report.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_WAV = REFERENCE_DIR / "teacher_short.wav"

# ── Test Texts ─────────────────────────────────────────────────────────────
TESTS = {
    "roman_hinglish": (
        "Force ek push ya pull hota hai. "
        "Newton ka First Law kehta hai ki agar kisi object par net force na lage to object rest ya uniform motion mein rahega."
    ),
    "transliterated_hinglish": (
        "फोर्स एक पुश या पुल होता है। "
        "न्यूटन का फर्स्ट लॉ कहता है कि अगर किसी ऑब्जेक्ट पर नेट फोर्स न लगे तो ऑब्जेक्ट रेस्ट या यूनिफॉर्म मोशन में रहेगा।"
    ),
    "pure_hindi": (
        "बल किसी वस्तु पर लगाया गया धक्का या खिंचाव होता है। "
        "न्यूटन का प्रथम नियम कहता है कि यदि किसी वस्तु पर कोई परिणामी बल न लगे तो वह विराम या समान वेग की अवस्था में बनी रहती है।"
    )
}

def check_reference_files():
    if not REFERENCE_WAV.exists():
        raise FileNotFoundError(
            f"[Experiment] Reference voice file missing: {REFERENCE_WAV}\n"
            "Please ensure teacher_short.wav is uploaded in xtts_benchmark/reference/ folder."
        )

def load_xtts_model():
    print("Loading XTTS-v2 model...")
    # Apply version patch
    try:
        import transformers.utils.import_utils as iu
        orig = iu.is_torch_greater_or_equal
        def patched_is_torch_greater_or_equal(library_version, accept_dev=False):
            if library_version == "2.9":
                return False
            return orig(library_version, accept_dev)
        iu.is_torch_greater_or_equal = patched_is_torch_greater_or_equal
    except Exception as e:
        print(f"Warning: failed to patch transformers version check: {e}")

    # Patch torchaudio using soundfile to bypass torchcodec/FFmpeg DLL dependencies on Windows
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
        print("Successfully patched torchaudio load/save with soundfile.")
    except Exception as e:
        print(f"Warning: failed to patch torchaudio load/save: {e}")

    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        print("XTTS-v2 loaded on CPU.")
        return tts
    except Exception as e:
        raise RuntimeError(f"Failed to load XTTS model: {e}\n{traceback.format_exc()}")

def run_experiment():
    print("=" * 70)
    print("Hinglish Transliteration Evaluation Experiment")
    print("=" * 70)
    
    check_reference_files()
    tts = load_xtts_model()

    report = {
        "experiment_name": "Hinglish Transliteration Script Study",
        "model": "tts_models/multilingual/multi-dataset/xtts_v2",
        "cpu_only": True,
        "reference_wav": str(REFERENCE_WAV.resolve()),
        "results": {}
    }

    for name, text in TESTS.items():
        out_path = OUTPUT_DIR / f"{name}.wav"
        print(f"\nGenerating '{name}' audio...")
        t_start = time.perf_counter()
        
        try:
            # All generations use language="hi" since they are Hindi/Hinglish pronunciations
            tts.tts_to_file(
                text=text,
                speaker_wav=str(REFERENCE_WAV),
                language="hi",
                file_path=str(out_path)
            )
            t_end = time.perf_counter()
            gen_time = round(t_end - t_start, 2)
            
            # Read metadata
            import soundfile as sf
            data, sr = sf.read(str(out_path))
            duration = round(len(data) / sr, 2)
            
            print(f"  [OK] Saved to: {out_path.name} ({duration}s duration, generated in {gen_time}s)")
            
            report["results"][name] = {
                "success": True,
                "output_path": str(out_path.resolve()),
                "duration": f"{duration} seconds",
                "generation_time_seconds": gen_time,
                "notes": "Pending manual listening verification"
            }
        except Exception as e:
            tb = traceback.format_exc()
            print(f"  [FAIL] Failed to generate {name}: {e}")
            report["results"][name] = {
                "success": False,
                "error": str(e),
                "traceback": tb
            }

    # Write JSON report
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"Experiment completed. Report saved to: {REPORT_PATH.resolve()}")
    print("=" * 70)

if __name__ == "__main__":
    try:
        run_experiment()
    except Exception as exc:
        print(f"\n[FATAL] Experiment failed: {exc}")
        traceback.print_exc()
        sys.exit(1)
