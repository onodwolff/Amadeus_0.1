# Amadeus Backend (FastAPI)

Requires **Python 3.12+**. Key libraries include FastAPI 0.116+, Uvicorn 0.35+, and
Pydantic 2.11+.

## Run
```bash
python3.12 -m venv .venv && source .venv/bin/activate
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

## Configuration
Runtime options are read from `config.yaml` (see `config.example.yaml` for the full schema).
The following sections were added:

```yaml
api:
  paper: true
  shadow: false
  autostart: false
ui:
  chart: tv
  theme: dark
features:
  risk_protections: true
  market_widget_feed: true
risk:
  max_drawdown_pct: 10.0
  dd_window_sec: 86400
  stop_duration_sec: 43200
  cooldown_sec: 1800
  min_trades_for_dd: 0
history:
  db_path: data/history.db
  retention_days: 365
```

The `strategy` section includes a `loop_sleep` option to configure the pause in
seconds between each iteration of the market-making loop. The default is `0.2`.

## Endpoints
- `POST /bot/start`
- `POST /bot/stop`
- `GET /bot/status`
- `POST /scanner/scan`
- `GET /config` / `PUT /config`
- `WS /ws`
