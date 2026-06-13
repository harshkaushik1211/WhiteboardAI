import sys
import os
import shutil
import asyncio
import logging
from pathlib import Path

# Setup basic logging to see XlitEngine initialization and logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Windows console encoding reconfigure
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import settings
from models.schemas import ScriptSchema, SceneSchema, LanguageMode
from services.voice.providers.xtts_hindi import XTTSHindiProvider

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

async def run_end_to_end_test():
    print("=" * 60)
    print("Running XTTS Voice Generation End-to-End Test")
    print("=" * 60)

    # 1. Create a mock script in Hinglish
    scene1 = SceneSchema(
        scene_id=1,
        narration="Force ek push ya pull hota hai. Velocity aur Acceleration basic metrics hain.",
        visual_description="A box being pushed",
        keywords=["Force", "Velocity", "Acceleration"],
        duration=10.0,
        scene_type="EXPLANATION",
        language_mode=LanguageMode.HINGLISH
    )
    
    script = ScriptSchema(
        title="Test Hinglish Physics",
        total_duration=10.0,
        scenes=[scene1],
        language_mode=LanguageMode.HINGLISH
    )
    
    project_id = "test_xtts_integration_proj"
    
    # Resolve actual project path
    proj_path = settings.generated_path / "projects" / project_id
    print(f"Using actual project path for check: {proj_path.resolve()}")
    
    # Clean up project dir first if it exists
    if proj_path.exists():
        shutil.rmtree(proj_path)
        
    provider = XTTSHindiProvider()
    
    print(f"Script language_mode type: {type(script.language_mode)}")
    print(f"Script language_mode str: {str(script.language_mode)}")
    
    try:
        # 2. Run Voice Generation (uses IndicXlit internally)
        results = await provider.generate(project_id=project_id, script=script, voice="male")
        print("\nVoice generation run complete.")
        
        # 3. Check that debug files are saved inside project output directory
        original_script_path = proj_path / "original_script.txt"
        transliterated_script_path = proj_path / "transliterated_script.txt"
        
        assert original_script_path.exists(), f"original_script.txt was NOT created at: {original_script_path}!"
        assert transliterated_script_path.exists(), f"transliterated_script.txt was NOT created at: {transliterated_script_path}!"
        
        orig_content = original_script_path.read_text(encoding="utf-8")
        trans_content = transliterated_script_path.read_text(encoding="utf-8")
        
        print(f"Original script content:\n{orig_content}")
        print(f"Transliterated script content:\n{trans_content}")
        
        assert "Force ek push" in orig_content
        # Transliterated content should contain Devanagari equivalents
        assert "फोर्स" in trans_content
        assert "वेलोसिटी" in trans_content
        
        # 4. Check generated audio file
        audio_file = proj_path / "voices/scene_1.wav"
        assert audio_file.exists(), f"Generated audio file was not found at {audio_file}!"
        print(f"Generated WAV size: {audio_file.stat().st_size} bytes")
        
        print("\n  [PASS] Debug script saving and transliteration generation succeeded.")
        print("  [PASS] XTTS voice audio file created successfully.")
        
    finally:
        # Cleanup mock project dir to keep git status clean
        if proj_path.exists():
            shutil.rmtree(proj_path)
            print("Cleaned up test project directory.")

if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())
