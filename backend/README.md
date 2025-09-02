# Amadeus Backend (FastAPI)

## Run
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## ENV
See `.env.example`. Defaults to shadow/paper mode.

### Authentication
- Set `API_TOKEN` to the shared secret used by clients.
- All `/api/*` endpoints expect `Authorization: Bearer <token>`.
- The WebSocket `/ws` requires `?token=<token>` in the URL.

## Structure
- `api/routers/*` — REST/WS routes
- `services/*` — Binance wrapper, MarketMaker, PairScanner, ShadowExecutor
- `core/config.py` — env + yaml config
- `models/schemas.py` — Pydantic schemas
- `services/state.py` — application state

## Endpoints
- `POST /bot/start`
- `POST /bot/stop`
- `GET /bot/status`
- `POST /scanner/scan`
- `GET /config` / `PUT /config`
- `WS /ws`
