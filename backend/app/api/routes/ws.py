from __future__ import annotations

import contextlib

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketException, status

from app.api.ws_manager import manager
from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models import User

router = APIRouter(tags=["ws"])


def _auth(token: str) -> int:
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from None
    db = SessionLocal()
    try:
        if db.get(User, user_id) is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    finally:
        db.close()
    return user_id


@router.websocket("/ws/alerts")
async def alerts_socket(ws: WebSocket, token: str = Query(...)):
    user_id = _auth(token)
    await manager.connect_user(user_id, ws)
    await ws.send_json({"type": "connected", "hint": "fetch current state via REST, then resume"})
    try:
        while True:
            # client may ping; we just keep the connection open
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            await manager.disconnect(ws, user_id)


@router.websocket("/ws/admin-feed")
async def admin_feed_socket(ws: WebSocket, token: str = Query(...)):
    _auth(token)
    await manager.connect_admin(ws)
    await ws.send_json({"type": "connected", "feed": "raw readings across all stations"})
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            await manager.disconnect(ws)
