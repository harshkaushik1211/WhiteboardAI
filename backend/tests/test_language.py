import sys
import os
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

# Configure stdout/stderr to use utf-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from utils.language_validator import contains_devanagari
from services.llm_service import llm_service
from models.schemas import LanguageMode
from main import app

def test_contains_devanagari():
    # Should not detect Devanagari in pure Roman Hinglish or English
    assert not contains_devanagari("Force ek push ya pull hota hai.")
    assert not contains_devanagari("Gravity pull objects towards the earth.")
    
    # Should detect Devanagari in text containing Hindi characters
    assert contains_devanagari("Force एक push या pull hota hai.")
    assert contains_devanagari("बल एक धक्का या खिंचाव है।")
    assert contains_devanagari("यह object ki motion ko badal sakta hai.")
    print("test_contains_devanagari passed successfully!")

async def test_clean_devanagari_narration():
    mixed_text = "Force एक push ya pull hota hai. यह object की motion को badal sakta hai."
    print("Testing clean_devanagari_narration with mixed text...")
    cleaned = await llm_service.clean_devanagari_narration(mixed_text)
    print(f"Original: {repr(mixed_text)}")
    print(f"Cleaned:  {repr(cleaned)}")
    
    # Verify Devanagari is gone and it's not empty
    assert cleaned != mixed_text
    assert not contains_devanagari(cleaned)
    assert len(cleaned.strip()) > 0
    print("test_clean_devanagari_narration passed successfully!")

def test_generate_script_endpoint():
    print("Testing /generate-script endpoint with language_mode='hinglish'...")
    client = TestClient(app)
    payload = {
        "topic": "Gravity",
        "duration": 60,
        "style": "whiteboard",
        "voice": "male",
        "language": "english",
        "language_mode": "hinglish",
        "voice_provider": "edge",
        "educational_level": "high_school"
    }
    
    response = client.post("/generate-script", json=payload)
    assert response.status_code == 200, f"Failed: {response.text}"
    data = response.json()
    
    # Verify basic response fields
    assert "project_id" in data
    assert "script" in data
    # Hinglish now defaults to xtts_hindi
    assert data["tts_provider"] == "xtts_hindi"
    
    project_id = data["project_id"]
    script = data["script"]
    
    # Verify script metadata and structure
    assert script["language_mode"] == "hinglish"
    assert len(script["scenes"]) > 0
    
    # Verify individual scene metadata and script narration language (no Devanagari)
    for scene in script["scenes"]:
        assert scene["language_mode"] == "hinglish"
        assert not contains_devanagari(scene["narration"]), f"Scene {scene['scene_id']} narration contains Devanagari: {scene['narration']}"
        
    # Check that project_manifest.json exists and contains correct metadata
    from utils.file_manager import load_json
    manifest = load_json(project_id, "project_manifest.json")
    assert manifest is not None, "project_manifest.json was not created!"
    assert manifest["language_mode"] == "hinglish"
    assert manifest["requested_language"] == "hinglish"
    assert manifest["screen_language"] == "english"
    assert manifest["narration_language"] == "hinglish"
    # Hinglish now defaults to xtts_hindi
    assert manifest["tts_provider"] == "xtts_hindi"
    
    # Check that pedagogical_metrics.json exists and includes language validation telemetry
    metrics = load_json(project_id, "pedagogical_metrics.json")
    assert metrics is not None
    assert "language_validation" in metrics
    telemetry = metrics["language_validation"]
    assert telemetry["language_mode"] == "hinglish"
    assert "validation_passed" in telemetry
    
    print(f"test_generate_script_endpoint passed! project_id={project_id}")

def test_generate_script_request_defaulting():
    print("Testing GenerateScriptRequest validation and defaulting directly...")
    from models.schemas import GenerateScriptRequest, LanguageMode, TTSProvider
    from pydantic import ValidationError
    
    # 1. English with voice_provider="edge" defaults to tts_provider="edge_tts"
    req1 = GenerateScriptRequest(topic="Gravity", voice_provider="edge", language_mode=LanguageMode.ENGLISH)
    assert req1.tts_provider == TTSProvider.EDGE_TTS.value

    # 2. English with voice_provider="f5tts" defaults to tts_provider="f5tts"
    req2 = GenerateScriptRequest(topic="Gravity", voice_provider="f5tts", language_mode=LanguageMode.ENGLISH)
    assert req2.tts_provider == TTSProvider.F5TTS.value

    # 3. Hinglish defaults to tts_provider="xtts_hindi"
    req3 = GenerateScriptRequest(topic="Gravity", language_mode=LanguageMode.HINGLISH)
    assert req3.tts_provider == TTSProvider.XTTS_HINDI.value

    # 4. English with explicit tts_provider="edge_tts" is valid
    req4 = GenerateScriptRequest(topic="Gravity", tts_provider="edge_tts", language_mode=LanguageMode.ENGLISH)
    assert req4.tts_provider == TTSProvider.EDGE_TTS.value

    # 5. Explicit tts_provider="f5tts" for Hinglish is valid
    req5 = GenerateScriptRequest(topic="Gravity", tts_provider="f5tts", language_mode=LanguageMode.HINGLISH)
    assert req5.tts_provider == TTSProvider.F5TTS.value

    # 6. Invalid tts_provider raises ValidationError
    try:
        GenerateScriptRequest(topic="Gravity", tts_provider="invalid_provider")
        assert False, "Expected ValidationError for invalid provider"
    except ValidationError:
        pass

    # 7. indic_parler_tts is no longer a valid provider
    try:
        GenerateScriptRequest(topic="Gravity", tts_provider="indic_parler_tts")
        assert False, "Expected ValidationError for retired indic_parler_tts provider"
    except ValidationError:
        pass
        
    print("test_generate_script_request_defaulting passed successfully!")

async def run_async_tests():
    # Only run async tests if OpenAI API key is present
    from config import settings
    if not settings.openai_api_key:
        print("Skipping LLM tests because OPENAI_API_KEY is not set.")
        return
        
    try:
        await test_clean_devanagari_narration()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

if __name__ == "__main__":
    # Run direct Pydantic validation tests first (never depends on APIs)
    test_generate_script_request_defaulting()
    
    # Run synchronous test
    test_contains_devanagari()
    
    from config import settings
    if settings.openai_api_key:
        # Run async tests
        asyncio.run(run_async_tests())
        
        # Run endpoint test synchronously outside the asyncio loop
        test_generate_script_endpoint()
    else:
        print("Skipping LLM tests because OPENAI_API_KEY is not set.")
        
    print("All tests completed successfully!")
