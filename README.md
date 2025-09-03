# Amadeus 0.1

This project provides a FastAPI backend and an Angular frontend for the Amadeus trading bot.

The backend targets **Python 3.12+** and depends on FastAPI 0.116+, Uvicorn 0.35+, and
Pydantic 2.11+.

> **Note**: building the frontend requires **Node.js 20+**.

By default the FastAPI server listens on port **8100** and the Angular development server runs on port **4400**.

## Authentication

All API and WebSocket endpoints require a static bearer token.

1. **Configure backend** – set the token via environment variable:
   ```bash
   export API_TOKEN="your-secret"
   uvicorn app.main:app --host 0.0.0.0 --port 8100
   ```

2. **Frontend** – expose the same token to the browser via `window.__TOKEN__` (and optionally `window.__WS__` for a custom WebSocket URL). The API base URL is configured in `src/environments/environment.ts`. The Angular `ApiService` automatically sends the token in the `Authorization: Bearer` header and the `WsService` appends it as a `token` query parameter.

3. **Making requests** – clients must include the token:
   - HTTP: `Authorization: Bearer <token>`
   - WebSocket: connect to `/ws?token=<token>`

Changing `API_TOKEN` will invalidate existing clients.

## Standalone scanner

The pair scanner can be used without starting the trading bot. The `/scanner/scan` route will
create a temporary Binance `AsyncClient` when no global client is available. Provide your API
credentials via environment variables before launching the backend:

```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Then call the scanner endpoint:

```bash
curl -X POST "http://localhost:8100/scanner/scan" \
     -H "Authorization: Bearer $API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'
```

The request returns the best trading pair and the top candidates based on your configuration.

The scanner's `min_vol_usdt_24h` and `min_spread_bps` thresholds are tuned for
liquid mainnet markets. When using Binance testnet (`api.paper: true`) or
trading pairs with low liquidity, lower these values; otherwise the scanner may
reject all candidates. The backend automatically falls back to near-zero
thresholds in paper mode, but adjust them as needed for your environment.

## Testing

1. Create a Python 3.12 virtual environment and install dependencies:
   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Run the test suite:
   ```bash
   pytest
   ```
