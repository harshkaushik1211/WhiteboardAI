import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils.job_queue import job_queue

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = job_queue.subscribe(job_id)

    job = job_queue.get_job(job_id)
    if job:
        await websocket.send_json(job.model_dump())

    try:
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(data)
                if data.get("step") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        job_queue.unsubscribe(job_id, queue)
