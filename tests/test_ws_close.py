import logging
from fastapi.testclient import TestClient


def test_websocket_close_is_idempotent(client: TestClient, caplog):
    with caplog.at_level(logging.ERROR):
        with client.websocket_connect("/ws?token=test-token") as ws:
            ws.close()
            ws.close()
    assert "Failed to close websocket" not in caplog.text
