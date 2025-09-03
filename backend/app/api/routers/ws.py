from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any, Callable, Optional
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from ...services.state import get_state
from ...core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def _safe_send(ws: WebSocket, msg: Any, timeout: float = 5.0) -> None:
    """
    Отправляем корректно: строки как text, объекты как json.

    Если отправка занимает слишком много времени, сообщение будет пропущено.
    """
    try:
        if isinstance(msg, str):
            await asyncio.wait_for(ws.send_text(msg), timeout)
        else:
            await asyncio.wait_for(ws.send_json(msg), timeout)
    except asyncio.TimeoutError:
        # Клиент не успел принять сообщение — просто пропускаем его
        logger.warning("WebSocket send timed out; dropping message")
    except Exception:
        logger.exception("WebSocket send failed, falling back to text")
        try:
            await asyncio.wait_for(
                ws.send_text(json.dumps(msg, default=str, ensure_ascii=False)),
                timeout,
            )
        except Exception:
            logger.exception("WebSocket fallback send failed")


def _subscribe(state: Any) -> tuple[asyncio.Queue, Callable[[], None]]:
    """
    Подписка на события state.
    Важно: работаем ИМЕННО с той очередью, которую слушает роутер.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)

    # Предпочитаем state.ws_subscribe(q) -> unsub
    if hasattr(state, "ws_subscribe"):
        unsub = state.ws_subscribe(q)  # type: ignore
        return q, unsub

    # Совместимость: register/unregister
    if hasattr(state, "register_ws"):
        # добавим q напрямую в пул
        if hasattr(state, "_clients") and isinstance(getattr(state, "_clients"), set):
            getattr(state, "_clients").add(q)
        def _unsub():
            try:
                state.unregister_ws(q)  # type: ignore
            except Exception:
                logger.exception("state.unregister_ws failed")
                try:
                    if hasattr(state, "_clients") and isinstance(getattr(state, "_clients"), set):
                        getattr(state, "_clients").discard(q)
                except Exception:
                    logger.exception("Failed to remove websocket client from pool")
        return q, _unsub

    # Фолбэк на приватное множество
    target_set_name = "_clients" if hasattr(state, "_clients") else "_ws_clients"
    client_set = getattr(state, target_set_name, None)
    if isinstance(client_set, set):
        client_set.add(q)
    def _unsub():
        try:
            if isinstance(client_set, set):
                client_set.discard(q)
        except Exception:
            logger.exception("Failed to discard websocket client")
    return q, _unsub


@router.websocket("/ws")
async def ws_stream(ws: WebSocket):
    """Стрим событий в UI. Устойчив к отключениям и shutdown."""
    token = ws.query_params.get("token")
    if not token or not secrets.compare_digest(token, settings.api_token or ""):
        await ws.close(code=1008, reason="Invalid token")
        return

    await ws.accept()
    state = await get_state()

    q, unsub = _subscribe(state)

    recv_task: Optional[asyncio.Task] = None
    send_task: Optional[asyncio.Task] = None

    try:
        # привет + первичный статус
        await _safe_send(ws, {"type": "hello", "version": "1.0"})
        try:
            cfg = getattr(state, "cfg", {}) or {}
            strat = (cfg.get("strategy") or {})
            name = strat.get("name")
            symbol = (strat.get(name, {}) or {}).get("symbol")
            await _safe_send(ws, {
                "type": "status",
                "running": bool(state.is_running()) if hasattr(state, "is_running") else False,
                "equity": getattr(state, "equity", None),
                "symbol": symbol,
            })
        except Exception:
            logger.exception("Failed to send initial status")

        recv_task = asyncio.create_task(ws.receive_text())
        send_task = asyncio.create_task(q.get())

        while True:
            done, _ = await asyncio.wait({recv_task, send_task}, return_when=asyncio.FIRST_COMPLETED)

            # входящие (пинги) — читаем и игнорим
            if recv_task in done:
                try:
                    _ = recv_task.result()
                except WebSocketDisconnect:
                    break
                except Exception:
                    logger.exception("Error receiving from WebSocket")
                finally:
                    recv_task = asyncio.create_task(ws.receive_text())

            # исходящие
            if send_task in done:
                try:
                    msg = send_task.result()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error getting message from queue")
                    msg = None

                if msg is None:
                    logger.warning("Queue returned None, closing connection")
                    break

                await _safe_send(ws, msg)
                send_task = asyncio.create_task(q.get())

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except asyncio.CancelledError:
        logger.info("WebSocket connection cancelled")
    finally:
        try:
            if recv_task:
                recv_task.cancel()
        except Exception:
            logger.exception("Failed to cancel recv_task")
        try:
            if send_task:
                send_task.cancel()
        except Exception:
            logger.exception("Failed to cancel send_task")
        try:
            unsub()
        except Exception:
            logger.exception("Failed to unsubscribe websocket")
        try:
            if (
                ws.client_state is not WebSocketState.DISCONNECTED
                and ws.application_state is not WebSocketState.DISCONNECTED
            ):
                await ws.close(code=1000, reason="Connection closed")
        except RuntimeError:
            # Socket already closed; skip without logging
            pass
        except Exception:
            logger.exception("Failed to close websocket")
