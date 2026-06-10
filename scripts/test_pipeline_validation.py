"""End-to-End Pipeline Validation Script.

Simulates the Google Drive queue and mocks the heavy GPU models to execute
colab_sadtalker_worker.py on CPU, verifying all folder transitions, heartbeats,
ffprobe properties, and telemetry metrics.
"""

from __future__ import annotations

import os
import sys
import json
import time
import shutil
import subprocess
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# ── Mock Module Injection (Allows running tests on CPU environments lacking PyTorch) ──
mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = True

sys.modules['torch'] = mock_torch
sys.modules['torchvision'] = MagicMock()
sys.modules['torchvision.transforms'] = MagicMock()
sys.modules['transformers'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()

import numpy as np
import cv2

# Add workspace scripts folder to path
scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(scripts_dir))

import colab_sadtalker_worker

class PipelineValidationTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = scripts_dir / "test_env"
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        
        cls.drive_root = cls.test_dir / "GoogleDrive"
        cls.queue_dir = cls.drive_root / "avatar_queue"
        cls.processing_dir = cls.drive_root / "avatar_processing"
        cls.completed_dir = cls.drive_root / "avatar_completed"
        cls.failed_dir = cls.drive_root / "avatar_failed"
        cls.workspace_root = cls.test_dir / "workspace"
        cls.sadtalker_dir = cls.test_dir / "SadTalkerMock"
        
        # Create folder structures
        for p in (cls.queue_dir, cls.processing_dir, cls.completed_dir, cls.failed_dir, cls.workspace_root, cls.sadtalker_dir):
            p.mkdir(parents=True, exist_ok=True)
            
        # Create mock checkpoint folder to satisfy file checks
        (cls.sadtalker_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        
        # Generate dummy checkpoints files
        for name in ("SadTalker_V0.0.2_256.safetensors", "mapping_00109-steps.pth", "mapping_00229-steps.pth"):
            (cls.sadtalker_dir / "checkpoints" / name).write_text("dummy", encoding="utf-8")

        # Generate dummy media assets
        cls.dummy_mp4 = cls.test_dir / "dummy_original.mp4"
        cls.dummy_wav = cls.test_dir / "dummy_audio.wav"
        cls.dummy_png = cls.test_dir / "dummy_portrait.png"
        
        cls._create_dummy_assets()

    @classmethod
    def tearDownClass(cls):
        # Cleanup test env
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    @classmethod
    def _create_dummy_assets(cls):
        # Use ffmpeg to generate a 3-second dummy MP4 video (color bars or testsrc)
        cmd_mp4 = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=3:size=256x256:rate=25",
            "-pix_fmt", "yuv420p",
            str(cls.dummy_mp4)
        ]
        subprocess.run(cmd_mp4, capture_output=True, check=True)
        
        # Generate dummy WAV
        cmd_wav = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=3",
            str(cls.dummy_wav)
        ]
        subprocess.run(cmd_wav, capture_output=True, check=True)

        # Create dummy PNG image (solid blue)
        img = np.zeros((256, 256, 3), dtype=np.uint8)
        img[:, :] = [255, 0, 0] # BGR Blue
        cv2.imwrite(str(cls.dummy_png), img)

    def setUp(self):
        # Clear directories before each test case
        for p in (self.queue_dir, self.processing_dir, self.completed_dir, self.failed_dir, self.workspace_root):
            if p.exists():
                shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)

    def _mock_inference_runner(self, project_dir: Path, manifest: dict) -> Path:
        """Simulates SadTalker by copying the dummy MP4 to the local workspace."""
        time.sleep(0.02)
        out_mp4 = project_dir / "sadtalker_output.mp4"
        shutil.copy2(self.dummy_mp4, out_mp4)
        return out_mp4

    def _mock_stream_frame_removal(self, video_path: Path):
        """Simulates BiRefNet segmentation by yielding frames with circular transparency alpha channel."""
        cap = cv2.VideoCapture(str(video_path))
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                h, w, _ = frame.shape
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Create a centered circle alpha mask
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.circle(mask, (w//2, h//2), min(w, h)//3, 255, -1)
                rgba = cv2.merge([frame_rgb[:, :, 0], frame_rgb[:, :, 1], frame_rgb[:, :, 2], mask])
                yield rgba, mask
        finally:
            cap.release()

    # ── Test Cases ────────────────────────────────────────────────────────────
    @patch("colab_sadtalker_worker.run_self_test", return_value=True)
    @patch("colab_sadtalker_worker.SadTalkerRunner.run")
    @patch("colab_sadtalker_worker.BackgroundRemover.stream_frame_removal")
    def test_happy_path(self, mock_bg, mock_runner, mock_test):
        """Happy Path pipeline validation (Test Case 1, 2, 3, 4, 8)."""
        mock_runner.side_effect = self._mock_inference_runner
        mock_bg.side_effect = self._mock_stream_frame_removal

        # 1. Setup project queue files
        proj_id = "newtons_laws"
        proj_dir = self.queue_dir / f"project_{proj_id}"
        proj_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "avatar_schema_version": 1,
            "manifest_version": 1,
            "provider": "sadtalker",
            "provider_version": "sadtalker_v1",
            "avatar_quality": "standard",
            "audio_file": "combined.wav",
            "source_image": "teacher.png",
            "background_removal": {"enabled": True}
        }
        (proj_dir / "avatar_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        shutil.copy2(self.dummy_wav, proj_dir / "combined.wav")
        shutil.copy2(self.dummy_png, proj_dir / "teacher.png")

        # Instantiate ColabWorker
        worker = colab_sadtalker_worker.ColabWorker(
            sadtalker_dir=self.sadtalker_dir,
            drive_root=self.drive_root,
            queue_dir="avatar_queue",
            processing_dir="avatar_processing",
            completed_dir="avatar_completed",
            failed_dir="avatar_failed",
            scan_interval=0.1,
            workspace_root=str(self.workspace_root)
        )

        # Poll and process one job
        worker._poll_and_process()

        # 2. Assert Folder Transitions (Test Case 2)
        # Check that it left queue and processing
        self.assertFalse((self.queue_dir / f"project_{proj_id}").exists())
        self.assertFalse((self.processing_dir / f"project_{proj_id}").exists())
        # Check completed folder exists
        comp_folder = self.completed_dir / f"project_{proj_id}"
        self.assertTrue(comp_folder.exists())

        # 3. Assert Outputs Present (Test Case 1)
        self.assertTrue((comp_folder / "avatar.webm").exists())
        self.assertTrue((comp_folder / "avatar_original.mp4").exists())
        self.assertTrue((comp_folder / "avatar_result.json").exists())
        self.assertTrue((comp_folder / "worker.json").exists())

        # 4. Assert worker.json Schema (Test Case 3)
        worker_data = json.loads((comp_folder / "worker.json").read_text(encoding="utf-8"))
        self.assertEqual(worker_data["worker"], "sadtalker_colab")
        self.assertEqual(worker_data["worker_version"], "1.0.0")
        self.assertEqual(worker_data["status"], "idle")
        self.assertEqual(worker_data["current_project"], "none")
        self.assertTrue("started_at" in worker_data)
        self.assertTrue("last_heartbeat" in worker_data)

        # 5. Assert ffprobe Transparent VP9 WebM output (Test Case 4)
        dur = colab_sadtalker_worker.validate_output_webm(comp_folder / "avatar.webm")
        self.assertGreater(dur, 0)
        print(f"  [VALIDATION] Produced transparent WebM. probed duration = {dur}s")

        # 6. Assert Timing Telemetry (Test Case 8)
        result_data = json.loads((comp_folder / "avatar_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result_data["avatar_schema_version"], 1)
        self.assertEqual(result_data["status"], "completed")
        self.assertTrue(result_data["background_removed"])
        self.assertTrue(result_data["alpha_video"])
        self.assertGreater(result_data["generation_time_seconds"], 0)
        self.assertGreater(result_data["encoding_seconds"], 0)
        self.assertGreater(result_data["total_processing_seconds"], 0)
        self.assertTrue("queue_wait_seconds" in result_data)

    @patch("colab_sadtalker_worker.run_self_test", return_value=True)
    def test_failure_handling(self, mock_test):
        """Failure Handling with invalid input (Test Case 11)."""
        # Create project with invalid manifest
        proj_id = "broken_project"
        proj_dir = self.queue_dir / f"project_{proj_id}"
        proj_dir.mkdir(parents=True, exist_ok=True)
        
        # Manifest version is invalid
        manifest = {
            "avatar_schema_version": 99,
            "provider": "unknown_provider"
        }
        (proj_dir / "avatar_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        worker = colab_sadtalker_worker.ColabWorker(
            sadtalker_dir=self.sadtalker_dir,
            drive_root=self.drive_root,
            scan_interval=0.1,
            workspace_root=str(self.workspace_root)
        )
        
        # Process job
        worker._poll_and_process()

        # Folder must transition to failed folder
        self.assertFalse((self.queue_dir / f"project_{proj_id}").exists())
        self.assertFalse((self.processing_dir / f"project_{proj_id}").exists())
        
        failed_folder = self.drive_root / "avatar_failed" / f"project_{proj_id}"
        self.assertTrue(failed_folder.exists())
        self.assertTrue((failed_folder / "failure_report.json").exists())
        
        report = json.loads((failed_folder / "failure_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["reason"], "worker_exception")
        self.assertTrue("Unsupported manifest config" in report["error_message"])
        print("  [VALIDATION] Failure handler correctly caught invalid manifest and moved folder to failed.")

    @patch("colab_sadtalker_worker.run_self_test", return_value=True)
    def test_abandoned_job_recovery(self, mock_test):
        """Stale processing folder recovery (Test Case 10)."""
        # Populate processing folder with an abandoned job
        proj_id = "abandoned_project"
        proc_dir = self.processing_dir / f"project_{proj_id}"
        proc_dir.mkdir(parents=True, exist_ok=True)
        
        # Write stale heartbeat
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        heartbeat = {
            "worker": "sadtalker_colab",
            "worker_version": "1.0.0",
            "status": "processing",
            "started_at": stale_time,
            "last_heartbeat": stale_time
        }
        (proc_dir / "worker.json").write_text(json.dumps(heartbeat, indent=2), encoding="utf-8")
        
        # Setup worker
        worker = colab_sadtalker_worker.ColabWorker(
            sadtalker_dir=self.sadtalker_dir,
            drive_root=self.drive_root,
            scan_interval=0.1,
            workspace_root=str(self.workspace_root)
        )
        
        # Run requeue scan
        worker.requeue_abandoned_jobs()
        
        # Job must be moved back to queue_path
        self.assertFalse((self.processing_dir / f"project_{proj_id}").exists())
        self.assertTrue((self.queue_dir / f"project_{proj_id}").exists())
        self.assertTrue((self.queue_dir / f"project_{proj_id}" / "worker.json").exists())
        print("  [VALIDATION] Abandoned job recovery detected stale heartbeat and requeued job back to queue.")

if __name__ == "__main__":
    unittest.main()
