import asyncio
import httpx
from httpx import MockTransport, Response, Request

from backend.app.services.binance_client import BinanceRestClient
from backend.app.services.pair_scanner import scan_best_symbol


def test_scan_best_symbol_binance_rest_client():
    async def _run():
        exchange_info = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
                {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
            ]
        }
        tickers = {
            "BTCUSDT": {"symbol": "BTCUSDT", "quoteVolume": "1000000", "lastPrice": "20000"},
            "ETHUSDT": {"symbol": "ETHUSDT", "quoteVolume": "2000000", "lastPrice": "1500"},
        }
        books = {
            "BTCUSDT": {"symbol": "BTCUSDT", "bidPrice": "20000", "askPrice": "20010"},
            "ETHUSDT": {"symbol": "ETHUSDT", "bidPrice": "1500", "askPrice": "1501"},
        }
        klines = {
            "BTCUSDT": [
                [0, 0, "20010", "19990", "20000", "0", 0, 0, 0, 0, 0, 0],
                [0, 0, "20020", "20000", "20010", "0", 0, 0, 0, 0, 0, 0],
            ],
            "ETHUSDT": [
                [0, 0, "1501", "1499", "1500", "0", 0, 0, 0, 0, 0, 0],
                [0, 0, "1502", "1500", "1501", "0", 0, 0, 0, 0, 0, 0],
            ],
        }

        def handler(request: Request) -> Response:
            path = request.url.path
            if path == "/api/v3/exchangeInfo":
                return Response(200, json=exchange_info)
            if path == "/api/v3/ticker/24hr":
                sym = request.url.params["symbol"]
                return Response(200, json=tickers[sym])
            if path == "/api/v3/ticker/bookTicker":
                sym = request.url.params["symbol"]
                return Response(200, json=books[sym])
            if path == "/api/v3/klines":
                sym = request.url.params["symbol"]
                return Response(200, json=klines[sym])
            return Response(404)

        transport = MockTransport(handler)
        client = BinanceRestClient(api_key=None, api_secret=None, paper=True)
        client._client = httpx.AsyncClient(transport=transport, base_url="https://test/api")

        cfg = {
            "scanner": {
                "quote": "USDT",
                "min_price": 0,
                "min_vol_usdt_24h": 0,
                "top_by_volume": 10,
                "max_pairs": 10,
                "min_spread_bps": 0,
                "vol_bars": 2,
                "score": {"w_spread": 1.0, "w_vol": 0.0},
            }
        }

        result = await scan_best_symbol(cfg, client)
        assert result["best"]["symbol"] == "ETHUSDT"
        await client.aclose()

    asyncio.run(_run())
