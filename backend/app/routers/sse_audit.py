# backend/app/routers/sse_audit.py
"""Server‑Sent Events endpoint for live audit logs.
This demo yields a synthetic audit event every second. In a real system you would
listen to DB triggers or a message queue.
"""
import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

async def audit_event_generator():
    counter = 0
    while True:
        await asyncio.sleep(1)
        payload = {
            "event_id": counter,
            "action": "login",
            "user_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        counter += 1
        yield f"event: audit\ndata: {json.dumps(payload)}\n\n"

@router.get("/sse/audit")
async def sse_audit(request: Request):
    async def event_stream():
        async for ev in audit_event_generator():
            if await request.is_disconnected():
                break
            yield ev
    return StreamingResponse(event_stream(), media_type="text/event-stream")
