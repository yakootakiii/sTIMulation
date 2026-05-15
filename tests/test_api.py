"""Integration tests for Socket.IO and API endpoints."""
import pytest
import json
from app import app, socketio
from simulation import SimConfig


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestAPI:
    def test_api_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "running" in data

    def test_api_vehicles(self, client):
        resp = client.get("/api/vehicles")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_api_config_get(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "scenario" in data or data == {}

    def test_api_config_post(self, client):
        payload = {"scenario": "rush", "speed_factor": 2.0}
        resp = client.post("/api/config", json=payload)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get("ok") is True

    def test_api_metrics(self, client):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "total_passed" in data
        assert "avg_wait" in data


class TestUI:
    def test_index_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"sTIMulation" in resp.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
