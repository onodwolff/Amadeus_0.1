from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import aiosqlite
from starlette.concurrency import iterate_in_threadpool

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "history.db"


class HistoryStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._inited = False

    async def init(self) -> None:
        if self._inited:
            return
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS orders (
                                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                   ts REAL,
                                                                   event TEXT,
                                                                   symbol TEXT,
                                                                   side TEXT,
                                                                   type TEXT,
                                                                   price REAL,
                                                                   qty REAL,
                                                                   status TEXT,
                                                                   raw TEXT
                             );
                             """)
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS trades (
                                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                   ts REAL,
                                                                   type TEXT,
                                                                   symbol TEXT,
                                                                   side TEXT,
                                                                   price REAL,
                                                                   qty REAL,
                                                                   pnl REAL,
                                                                   raw TEXT
                             );
                             """)
            await db.commit()
        self._inited = True

    # ---------- append ----------
    async def log_order_event(self, evt: Dict[str, Any]) -> None:
        """
        evt: {type:'order_event', evt:'NEW'|'FILLED'|..., id, symbol, side, price, qty, status?, ts?}
        Совместимо со старым форматом {event, order:{...}}.
        """
        await self.init()
        o = evt.get("order") or {}
        ts = float(evt.get("ts") or evt.get("time") or evt.get("T") or o.get("updateTime") or o.get("transactTime") or 0.0)
        event = str(evt.get("evt") or evt.get("event") or o.get("status") or evt.get("status") or "")
        symbol = str(evt.get("symbol") or o.get("symbol") or "")
        side = (evt.get("side") or o.get("side") or "").upper() or None
        typ = (evt.get("ord_type") or o.get("type") or "").upper() or None
        price = _to_float(evt.get("price") or o.get("price"))
        qty = _to_float(evt.get("qty") or o.get("qty") or o.get("quantity") or o.get("origQty"))
        status = (evt.get("status") or o.get("status") or event or "").upper() or None
        raw = json.dumps(evt, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            await db.execute(
                "INSERT INTO orders(ts, event, symbol, side, type, price, qty, status, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, event, symbol, side, typ, price, qty, status, raw),
            )
            await db.commit()

    async def log_trade(self, evt: Dict[str, Any]) -> None:
        """
        evt: {type:'trade'|'fill', symbol, side?, price, qty, pnl?, ts?}
        """
        await self.init()
        ts = float(evt.get("ts") or evt.get("time") or evt.get("T") or 0.0)
        typ = str(evt.get("type") or "")
        symbol = str(evt.get("symbol") or evt.get("s") or "")
        side = (evt.get("side") or evt.get("S") or "").upper() or None
        price = _to_float(evt.get("price") or evt.get("p"))
        qty = _to_float(evt.get("qty") or evt.get("q"))
        pnl = _to_float(evt.get("pnl"))
        raw = json.dumps(evt, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            await db.execute(
                "INSERT INTO trades(ts, type, symbol, side, price, qty, pnl, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, typ, symbol, side, price, qty, pnl, raw),
            )
            await db.commit()

    # ---------- read ----------
    async def list_orders(self, limit: int = 200, offset: int = 0):
        await self.init()
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                    "SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def list_trades(self, limit: int = 200, offset: int = 0):
        await self.init()
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                    "SELECT * FROM trades ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def stats(self) -> Dict[str, int]:
        await self.init()
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            async with db.execute("SELECT COUNT(*) FROM orders") as c1, db.execute("SELECT COUNT(*) FROM trades") as c2:
                o = (await c1.fetchone())[0]
                t = (await c2.fetchone())[0]
        return {"orders": int(o), "trades": int(t)}

    async def clear(self, kind: str) -> Dict[str, int]:
        await self.init()
        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            if kind == "orders":
                await db.execute("DELETE FROM orders")
            elif kind == "trades":
                await db.execute("DELETE FROM trades")
            else:
                await db.execute("DELETE FROM orders")
                await db.execute("DELETE FROM trades")
            await db.commit()
        return await self.stats()

    # ---------- export ----------
    async def export_csv_iter(self, kind: str) -> Iterable[bytes]:
        """
        Возвращает async-итератор байтов CSV (для StreamingResponse).
        """
        await self.init()
        header = []
        query = ""
        if kind == "orders":
            header = ["id", "ts", "event", "symbol", "side", "type", "price", "qty", "status"]
            query = "SELECT id, ts, event, symbol, side, type, price, qty, status FROM orders ORDER BY id DESC"
        else:
            header = ["id", "ts", "type", "symbol", "side", "price", "qty", "pnl"]
            query = "SELECT id, ts, type, symbol, side, price, qty, pnl FROM trades ORDER BY id DESC"

        yield (",".join(header) + "\n").encode("utf-8")

        async with aiosqlite.connect(self.db_path.as_posix()) as db:
            async with db.execute(query) as cur:
                async for row in cur:
                    line = ",".join(_csv_cell(v) for v in row) + "\n"
                    yield line.encode("utf-8")


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if "," in s or "\"" in s or "\n" in s:
        s = "\"" + s.replace("\"", "\"\"") + "\""
    return s
