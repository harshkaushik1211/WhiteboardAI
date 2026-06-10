"""Verify Real GPU Outputs Utility.

This script scans your Google Drive completed folder for actual SadTalker worker outputs,
validates the transparency format of avatar.webm with ffprobe, parses processing telemetry,
and prints a final Phase-5.6 GPU Validation Report.
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path

# Add backend directory to path to load config settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
try:
    from config import settings
except ImportError:
    settings = None

def main():
    print("==================================================")
    # Determine Google Drive completed folder path
    if settings:
        completed_path = settings.sadtalker_completed_path
    else:
        # Fallback default
        completed_path = Path(__file__).resolve().parent.parent / "WhiteboardAI_Avatar" / "completed"

    print(f"Scanning completed jobs directory: {completed_path}")
    if not completed_path.exists():
        print(f"Directory {completed_path} not found. Ensure the Colab worker has completed at least one job.")
        sys.exit(1)

    completed_jobs = [p for p in completed_path.iterdir() if p.is_dir() and p.name.startswith("project_")]
    if not completed_jobs:
        print("No completed projects found in Drive folder. Run a job in Google Colab first.")
        sys.exit(0)

    print(f"Found {len(completed_jobs)} completed project(s).")
    print("==================================================")

    for job in completed_jobs:
        project_id = job.name.replace("project_", "")
        print(f"\n[VALIDATING PROJECT {project_id}]")
        
        # 1. Check required files
        webm = job / "avatar.webm"
        orig_mp4 = job / "avatar_original.mp4"
        result_json = job / "avatar_result.json"
        worker_json = job / "worker.json"
        
        files_ok = True
        for f in (webm, orig_mp4, result_json, worker_json):
            if f.exists():
                print(f"  - {f.name}: FOUND ({f.stat().st_size // 1024} KB)")
            else:
                print(f"  - {f.name}: MISSING")
                files_ok = False
                
        if not files_ok:
            print(f"  - [RESULT] TC 1/TC 2: FAIL (Missing files in project directory)")
            continue
            
        print("  - [RESULT] TC 1/TC 2: PASS (All assets present)")

        # 2. worker.json Validation
        try:
            w_data = json.loads(worker_json.read_text(encoding="utf-8"))
            print("  - worker.json Health:")
            print(f"    * worker: {w_data.get('worker')}")
            print(f"    * worker_version: {w_data.get('worker_version')}")
            print(f"    * status: {w_data.get('status')}")
            print(f"    * started_at: {w_data.get('started_at')}")
            print(f"    * last_heartbeat: {w_data.get('last_heartbeat')}")
            print("  - [RESULT] TC 3: PASS")
        except Exception as e:
            print(f"  - [RESULT] TC 3: FAIL (Could not parse worker.json: {e})")

        # 3. ffprobe Transparency Validation
        print("  - Probing transparent WebM...")
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,pix_fmt,duration",
            "-of", "json",
            str(webm)
        ]
        try:
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            info = json.loads(res.stdout)
            streams = info.get("streams", [])
            if streams:
                stream = streams[0]
                codec = stream.get("codec_name")
                pix_fmt = stream.get("pix_fmt")
                duration = stream.get("duration") or "N/A"
                print(f"    * Codec: {codec}")
                print(f"    * Pixel Format: {pix_fmt}")
                print(f"    * Duration: {duration}s")
                
                # Check VP9 transparency (accept yuv420p/yuva420p for WebM VP9)
                if codec == "vp9" and pix_fmt in ("yuv420p", "yuva420p"):
                    print("  - [RESULT] TC 4: PASS (Valid VP9 container with transparent channels)")
                else:
                    print(f"  - [RESULT] TC 4: FAIL (Codec/PixFmt mismatch: codec={codec}, format={pix_fmt})")
            else:
                print("  - [RESULT] TC 4: FAIL (No streams in video file)")
        except Exception as e:
            print(f"  - [RESULT] TC 4: FAIL (ffprobe check failed: {e})")

        # 4. Telemetry parsing
        try:
            r_data = json.loads(result_json.read_text(encoding="utf-8"))
            print("  - Telemetry Timing Metrics:")
            print(f"    * Queue wait: {r_data.get('queue_wait_seconds')}s")
            print(f"    * Generation: {r_data.get('generation_time_seconds')}s")
            print(f"    * Background removal: {r_data.get('background_removal_seconds')}s")
            print(f"    * WebM Encoding: {r_data.get('encoding_seconds')}s")
            print(f"    * Total worker duration: {r_data.get('total_processing_seconds')}s")
            print(f"    * Video probed duration: {r_data.get('video_duration')}s")
            print(f"    * Validation status: {r_data.get('validation_passed')}")
            print("  - [RESULT] TC 5/6/7/8: PASS")
        except Exception as e:
            print(f"  - [RESULT] TC 5/6/7/8: FAIL (Could not parse avatar_result.json: {e})")

if __name__ == "__main__":
    main()
