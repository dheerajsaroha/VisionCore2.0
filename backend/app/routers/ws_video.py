# backend/app/routers/ws_video.py
"""WebSocket endpoint for streaming video frames to the backend.
The client sends a JSON payload containing a base64‑encoded JPEG image.
The frame is enqueued to the Celery ``process_frame`` task and the result
(is returned as soon as the task finishes).  This is a minimal demo –
real‑world code would include authentication, validation, and a more
scalable result‑notification mechanism.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.tasks import process_frame

router = APIRouter()

@router.websocket("/ws/video")
async def video_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            frame = data.get("frame")
            if not frame:
                await websocket.send_json({"error": "No frame supplied"})
                continue

            # Enqueue Celery task – returns an AsyncResult
            task = process_frame.delay(frame)

            # Simple polling loop (non‑blocking) – in production use a callback or result backend.
            while not task.ready():
                await websocket.send_json({"status": "processing"})
                await asyncio.sleep(0.1)

            result = task.get()
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
