import sys
import asyncio
import traceback
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from services.render_service import run_full_pipeline

async def main():
    try:
        print("Starting full pipeline run for a768e9b7...")
        await run_full_pipeline(
            job_id="test_run_job_2",
            project_id="a768e9b7",
            topic="Understanding the TCP Handshake",
            duration=60,
            style="whiteboard",
            voice="male",
            language="english"
        )
        print("Pipeline finished successfully!")
    except Exception as e:
        print("PIPELINE FAILED:")
        traceback.print_exc()

asyncio.run(main())
