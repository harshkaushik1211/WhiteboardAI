import sys
import os
import json
import time
import shutil
import asyncio
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from utils.file_manager import ensure_project_dirs, save_json, new_project_id
from models.schemas import ScriptSchema, SceneSchema, LanguageMode
from services.voice.exporter import F5ExportService
from services.f5_queue_service import F5QueueService
from config import settings

# Test script definitions
TESTS = {
    "roman_hinglish": {
        "text": (
            "Socho ek football ground par pada hai. "
            "Jab tak koi force apply nahi karega, woh move nahi karega. "
            "Yahi Newton ke First Law ka basic idea hai."
        ),
        "language_mode": LanguageMode.HINGLISH
    },
    "devanagari_hindi": {
        "text": (
            "सोचो एक फुटबॉल ग्राउंड पर पड़ा है। "
            "जब तक कोई फोर्स अप्लाई नहीं करेगा, वह मूव नहीं करेगा। "
            "यही न्यूटन के फर्स्ट लॉ का बेसिक आइडिया है।"
        ),
        "language_mode": LanguageMode.HINGLISH
    },
    "english": {
        "text": (
            "Imagine a football lying on the ground. "
            "It will not move unless a force is applied. "
            "This is the basic idea behind Newton's First Law."
        ),
        "language_mode": LanguageMode.ENGLISH
    }
}

async def run_benchmark():
    # Configure stdout to use utf-8 on Windows
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("=" * 60)
    print("F5-TTS HINDI/HINGLISH BENCHMARK GENERATOR")
    print("=" * 60)

    # 1. Enqueue projects
    project_ids = {}
    exporter = F5ExportService()
    queue_service = F5QueueService()

    for name, data in TESTS.items():
        project_id = f"bench_{name[:4]}_{new_project_id()}"
        print(f"\n[{name.upper()}] Creating project with ID: {project_id}")
        ensure_project_dirs(project_id)
        
        # Create minimal config
        config_data = {
            "topic": f"Benchmark F5 {name}",
            "duration": 20,
            "style": "whiteboard",
            "voice": "male",
            "language": "english",
            "language_mode": data["language_mode"].value,
            "voice_provider": "f5tts",
            "avatar_provider": None,
            "visual_mode": "minimal"
        }
        save_json(project_id, "config.json", config_data)

        # Create scene schema
        scene = SceneSchema(
            scene_id=1,
            narration=data["text"],
            visual_description="A football on a ground",
            keywords=["football", "ground"],
            duration=15.0,
            scene_type="HOOK",
            language_mode=data["language_mode"]
        )

        script = ScriptSchema(
            title=f"Benchmark F5 {name}",
            total_duration=15.0,
            scenes=[scene],
            language_mode=data["language_mode"]
        )
        save_json(project_id, "script.json", script.model_dump())

        # Export narration package
        print(f"[{name.upper()}] Exporting narration package...")
        exporter.export(project_id, script)

        # Enqueue to Drive
        print(f"[{name.upper()}] Enqueuing to Google Drive queue...")
        queue_service.enqueue_project(project_id)
        project_ids[name] = project_id

    print("\n" + "=" * 60)
    print("WAITING FOR F5-TTS WORKER TO PROCESS JOBS...")
    print("Check your external Colab / F5-TTS worker log.")
    print("=" * 60)

    # 2. Poll for results
    completed_projects = {}
    dest_dir = Path("c:/projects/WhiteboardAI")
    
    start_time = time.time()
    timeout = 1800  # 30 minutes timeout
    
    while len(completed_projects) < len(TESTS):
        # Prevent hitting rate limits or spinning too fast
        await asyncio.sleep(15)
        
        elapsed = int(time.time() - start_time)
        print(f"Polling Drive completed folder... ({elapsed}s elapsed) Completed: {len(completed_projects)}/3")
        
        for name, pid in project_ids.items():
            if name in completed_projects:
                continue
                
            # Check completed Drive folder
            completed_folder = settings.f5_completed_path / f"project_{pid}"
            if completed_folder.exists():
                # Verify status.json and scene_1.wav exist
                status_file = completed_folder / "status.json"
                audio_file = completed_folder / "scene_1.wav"
                
                # Check for scene_1.mp3 as fallback
                if not audio_file.exists():
                    audio_file = completed_folder / "scene_1.mp3"
                    
                if status_file.exists() and audio_file.exists():
                    # Read status to verify it's complete
                    try:
                        with open(status_file, "r", encoding="utf-8") as f:
                            status_data = json.load(f)
                        if status_data.get("status") == "completed":
                            print(f"\n>>> [{name.upper()}] Completed folder found on Drive!")
                            
                            # Copy the completed audio file to final benchmark output file
                            dest_name = f"test_{name}.wav"
                            dest_path = dest_dir / dest_name
                            shutil.copy2(audio_file, dest_path)
                            
                            # Get file size and duration details
                            stat = dest_path.stat()
                            file_size_kb = round(stat.st_size / 1024, 2)
                            
                            completed_projects[name] = {
                                "path": str(dest_path.resolve()),
                                "size": f"{file_size_kb} KB",
                                "status": "completed",
                                "duration": status_data.get("duration", "unknown")
                            }
                            print(f"[{name.upper()}] Copied to: {dest_path}")
                    except Exception as e:
                        print(f"Error checking status for {name}: {e}")
                        
        if time.time() - start_time > timeout:
            print(f"\nTimeout of {timeout} seconds reached. Stopping benchmark polling.")
            break

    # 3. Print final benchmark summary
    print("\n" + "=" * 60)
    print("F5-TTS HINDI/HINGLISH BENCHMARK RESULTS")
    print("=" * 60)
    
    for name in TESTS.keys():
        res = completed_projects.get(name)
        if res:
            print(f"\n{name.replace('_', ' ').title()} Audio:")
            print(res["path"])
            print(f"Duration: {res['duration']} seconds")
            print(f"File Size: {res['size']}")
            print(f"Generation Status: {res['status']}")
        else:
            print(f"\n{name.replace('_', ' ').title()} Audio:")
            print("FAILED TO GENERATE (Timeout/Error)")
            print("Generation Status: failed")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
