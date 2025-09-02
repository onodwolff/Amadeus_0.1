# Amadeus 0.1

This project provides a FastAPI backend and an Angular frontend for the Amadeus trading bot.

## Authentication

All API and WebSocket endpoints require a static bearer token.

1. **Configure backend** – set the token via environment variable:
   ```bash
   export API_TOKEN="your-secret"
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Frontend** – expose the same token to the browser via `window.__TOKEN__` (and optionally `window.__API__`/`__WS__` for custom URLs). The Angular `ApiService` automatically sends the token in the `Authorization: Bearer` header and the `WsService` appends it as a `token` query parameter.

3. **Making requests** – clients must include the token:
   - HTTP: `Authorization: Bearer <token>`
   - WebSocket: connect to `/ws?token=<token>`

Changing `API_TOKEN` will invalidate existing clients.
