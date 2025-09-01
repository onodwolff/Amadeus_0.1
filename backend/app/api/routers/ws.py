from __future__ import annotations
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from ...deps import state_dep

router = APIRouter(tags=["ws"])

@router.websocket("/ws")
async def ws_stream(ws: WebSocket, state = Depends(state_dep)):
    await ws.accept()
    q = state.register_ws()
    try:
        while True:
            data = await q.get()
            await ws.send_text(data)
    except WebSocketDisconnect:
        pass
    finally:
        state.unregister_ws(q)
