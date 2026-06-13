# Teacher Voice Reference Assets

This directory contains the reference voice file used for XTTS-v2 speaker cloning.

## Required Files

| File | Purpose |
|------|---------|
| `teacher_short.wav` | 6–10 second reference voice clip for XTTS speaker cloning |

## Source

This file was originally uploaded by the user during the XTTS benchmark phase and
should have been copied from:

    backend/xtts_benchmark/reference/teacher_short.wav

## Format Requirements

- Format: WAV (16-bit PCM or float32)
- Sample rate: 22 050 Hz or 24 000 Hz recommended (XTTS native is 24 kHz)
- Duration: 6–12 seconds (shorter is fine; longer improves cloning fidelity)
- Content: Clear speech, single speaker, minimal background noise

## Replacing the Reference Voice

To use a different teacher voice:
1. Replace `teacher_short.wav` with your new reference audio.
2. Restart the WhiteboardAI backend.
3. The XTTS model singleton will use the new reference on next generation.

No code changes are needed — the provider reads the path at runtime.
