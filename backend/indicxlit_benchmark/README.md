# IndicXlit Transliteration Evaluation Benchmark

This is an isolated benchmark environment to evaluate the performance and quality of AI4Bharat's **IndicXlit** model for Hinglish script transliteration (Roman script Hinglish → Devanagari script Hinglish) in WhiteboardAI.

## Objective

The core objective is to determine if the `ai4bharat-transliteration` engine successfully performs phonetic script transliteration and preserves educational/technical vocabulary without semantic translation.

The benchmark evaluates:
- 7 standard categories (Physics, Physics Long, CS, Bio, Chemistry, Software Engineering, and Mixed Paragraph).
- A 17-word **Educational Vocabulary Stress Test** (e.g. Force, Momentum, Mitochondria, etc.), weighted at 40% of the overall scores.
- A **Long Educational Narration** (150-200 words) to evaluate long-form consistency.
- Automatic **Roman script character leakage** percentage.

## Setup & Running

1. **Install Dependencies**:
   ```bash
   pip install ai4bharat-transliteration
   ```

2. **Execute Benchmark**:
   ```bash
   python benchmark_indicxlit.py
   ```

## Output files

- **`benchmark_report.json`**: Detailed score metrics and generated outputs.
- **`outputs/`**: Generated validation WAV files cloned using the user's `teacher_short.wav` reference voice.
