"""WebSocket GET /api/v1/jobs/{job_id}/events (contracts/websocket.md)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/api/v1/jobs/{job_id}/events")
async def job_events(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    runner = ws.app.state.runner
    try:
        if runner.has_job(job_id):
            async for msg in runner.events(job_id):
                await ws.send_json(msg)
            await ws.close(code=1000)
            return
        snap = ws.app.state.lookup_snapshot(job_id)
        if snap is None:
            await ws.close(code=4404, reason="Job não encontrado.")
            return
        snapshot, finished = snap
        await ws.send_json(snapshot)
        if finished is not None:
            await ws.send_json(finished)
        await ws.close(code=1000)
    except WebSocketDisconnect:
        return
