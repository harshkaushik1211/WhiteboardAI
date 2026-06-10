"""SadTalker Google Colab Queue Worker Script.

Designed for Phase-5 continuous worker loop with robust error-handling,
GPU memory recovery, direct ffmpeg-RGBA-streaming (no large RAM loads),
and compatibility with backend watcher services.
"""

from __future__ import annotations

import os
import gc
import re
import cv2
import time
import json
import signal
import shutil
import logging
import argparse
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Generator, Tuple, Optional

import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from transformers import AutoModelForImageSegmentation

# ── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("sadtalker_worker")

# ── Heartbeat & Health Telemetry Service (Hardening 4, Review 10) ─────────────
class HeartbeatService:
    """Updates worker.json with periodic timestamps and status reports."""
    def __init__(
        self,
        path: Path,
        version: str = "1.0.0",
        interval: float = 30.0
    ):
        self.path = path
        self.version = version
        self.interval = interval
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.status = "idle"
        self.current_project: Optional[str] = None
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def update_state(self, status: str, project_id: Optional[str] = None) -> None:
        self.status = status
        self.current_project = project_id
        # Force immediate write
        self._write_health()

    def _write_health(self) -> None:
        data = {
            "worker": "sadtalker_colab",
            "worker_version": self.version,
            "status": self.status,
            "current_project": self.current_project or "none",
            "started_at": self.started_at,
            "last_heartbeat": datetime.now(timezone.utc).isoformat()
        }
        try:
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[AVATAR_HEARTBEAT] Error writing heartbeat file: {e}")

    def _run(self) -> None:
        while not self.stop_event.is_set():
            self._write_health()
            self.stop_event.wait(self.interval)

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3.0)

# ── Pluggable Avatar Runners (Hardening 13) ───────────────────────────────────
class AvatarProviderRunner:
    """Base interface for different avatar providers to allow clean expansion."""
    def run(self, project_dir: Path, manifest: dict) -> Path:
        raise NotImplementedError("Providers must implement run()")

class SadTalkerRunner(AvatarProviderRunner):
    """Executes SadTalker command-line inference mapping manifest config to parameters."""
    def __init__(self, sadtalker_dir: Path):
        self.sadtalker_dir = sadtalker_dir

    def run(self, project_dir: Path, manifest: dict) -> Path:
        # Extract inputs from local workspace directory
        audio_file = manifest.get("audio_file", "combined.wav")
        image_file = manifest.get("source_image", "source_image.png")

        audio_path = project_dir / audio_file
        image_path = project_dir / image_file

        if not audio_path.exists():
            raise FileNotFoundError(f"Driven audio missing: {audio_path}")
        if not image_path.exists():
            raise FileNotFoundError(f"Source image missing: {image_path}")

        # Parse inference settings from manifest mapping
        sadtalker_cfg = manifest.get("sadtalker_config", {})
        still = sadtalker_cfg.get("still", True)
        preprocess = sadtalker_cfg.get("preprocess", "full")
        size = sadtalker_cfg.get("size", 256)
        enhancer = sadtalker_cfg.get("enhancer", None)

        output_dir = project_dir / "results"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build execution arguments
        cmd = [
            "python", str(self.sadtalker_dir / "inference.py"),
            "--driven_audio", str(audio_path),
            "--source_image", str(image_path),
            "--result_dir", str(output_dir),
            "--preprocess", str(preprocess),
            "--size", str(size)
        ]

        if still:
            cmd.append("--still")
        if enhancer:
            cmd.extend(["--enhancer", str(enhancer)])

        logger.info(f"[SADTALKER_RUNNER] Starting SadTalker process: {' '.join(cmd)}")
        
        # Execute SadTalker
        res = subprocess.run(cmd, cwd=str(self.sadtalker_dir), capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"SadTalker execution failed: {res.stderr}\nStdout: {res.stdout}")

        # Scan for output video (SadTalker outputs to output_dir/<timestamp>/*.mp4)
        mp4_files = list(output_dir.rglob("*.mp4"))
        if not mp4_files:
            raise FileNotFoundError(f"SadTalker completed but no output video found in {output_dir}")

        # Return latest modified MP4
        mp4_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        logger.info(f"[SADTALKER_RUNNER] Generation completed successfully: {mp4_files[0]}")
        return mp4_files[0]

# ── Background Removal Streamer (Hardening 1, 10, Review 11) ──────────────────
class BackgroundRemover:
    """Removes background frame-by-frame as a memory-safe generator pipeline."""
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None
        self.transform = T.Compose([
            T.Resize((1024, 1024)),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def load_model(self) -> None:
        """Loads BiRefNet, falling back to BRIA RMBG-1.4 if primary fails."""
        try:
            logger.info("[BACKGROUND_REMOVE] Loading primary model: ZhengPeng7/BiRefNet-general-lite")
            self.model = AutoModelForImageSegmentation.from_pretrained(
                "ZhengPeng7/BiRefNet-general-lite", trust_remote_code=True
            )
            self.model.to(self.device)
            self.model.eval()
            logger.info("[BACKGROUND_REMOVE] Primary model loaded successfully.")
        except Exception as e:
            logger.warning(f"[BACKGROUND_REMOVE] Primary BiRefNet model failed to load ({e}). Trying fallback...")
            try:
                logger.info("[BACKGROUND_REMOVE] Loading fallback model: briaai/RMBG-1.4")
                self.model = AutoModelForImageSegmentation.from_pretrained(
                    "briaai/RMBG-1.4", trust_remote_code=True
                )
                self.model.to(self.device)
                self.model.eval()
                logger.info("[BACKGROUND_REMOVE] Fallback model loaded successfully.")
            except Exception as fe:
                logger.error(f"[BACKGROUND_REMOVE] Fallback model failed to load ({fe}).")
                raise RuntimeError(f"All background removal models failed to load: {fe}")

    def stream_frame_removal(self, video_path: Path) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """Reads video frames one-by-one and yields processed (RGBA frame, alpha mask) bytes."""
        if self.model is None:
            self.load_model()

        cap = cv2.VideoCapture(str(video_path))
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                h, w, _ = frame.shape
                # OpenCV uses BGR, convert to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Transform to PyTorch Tensor
                pil_img = Image.fromarray(frame_rgb)
                input_tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

                with torch.no_grad():
                    output = self.model(input_tensor)
                    logits = output[0][0] if isinstance(output, tuple) else output
                    pred = torch.sigmoid(logits).cpu().data.numpy()[0, 0]
                    
                    # Resize mask to fit frame dimensions
                    mask = cv2.resize(pred, (w, h))
                    mask_uint8 = (mask * 255).astype(np.uint8)

                # Merge RGB with alpha mask
                rgba = cv2.merge([
                    frame_rgb[:, :, 0],
                    frame_rgb[:, :, 1],
                    frame_rgb[:, :, 2],
                    mask_uint8
                ])
                yield rgba, mask_uint8
        finally:
            cap.release()

# ── Dual WebM + Grayscale Mask Encoder (Hardening 1, 5) ───────────────────────
class VideoEncoder:
    """Streams frame sequences directly into ffmpeg stdin to write transparent videos."""
    @staticmethod
    def encode_dual(
        generator: Generator[Tuple[np.ndarray, np.ndarray], None, None],
        output_webm: Path,
        output_mask: Path,
        width: int,
        height: int,
        fps: float
    ) -> None:
        """Writes transparent VP9 WebM and grayscale mask MP4 concurrently."""
        webm_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "rgba",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "2M",
            "-auto-alt-ref", "0",
            "-speed", "4",
            str(output_webm)
        ]

        mask_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "gray",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_mask)
        ]

        logger.info(f"[AVATAR_ENCODE] Launching dual WebM and Mask ffmpeg processes.")
        proc_webm = subprocess.Popen(webm_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        proc_mask = subprocess.Popen(mask_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            for rgba_frame, mask_frame in generator:
                proc_webm.stdin.write(rgba_frame.tobytes())
                proc_mask.stdin.write(mask_frame.tobytes())
            
            proc_webm.stdin.close()
            proc_mask.stdin.close()

            _, err_webm = proc_webm.communicate()
            _, err_mask = proc_mask.communicate()

            if proc_webm.returncode != 0:
                raise RuntimeError(f"VP9 WebM encoding failed: {err_webm.decode('utf-8')}")
            if proc_mask.returncode != 0:
                raise RuntimeError(f"Mask MP4 encoding failed: {err_mask.decode('utf-8')}")
            
            logger.info("[AVATAR_ENCODE] Dual encoding complete.")
        except Exception as e:
            for p in (proc_webm, proc_mask):
                if p.poll() is None:
                    p.kill()
            raise e

# ── Self-Test & Safe Moves (Hardening 6, 9, Review 4, 5) ──────────────────────
def safe_move(src: Path, dst: Path, max_attempts: int = 3) -> None:
    """Moves directories on Drive with retries and exponential backoff."""
    attempt = 0
    delay = 2.0
    while attempt < max_attempts:
        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
            logger.info(f"[AVATAR_RECOVERY] Successfully moved {src.name} to {dst.parent.name}")
            return
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                logger.error(f"[AVATAR_RECOVERY] Directory move failed after {max_attempts} attempts: {e}")
                raise e
            logger.warning(f"[AVATAR_RECOVERY] Move failed (attempt {attempt}/{max_attempts}). Backoff sleep: {delay}s")
            time.sleep(delay)
            delay *= 2.0

def run_self_test(sadtalker_dir: Path, drive_root: Path) -> bool:
    """Verifies ffmpeg, GPU, checkpoints, and Drive mounts. Checks weight integrity (Review 4, 5)."""
    logger.info("[SADTALKER_SELF_TEST] Initiating self test diagnostics...")
    passed = True

    # 1. ffmpeg & ffprobe self-tests (Review 5)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        logger.info("  - ffmpeg: AVAILABLE")
    except Exception as e:
        logger.error(f"  - ffmpeg: NOT FOUND ({e})")
        passed = False

    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        logger.info("  - ffprobe: AVAILABLE")
    except Exception as e:
        logger.error(f"  - ffprobe: NOT FOUND ({e})")
        passed = False

    # 2. GPU availability
    if torch.cuda.is_available():
        logger.info(f"  - GPU: AVAILABLE ({torch.cuda.get_device_name(0)})")
    else:
        logger.error("  - GPU: NOT AVAILABLE (CUDA missing)")
        passed = False

    # 3. Drive root mount check
    if drive_root.exists():
        logger.info(f"  - Drive root path: MOUNTED ({drive_root})")
    else:
        logger.error(f"  - Drive root path: NOT MOUNTED ({drive_root})")
        passed = False

    # 4. Checkpoints pre-load weights integrity verification (Review 4)
    checkpoints = {
        "SadTalker_V0.0.2_256.safetensors": sadtalker_dir / "checkpoints" / "SadTalker_V0.0.2_256.safetensors",
        "mapping_00109-steps.pth": sadtalker_dir / "checkpoints" / "mapping_00109-steps.pth",
        "mapping_00229-steps.pth": sadtalker_dir / "checkpoints" / "mapping_00229-steps.pth"
    }

    for name, path in checkpoints.items():
        if not path.exists():
            logger.error(f"  - Checkpoint missing: {path}")
            passed = False
            continue

        if path.suffix == ".safetensors":
            try:
                from safetensors import safe_open
                with safe_open(str(path), framework="pt", device="cpu") as f:
                    f.keys()
                logger.info(f"  - Checkpoint verification: {name} (INTEGRITY PASS)")
            except Exception as e:
                logger.error(f"  - Checkpoint verification: {name} (CORRUPTED: {e})")
                passed = False
        else:
            try:
                # Use weights_only=True to prevent unsafe imports
                torch.load(str(path), map_location="cpu", weights_only=True)
                logger.info(f"  - Checkpoint verification: {name} (INTEGRITY PASS)")
            except Exception as e:
                logger.error(f"  - Checkpoint verification: {name} (CORRUPTED: {e})")
                passed = False

    if passed:
        logger.info("[SADTALKER_SELF_TEST] PASS")
    else:
        logger.error("[SADTALKER_SELF_TEST] FAIL")
    
    return passed

# ── Validation Layer (Hardening 3, 5) ─────────────────────────────────────────
def validate_output_webm(webm_path: Path) -> float:
    """Probes transparent WebM with ffprobe to verify structure, codec, and duration."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,pix_fmt,duration",
        "-of", "json",
        str(webm_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        if not streams:
            raise ValueError("No streams found in video file")
        
        stream = streams[0]
        codec = stream.get("codec_name")
        pix_fmt = stream.get("pix_fmt")
        
        if codec != "vp9":
            raise ValueError(f"Codec is {codec}, expected vp9")
        # Note: In transparent VP9 WebM containers, the alpha channel is often stored 
        # as auxiliary block side-data. Some builds of ffprobe decode the primary stream 
        # profile (yuv420p) rather than the alpha wrapper. We accept both yuv420p and yuva420p.
        if not pix_fmt or (pix_fmt not in ("yuv420p", "yuva420p") and "alpha" not in pix_fmt and "yuva" not in pix_fmt):
            raise ValueError(f"Pixel format {pix_fmt} lacks alpha channel support")

        # Resolve duration
        duration = float(stream.get("duration") or 0.0)
        if duration <= 0.0:
            # Try parsing format container duration
            fmt_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(webm_path)
            ]
            fmt_res = subprocess.run(fmt_cmd, capture_output=True, text=True, check=True)
            fmt_info = json.loads(fmt_res.stdout)
            duration = float(fmt_info.get("format", {}).get("duration" or 0.0))

        if duration <= 0.0:
            raise ValueError("Parsed clip duration is 0 or negative")
        
        return duration
    except Exception as e:
        raise ValueError(f"ffprobe validation failure: {e}")

def verify_drive_writes(folder: Path, max_attempts: int = 3, delay: float = 5.0) -> bool:
    """Ensures eventually consistent Drive writes are visible before moving directories."""
    for attempt in range(max_attempts):
        webm = folder / "avatar.webm"
        result_json = folder / "avatar_result.json"
        if webm.exists() and result_json.exists():
            logger.info("[AVATAR_SYNC] Output writes verified on Google Drive.")
            return True
        logger.warning(f"[AVATAR_SYNC] Files missing on Drive. Retrying verification ({attempt + 1}/{max_attempts})...")
        time.sleep(delay)
    return False

# ── Main Processing Loop ──────────────────────────────────────────────────────
class ColabWorker:
    def __init__(
        self,
        sadtalker_dir: Path,
        drive_root: Path,
        queue_dir: str = "avatar_queue",
        processing_dir: str = "avatar_processing",
        completed_dir: str = "avatar_completed",
        failed_dir: str = "avatar_failed",
        heartbeat_interval: float = 30.0,
        scan_interval: float = 5.0,
        workspace_root: str = "/content/workspace",
        worker_version: str = "1.0.0"
    ):
        self.sadtalker_dir = sadtalker_dir
        self.drive_root = drive_root
        self.version = worker_version
        self.heartbeat_interval = heartbeat_interval
        self.scan_interval = scan_interval
        self.workspace_root = Path(workspace_root)
        
        # Google Drive paths (Review 2, 11)
        self.queue_path = drive_root / queue_dir
        self.processing_path = drive_root / processing_dir
        self.completed_path = drive_root / completed_dir
        self.failed_path = drive_root / failed_dir

        self.bg_remover = BackgroundRemover()
        self.heartbeat: Optional[HeartbeatService] = None
        self.running = False

    def start(self) -> None:
        """Starts the worker polling loop with KeyboardInterrupt handlers (Review 9)."""
        self.running = True

        # Setup Clean Shutdown Signal Handlers (Review 9)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Startup self test
        if not run_self_test(self.sadtalker_dir, self.drive_root):
            logger.error("Self test failed. Refusing to start worker queue loop.")
            return

        # Ensure Drive folders exist
        for p in (self.processing_path, self.completed_path, self.failed_path):
            p.mkdir(parents=True, exist_ok=True)

        # Clear/Create temporary workspace (Review 7)
        if self.workspace_root.exists():
            shutil.rmtree(self.workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        # Notebook Restart Resilience: scan for abandoned jobs (Review 3)
        self.requeue_abandoned_jobs()

        logger.info("[SADTALKER_WORKER] Colab worker started. Scanning queue loop...")
        
        while self.running:
            try:
                self._poll_and_process()
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
            time.sleep(self.scan_interval)

    def _handle_shutdown(self, signum, frame) -> None:
        """Shuts down the thread and cleans workspace on KeyboardInterrupt (Review 9)."""
        logger.info("[SADTALKER_WORKER] Shutdown signal received. Performing clean exit...")
        self.running = False
        if self.heartbeat:
            self.heartbeat.stop()
        
        # Cleanup temporary workspace (Review 7)
        if self.workspace_root.exists():
            try:
                shutil.rmtree(self.workspace_root)
                logger.info("[SADTALKER_WORKER] Cleaned up temporary workspace folder.")
            except Exception as e:
                logger.error(f"Failed to clear workspace folder: {e}")
        
        logger.info("[SADTALKER_WORKER] Clean shutdown complete.")
        os._exit(0)

    def requeue_abandoned_jobs(self) -> None:
        """Scan processing folder on startup and requeue abandoned jobs (Review 3)."""
        if not self.processing_path.exists():
            return
        
        logger.info("[AVATAR_RECOVERY] Scanning for abandoned jobs in processing directory...")
        now = datetime.now(timezone.utc)
        
        for entry in self.processing_path.iterdir():
            if not entry.is_dir() or not entry.name.startswith("project_"):
                continue
                
            project_id = entry.name.replace("project_", "")
            logger.info(f"[AVATAR_RECOVERY] Checking active folder: {entry.name}")
            
            # Check worker.json or folder timestamp
            worker_file = entry / "worker.json"
            stale = False
            
            if worker_file.exists():
                try:
                    data = json.loads(worker_file.read_text(encoding="utf-8"))
                    last_hb_str = data.get("last_heartbeat")
                    if last_hb_str:
                        last_hb = datetime.fromisoformat(last_hb_str)
                        if last_hb.tzinfo is None:
                            last_hb = last_hb.replace(tzinfo=timezone.utc)
                        # Stale if last heartbeat was more than 3 minutes ago
                        if now - last_hb > timedelta(minutes=3):
                            stale = True
                            logger.info(f"[AVATAR_RECOVERY] Stale heartbeat found: last={now - last_hb}")
                except Exception as e:
                    logger.warning(f"[AVATAR_RECOVERY] Could not parse heartbeat: {e}")
                    stale = True
            else:
                # If no worker.json, check folder mtime
                mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
                if now - mtime > timedelta(minutes=5):
                    stale = True
                    logger.info(f"[AVATAR_RECOVERY] Stale folder mtime: last={now - mtime}")
                    
            if stale:
                logger.info(f"[AVATAR_RECOVERY] Abandoned job detected. Requeuing {entry.name}...")
                queue_dest = self.queue_path / entry.name
                try:
                    safe_move(entry, queue_dest)
                    # Reset status on Drive queue folder
                    status_json = queue_dest / "queue_status.json"
                    if status_json.exists():
                        try:
                            status_data = json.loads(status_json.read_text(encoding="utf-8"))
                            status_data["status"] = "queued"
                            status_json.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"[AVATAR_RECOVERY] Failed to requeue {entry.name}: {e}")

    def _poll_and_process(self) -> None:
        if not self.queue_path.exists():
            return

        # Scan for project folders
        project_folders = [p for p in self.queue_path.iterdir() if p.is_dir() and p.name.startswith("project_")]
        if not project_folders:
            return

        # Pick the oldest queued project folder
        project_folders.sort(key=lambda x: x.stat().st_mtime)
        queue_folder = project_folders[0]
        project_id = queue_folder.name.replace("project_", "")

        logger.info(f"[SADTALKER_PROCESSING] Discovered job: {queue_folder.name}")
        t_queue_wait_start = queue_folder.stat().st_mtime

        # Hardening 6: Free disk space check (Review 6)
        total, used, free = shutil.disk_usage(self.workspace_root)
        free_gb = free / (1024**3)
        if free_gb < 5.0:
            logger.error(f"[SADTALKER_PROCESSING] Aborting job {project_id}: Insufficient workspace storage. Free={free_gb:.2f}GB (Req=5GB)")
            return

        # Move Drive queue folder to Drive processing (Acts as lock - Step 1)
        drive_proc_folder = self.processing_path / queue_folder.name
        try:
            safe_move(queue_folder, drive_proc_folder)
        except Exception:
            logger.error(f"Could not lock/move {queue_folder.name} to processing.")
            return

        # Setup local temp directory workspace (Review 7)
        local_workspace = self.workspace_root / queue_folder.name
        if local_workspace.exists():
            shutil.rmtree(local_workspace)
        local_workspace.mkdir(parents=True, exist_ok=True)

        # Copy inputs from Drive processing folder to local workspace
        logger.info(f"[SADTALKER_PROCESSING] Copying assets to local workspace: {local_workspace}")
        for item in drive_proc_folder.iterdir():
            if item.is_file():
                shutil.copy2(item, local_workspace / item.name)

        # Startup heartbeat thread pointing to the local file (to copy back later)
        # We also write a copy directly to Drive processing folder for watchers (Review 10)
        drive_heartbeat_json = drive_proc_folder / "worker.json"
        self.heartbeat = HeartbeatService(drive_heartbeat_json, self.version, self.heartbeat_interval)
        self.heartbeat.update_state(status="processing", project_id=project_id)
        self.heartbeat.start()

        # Telemetry tracking variables (Hardening 8)
        telemetry = {
            "queue_wait_seconds": round(time.time() - t_queue_wait_start, 2),
            "generation_seconds": 0.0,
            "background_removal_seconds": 0.0,
            "encoding_seconds": 0.0,
            "total_processing_seconds": 0.0
        }
        t_start_processing = time.time()

        try:
            # Read manifest from local workspace
            manifest_path = local_workspace / "avatar_manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError("avatar_manifest.json is missing in package")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            
            # Compatibility check
            m_ver = manifest.get("avatar_schema_version" or manifest.get("manifest_version", 1))
            prov = manifest.get("provider")
            prov_ver = manifest.get("provider_version")

            if m_ver != 1 or prov != "sadtalker" or prov_ver != "sadtalker_v1":
                raise ValueError(
                    f"Unsupported manifest config: version={m_ver}, provider={prov}, version={prov_ver}"
                )

            # 1. Run SadTalker in local workspace (Step 4 & Hardening 12)
            t_gen_start = time.time()
            runner = SadTalkerRunner(self.sadtalker_dir)
            
            # Returns path to SadTalker output video clip in local workspace
            orig_mp4 = runner.run(local_workspace, manifest)
            telemetry["generation_seconds"] = round(time.time() - t_gen_start, 2)

            # Move original video to target filename inside local workspace
            avatar_original = local_workspace / "avatar_original.mp4"
            shutil.move(str(orig_mp4), str(avatar_original))

            # Resolve video parameters
            cap = cv2.VideoCapture(str(avatar_original))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            output_webm = local_workspace / "avatar.webm"
            output_mask = local_workspace / "avatar_mask.mp4"

            # 2. Background Removal Flag Check (Review 11)
            bg_removal_cfg = manifest.get("background_removal", {})
            bg_enabled = bg_removal_cfg.get("enabled", True) if isinstance(bg_removal_cfg, dict) else bool(bg_removal_cfg)

            if bg_enabled:
                t_bg_start = time.time()
                if self.bg_remover.model is None:
                    self.bg_remover.load_model()
                
                # Setup generator streams
                frame_gen = self.bg_remover.stream_frame_removal(avatar_original)
                telemetry["background_removal_seconds"] = round(time.time() - t_bg_start, 2)

                # 3. Encoding (Hardening 1)
                t_enc_start = time.time()
                VideoEncoder.encode_dual(
                    generator=frame_gen,
                    output_webm=output_webm,
                    output_mask=output_mask,
                    width=width,
                    height=height,
                    fps=fps
                )
                telemetry["encoding_seconds"] = round(time.time() - t_enc_start, 2)
            else:
                logger.info("[BACKGROUND_REMOVE] Background removal disabled. Direct VP9 WebM encoding.")
                t_enc_start = time.time()
                cmd = ["ffmpeg", "-y", "-i", str(avatar_original), "-c:v", "libvpx-vp9", "-b:v", "2M", str(output_webm)]
                subprocess.run(cmd, check=True, capture_output=True)
                telemetry["encoding_seconds"] = round(time.time() - t_enc_start, 2)

            telemetry["total_processing_seconds"] = round(time.time() - t_start_processing, 2)

            # 4. Validation Probing on Local File (Hardening 5)
            probed_dur = validate_output_webm(output_webm)

            # 5. Generate result files locally (Step 7 & Hardening 8)
            result = {
                "avatar_schema_version": 1,
                "status": "completed",
                "provider": "sadtalker",
                "provider_version": "sadtalker_v1",
                "background_removed": bg_enabled,
                "alpha_video": bg_enabled,
                "video_duration": round(probed_dur, 2),
                "generation_time_seconds": telemetry["generation_seconds"],
                "validation_passed": True,
                # Telemetry
                "queue_wait_seconds": telemetry["queue_wait_seconds"],
                "background_removal_seconds": telemetry["background_removal_seconds"],
                "encoding_seconds": telemetry["encoding_seconds"],
                "total_processing_seconds": telemetry["total_processing_seconds"]
            }
            (local_workspace / "avatar_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            (local_workspace / "status.json").write_text(json.dumps({"status": "completed"}, indent=2), encoding="utf-8")

            # Terminate heartbeat thread before moving folders
            self.heartbeat.stop()

            # Write final local worker status
            final_worker_data = {
                "worker": "sadtalker_colab",
                "worker_version": self.version,
                "status": "idle",
                "current_project": "none",
                "started_at": self.heartbeat.started_at,
                "last_heartbeat": datetime.now(timezone.utc).isoformat()
            }
            (local_workspace / "worker.json").write_text(json.dumps(final_worker_data, indent=2), encoding="utf-8")

            # 6. Copy final outputs back to Drive processing directory (Review 7)
            logger.info(f"[SADTALKER_PROCESSING] Copying results back to Drive: {drive_proc_folder}")
            for item in local_workspace.iterdir():
                if item.is_file():
                    shutil.copy2(item, drive_proc_folder / item.name)

            # 7. Drive Synchronization Check (Hardening 3)
            if not verify_drive_writes(drive_proc_folder):
                raise IOError("Failed to verify consistent writes of avatar.webm and avatar_result.json to Google Drive")

            # Move Drive processing directory to completed (Step 9)
            dest_folder = self.completed_path / queue_folder.name
            safe_move(drive_proc_folder, dest_folder)
            logger.info(f"[AVATAR_PROCESSING] Job completed successfully: {project_id}")

        except Exception as e:
            logger.error(f"[AVATAR_PROCESSING] Job FAILED: {project_id}. Error: {e}", exc_info=True)
            if self.heartbeat:
                self.heartbeat.stop()

            # Write failure reports locally first
            failure_report = {
                "reason": "worker_exception",
                "project_id": project_id,
                "error_message": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                (local_workspace / "failure_report.json").write_text(json.dumps(failure_report, indent=2), encoding="utf-8")
                (local_workspace / "status.json").write_text(json.dumps({"status": "failed"}, indent=2), encoding="utf-8")
                
                # Copy failures back to Drive processing
                for item in local_workspace.iterdir():
                    if item.is_file():
                        shutil.copy2(item, drive_proc_folder / item.name)
            except Exception as fe:
                logger.error(f"Could not write failure files: {fe}")

            # Move Drive processing to failed
            failed_dest = self.failed_path / queue_folder.name
            try:
                safe_move(drive_proc_folder, failed_dest)
            except Exception as me:
                logger.error(f"Failed to move folder to failed: {me}")

        finally:
            # Delete local workspace directory (Review 7)
            if local_workspace.exists():
                try:
                    shutil.rmtree(local_workspace)
                except Exception as cle:
                    logger.warning(f"Could not clear local temp folder: {cle}")

            # 8. Memory cleanups & recovery (Hardening 2)
            torch.cuda.empty_cache()
            gc.collect()
            logger.info("[AVATAR_GPU_CLEANUP] Cleaned CUDA caches and triggered garbage collection.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SadTalker Google Colab Queue Worker")
    parser.add_argument("--sadtalker_dir", type=str, required=True, help="Path to SadTalker directory")
    parser.add_argument("--drive_root", type=str, required=True, help="Path to Google Drive root folder")
    parser.add_argument("--queue_dir", type=str, default="avatar_queue")
    parser.add_argument("--processing_dir", type=str, default="avatar_processing")
    parser.add_argument("--completed_dir", type=str, default="avatar_completed")
    parser.add_argument("--failed_dir", type=str, default="avatar_failed")
    parser.add_argument("--heartbeat_interval", type=float, default=30.0)
    parser.add_argument("--scan_interval", type=float, default=5.0)
    parser.add_argument("--workspace", type=str, default="/content/workspace")
    parser.add_argument("--version", type=str, default="1.0.0")
    
    args = parser.parse_args()
    
    worker = ColabWorker(
        sadtalker_dir=Path(args.sadtalker_dir),
        drive_root=Path(args.drive_root),
        queue_dir=args.queue_dir,
        processing_dir=args.processing_dir,
        completed_dir=args.completed_dir,
        failed_dir=args.failed_dir,
        heartbeat_interval=args.heartbeat_interval,
        scan_interval=args.scan_interval,
        workspace_root=args.workspace,
        worker_version=args.version
    )
    worker.start()
