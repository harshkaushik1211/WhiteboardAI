import asyncio
import json
import sys
from pathlib import Path

# Add backend package to path
sys.path.append("c:/Users/harsh/OneDrive/Desktop/WhiteboardAI/backend")

from models.schemas import GenerateScriptRequest
from api.routes.generate import generate_script

async def test_route(topic: str):
    print(f"\n==================================================")
    print(f"Testing /generate-script route for topic: {topic}")
    print(f"==================================================")
    
    req = GenerateScriptRequest(
        topic=topic,
        duration=60,
        style="whiteboard",
        language="english",
        educational_level="high_school"
    )
    
    res = await generate_script(req)
    project_id = res["project_id"]
    print(f"Route succeeded! Project ID: {project_id}")
    
    # Check that the concept decomposition files exist
    proj_dir = Path("c:/Users/harsh/OneDrive/Desktop/WhiteboardAI/generated/projects") / project_id
    files = [
        "concept_graph.json",
        "scene_concept_allocation.json",
        "concept_graph_audit.json",
        "script.json",
        "lesson_plan.json"
    ]
    for f in files:
        path = proj_dir / f
        exists = path.exists()
        print(f"- {f}: {'EXISTS' if exists else 'MISSING'} (size={path.stat().st_size if exists else 0})")
        if exists and f == "concept_graph_audit.json":
            with open(path, "r", encoding="utf-8") as file_obj:
                audit = json.load(file_obj)
                print(f"  +- Metrics: {audit.get('metrics')}")
                print(f"  +- Validation passed: {audit.get('validation_passed')}")

async def main():
    await test_route("Newton's Laws")
    await test_route("Photosynthesis")

if __name__ == "__main__":
    asyncio.run(main())
