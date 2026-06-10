import sys
from pathlib import Path

# Ensure backend package is on path when running from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from api.routes import generate, websocket

app = FastAPI(
    title="AI Whiteboard Video Generator",
    description="Local educational whiteboard video generation API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, tags=["generation"])
app.include_router(websocket.router, tags=["websocket"])


@app.on_event("startup")
async def startup_build_asset_index():
    from services.svg_indexer import get_index
    from services.svg_retriever import svg_retriever

    entries = get_index()
    svg_retriever.reload()
    print(f"SVG asset index loaded: {len(entries)} assets")

    # Start F5 Completion Watcher (Phase-2)
    from services.f5_completion_watcher import F5CompletionWatcher
    watcher = F5CompletionWatcher()
    await watcher.start()

    # Start SadTalker completion/timeout watcher & cleanup loop (Phase-4)
    import asyncio
    async def sadtalker_watcher_loop():
        print("Starting SadTalker background watcher task (timeout recovery + cleanup).")
        from services.avatar.watcher import AvatarProcessingWatcher
        from services.avatar.cleanup import AvatarCleanupService
        
        watcher_inst = AvatarProcessingWatcher()
        cleanup_inst = AvatarCleanupService()
        
        while True:
            try:
                watcher_inst.check_timeouts()
            except Exception as e:
                import logging
                logging.getLogger("sadtalker_watcher").error(f"Error in SadTalker timeout check: {e}", exc_info=True)
                
            try:
                cleanup_inst.run()
            except Exception as e:
                import logging
                logging.getLogger("sadtalker_cleanup").error(f"Error in SadTalker cleanup sweep: {e}", exc_info=True)
                
            await asyncio.sleep(60) # Run every minute

    asyncio.create_task(sadtalker_watcher_loop())

# Serve generated media files
generated_path = settings.generated_path
generated_path.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(generated_path)), name="media")


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.openai_model}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
