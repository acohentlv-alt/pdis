"""
Basic API smoke tests for PDIS.
Requires a running server at http://localhost:8090.
Run with: pytest tests/test_api.py -v
"""

import pytest
import httpx


BASE_URL = "http://localhost:8090"


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "db_connected" in data


def test_presets(client):
    r = client.get("/api/presets")
    assert r.status_code == 200
    data = r.json()
    assert "presets" in data


def test_sessions(client):
    r = client.get("/api/scan/sessions")
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data


def test_properties(client):
    r = client.get("/api/properties")
    assert r.status_code == 200
    data = r.json()
    assert "properties" in data
    assert "total" in data
    assert "page" in data


def test_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_properties" in data
    assert "active_properties" in data


def test_property_not_found(client):
    r = client.get("/api/properties/nonexistent_id_xyz")
    assert r.status_code == 404
