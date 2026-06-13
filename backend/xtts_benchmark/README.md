# XTTS Hindi Finetuned — Standalone Benchmark

> **This directory is completely isolated from production WhiteboardAI.**
> No provider registration. No API changes. No frontend changes.

---

## Directory Structure

```
xtts_benchmark/
├── benchmark_xtts.py      # Main benchmark runner
├── benchmark_report.json  # Auto-generated after run
├── requirements.txt       # XTTS-specific dependencies
├── README.md              # This file
├── reference/             # ← Upload your voice files here
│   ├── teacher_short.wav      # Reference speaker audio (6-10s, clear speech)
│   └── teacher_transcript.txt # Transcript of what teacher_short.wav says
└── outputs/               # Generated WAV files appear here
    ├── xtts_english_short.wav
    ├── xtts_english_long.wav
    ├── xtts_hindi_short.wav
    ├── xtts_hindi_long.wav
    ├── xtts_hinglish_short.wav
    ├── xtts_hinglish_long.wav
    ├── xtts_variant_a.wav     (Roman Hinglish)
    ├── xtts_variant_b.wav     (Mixed Script)
    └── xtts_variant_c.wav     (Pure Hindi)
```

---

## Upload Instructions

**Before running the benchmark**, place these files in the `reference/` folder:

1. `teacher_short.wav` — A 6–10 second WAV recording of the teacher voice.
   - Format: WAV, 22050 Hz or 44100 Hz, mono or stereo
   - Content: Any clear, natural speech (the XTTS model will clone this voice)
   - Quality: No background noise; clear pronunciation

2. `teacher_transcript.txt` — The text content of the reference WAV.
   - Plain text, one line
   - Example: `"Hello, today we will learn about Newton's Laws of Motion."`

---

## Setup & Run

```powershell
# From backend/ directory
# 1. Install XTTS dependencies
pip install -r xtts_benchmark/requirements.txt

# 2. Run benchmark
python xtts_benchmark/benchmark_xtts.py

# 3. Results appear in:
#    xtts_benchmark/outputs/*.wav
#    xtts_benchmark/benchmark_report.json
```

---

## What the Benchmark Tests

| Test | Text | Output |
|---|---|---|
| English (short) | Newton's First Law — 3 sentences | `xtts_english_short.wav` |
| English (long) | Newton's Laws — full 60-90s lesson | `xtts_english_long.wav` |
| Hindi (short) | Newton's First Law in Hindi | `xtts_hindi_short.wav` |
| Hindi (long) | Full lesson in Hindi | `xtts_hindi_long.wav` |
| Hinglish (short) | Newton's First Law in Hinglish | `xtts_hinglish_short.wav` |
| Hinglish (long) | Full lesson in Hinglish | `xtts_hinglish_long.wav` |
| Variant A | Roman Hinglish | `xtts_variant_a.wav` |
| Variant B | Mixed Script (Roman + Devanagari) | `xtts_variant_b.wav` |
| Variant C | Pure Hindi (Devanagari only) | `xtts_variant_c.wav` |

---

## Interpreting Results

The `benchmark_report.json` will contain:
- Audio duration (seconds)
- Generation time (seconds)
- Peak RAM usage (MB)
- Waveform diagnostics (min/max amplitude)
- Manual clone fidelity scoring placeholders
