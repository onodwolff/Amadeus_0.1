from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "Amadeus" in data.get("name", "")


def test_config_endpoint_requires_auth(client: TestClient, auth_headers):
    # no auth should be unauthorized
    resp = client.get("/api/config")
    assert resp.status_code == 401

    resp = client.get("/api/config", headers=auth_headers)
    assert resp.status_code == 200
    assert "cfg" in resp.json()
