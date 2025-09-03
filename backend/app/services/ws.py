from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Set
from collections.abc import Mapping

from ..models.schemas import BotStatus

logger = logging.getLogger(__name__)


class WSBroadcaster:
    """Manage websocket clients and broadcast events."""

    def __init__(self) -> None:
        self._clients: Set[asyncio.Queue[str]] = set()
        self.sent_counter = 0
        self.sent_last_ts = time.time()

    # --- client management -------------------------------------------------
    @property
    def clients(self) -> Set[asyncio.Queue[str]]:
        return self._clients

    def register_ws(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._clients.add(q)
        logger.info("WS connected. total=%d", len(self._clients))
        return q

    def unregister_ws(self, q: asyncio.Queue[str]) -> None:
        self._clients.discard(q)
        logger.info("WS disconnected. total=%d", len(self._clients))

    def ws_subscribe(self, q: asyncio.Queue) -> callable:
        self._clients.add(q)  # type: ignore
        logger.info("WS connected (ext). total=%d", len(self._clients))

        def _unsub():
            try:
                self._clients.discard(q)  # type: ignore
                logger.info("WS disconnected (ext). total=%d", len(self._clients))
            except Exception:
                logger.exception("Failed to disconnect websocket client")

        return _unsub

    # --- broadcasting ------------------------------------------------------
    def _broadcast_obj(self, obj: Any) -> None:
        try:
            if isinstance(obj, dict):
                data = json.dumps(obj, ensure_ascii=False)
            elif isinstance(obj, str):
                data = obj
            else:
                if hasattr(obj, "model_dump"):
                    data = json.dumps(obj.model_dump(), ensure_ascii=False)
                elif hasattr(obj, "dict"):
                    data = json.dumps(obj.dict(), ensure_ascii=False)
                elif is_dataclass(obj):
                    data = json.dumps(asdict(obj), ensure_ascii=False)
                elif isinstance(obj, Mapping):
                    data = json.dumps(dict(obj), ensure_ascii=False)
                else:
                    data = str(obj)
        except Exception:
            logger.exception("Failed to serialize broadcast obj, sending as text")
            data = str(obj)

        for q in list(self._clients):
            try:
                q.put_nowait(data)
                self.sent_counter += 1
            except asyncio.QueueFull:
                self._clients.discard(q)

    def broadcast(self, type_: str, **payload: Any) -> None:
        self._broadcast_obj({"type": type_, **payload})

    def broadcast_status(self, status: BotStatus) -> None:
        try:
            payload = status.model_dump()  # pydantic v2
        except Exception:
            payload = {
                "running": status.running,
                "symbol": status.symbol,
                "metrics": status.metrics,
                "cfg": status.cfg,
            }
        payload["type"] = "status"
        self._broadcast_obj(payload)
