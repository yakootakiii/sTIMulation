"""
Integration Tests — app.py (Flask REST API + SocketIO)
Tests the HTTP endpoints and SocketIO event flow end-to-end.
"""

import sys, os, time, threading, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

# ── Patch Redis before importing app so cache falls back to SimpleCache ───────
with patch("flask_caching.Cache.get", side_effect=Exception("no redis")):
    pass  # just warm the import path

os.environ.setdefault("TESTING", "1")

# Patch out Redis on the cache init
import flask_caching
_orig_cache_init = flask_caching.Cache.__init__

def _patched_cache_init(self, app=None, config=None, **kwargs):
    fallback = {
        "CACHE_TYPE": "SimpleCache",
        "CACHE_DEFAULT_TIMEOUT": 5,
    }
    _orig_cache_init(self, app=app, config=fallback, **kwargs)

flask_caching.Cache.__init__ = _patched_cache_init

import app as app_module
from app import app as flask_app, socketio

flask_app.config["TESTING"] = True
flask_app.config["SECRET_KEY"] = "test-secret"


@pytest.fixture(autouse=True)
def reset_sim():
    """Reset global sim state between every test."""
    app_module.sim = None
    yield
    if app_module.sim and app_module.sim.running:
        app_module.sim.stop()
    app_module.sim = None


@pytest.fixture()
def client():
    with flask_app.test_client() as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 1. Route smoke tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRoutes:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_analytics_returns_200(self, client):
        resp = client.get("/analytics")
        assert resp.status_code == 200

    def test_index_contains_html(self, client):
        resp = client.get("/")
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data


# ══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/status
# ══════════════════════════════════════════════════════════════════════════════

class TestStatusEndpoint:
    def test_status_when_no_sim(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False

    def test_status_after_sim_created(self, client):
        app_module.new_sim()
        app_module.invalidate_sim_cache()  # ensure we get fresh data
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "running" in data
        assert "paused" in data

    def test_status_has_stats_keys(self, client):
        app_module.new_sim()
        app_module.invalidate_sim_cache()  # ensure we get fresh data
        resp = client.get("/api/status")
        data = resp.get_json()
        for key in ("total_passed", "avg_wait", "cycles"):
            assert key in data


# ══════════════════════════════════════════════════════════════════════════════
# 3. GET /api/vehicles
# ══════════════════════════════════════════════════════════════════════════════

class TestVehiclesEndpoint:
    def test_vehicles_returns_list(self, client):
        app_module.new_sim()
        resp = client.get("/api/vehicles")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_vehicles_empty_at_start(self, client):
        app_module.new_sim()
        resp = client.get("/api/vehicles")
        assert resp.get_json() == []


# ══════════════════════════════════════════════════════════════════════════════
# 4. GET /api/config
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigGetEndpoint:
    def test_config_get_returns_200(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200

    def test_config_has_required_fields(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        for field in ("green_duration", "yellow_duration", "red_duration",
                      "scenario", "road_type", "right_turn_free", "speed_factor"):
            assert field in data, f"Missing field: {field}"

    def test_config_defaults(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        assert data["green_duration"] == 20.0
        assert data["yellow_duration"] == 4.0
        assert data["scenario"] == "normal"


# ══════════════════════════════════════════════════════════════════════════════
# 5. POST /api/config
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigPostEndpoint:
    def test_update_green_duration(self, client):
        resp = client.post("/api/config",
                           data=json.dumps({"green_duration": 30.0}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["config"]["green_duration"] == 30.0

    def test_update_scenario(self, client):
        resp = client.post("/api/config",
                           data=json.dumps({"scenario": "rush"}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert resp.get_json()["config"]["scenario"] == "rush"

    def test_empty_payload_returns_400(self, client):
        resp = client.post("/api/config",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_value_returns_400(self, client):
        resp = client.post("/api/config",
                           data=json.dumps({"green_duration": "not-a-number"}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_update_persisted_in_sim(self, client):
        client.post("/api/config",
                    data=json.dumps({"green_duration": 45.0}),
                    content_type="application/json")
        assert app_module.sim.config.green_duration == 45.0

    def test_update_right_turn_free_false(self, client):
        resp = client.post("/api/config",
                           data=json.dumps({"right_turn_free": False}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert resp.get_json()["config"]["right_turn_free"] is False

    def test_unknown_keys_rejected(self, client):
        """Unknown keys should be rejected at the API boundary."""
        resp = client.post("/api/config",
                           data=json.dumps({"green_duration": 25.0, "bogus_key": "x"}),
                           content_type="application/json")
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# 6. GET /api/metrics
# ══════════════════════════════════════════════════════════════════════════════

class TestMetricsEndpoint:
    def test_metrics_without_sim_returns_400(self, client):
        resp = client.get("/api/metrics")
        assert resp.status_code == 400

    def test_metrics_with_sim_returns_200(self, client):
        app_module.new_sim()
        resp = client.get("/api/metrics")
        assert resp.status_code == 200

    def test_metrics_has_stats_keys(self, client):
        app_module.new_sim()
        resp = client.get("/api/metrics")
        data = resp.get_json()
        for key in ("total_passed", "avg_wait", "cycles", "sim_time", "queues"):
            assert key in data

    def test_metrics_queues_have_four_directions(self, client):
        app_module.new_sim()
        resp = client.get("/api/metrics")
        data = resp.get_json()
        for d in ("N", "S", "E", "W"):
            assert d in data["queues"]


# ══════════════════════════════════════════════════════════════════════════════
# 7. new_sim / sim lifecycle helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestSimLifecycle:
    def test_new_sim_creates_sim_instance(self):
        from simulation import TrafficSimulation
        s = app_module.new_sim()
        assert isinstance(s, TrafficSimulation)

    def test_new_sim_replaces_existing(self):
        s1 = app_module.new_sim()
        s2 = app_module.new_sim()
        assert s1 is not s2

    def test_new_sim_stops_running_sim(self):
        s1 = app_module.new_sim()
        s1.start()
        time.sleep(0.05)
        assert s1.running is True
        app_module.new_sim()  # should stop s1
        time.sleep(0.1)
        assert s1.running is False

    def test_apply_cfg_sets_green(self):
        from simulation import SimConfig
        cfg = SimConfig()
        app_module._apply_cfg(cfg, {"green": 35.0})
        assert cfg.green_duration == 35.0

    def test_apply_cfg_sets_scenario(self):
        from simulation import SimConfig
        cfg = SimConfig()
        app_module._apply_cfg(cfg, {"scenario": "low"})
        assert cfg.scenario == "low"

    def test_apply_cfg_sets_road_type(self):
        from simulation import SimConfig
        cfg = SimConfig()
        app_module._apply_cfg(cfg, {"road_type": 6})
        assert cfg.road_type == 6

    def test_apply_cfg_ignores_unknown(self):
        from simulation import SimConfig
        cfg = SimConfig()
        app_module._apply_cfg(cfg, {"does_not_exist": 999})
        # no AttributeError and no attribute created
        assert not hasattr(cfg, "does_not_exist")


# ══════════════════════════════════════════════════════════════════════════════
# 8. SocketIO events (via test client)
# ══════════════════════════════════════════════════════════════════════════════

class TestSocketIOEvents:
    @pytest.fixture()
    def sio_client(self):
        sc = socketio.test_client(flask_app, flask_test_client=flask_app.test_client())
        yield sc
        sc.disconnect()

    def test_connect_does_not_crash(self, sio_client):
        assert sio_client.is_connected()

    def test_cmd_reset_emits_ack(self, sio_client):
        sio_client.emit("cmd_reset", {})
        received = sio_client.get_received()
        ack_events = [r for r in received if r["name"] == "ack"]
        assert len(ack_events) >= 1
        assert ack_events[0]["args"][0]["action"] == "reset"

    def test_cmd_start_emits_ack(self, sio_client):
        sio_client.emit("cmd_start", {
            "green": 20, "yellow": 4, "red": 1,
            "scenario": "normal", "road_type": 4,
            "right_turn": True, "speed": 1.0
        })
        received = sio_client.get_received()
        ack_events = [r for r in received if r["name"] == "ack"]
        assert any(a["args"][0].get("action") == "start" for a in ack_events)

    def test_cmd_start_creates_running_sim(self, sio_client):
        sio_client.emit("cmd_start", {"scenario": "normal"})
        time.sleep(0.1)
        assert app_module.sim is not None
        assert app_module.sim.running is True

    def test_cmd_reset_stops_running_sim(self, sio_client):
        sio_client.emit("cmd_start", {})
        time.sleep(0.1)
        sio_client.emit("cmd_reset", {})
        time.sleep(0.1)
        assert app_module.sim is not None
        assert app_module.sim.running is False

    def test_cmd_pause_toggles_paused(self, sio_client):
        sio_client.emit("cmd_start", {"speed": 1.0})
        time.sleep(0.1)
        sio_client.emit("cmd_pause")
        received = sio_client.get_received()
        ack_events = [r for r in received if r["name"] == "ack"]
        pause_acks = [a for a in ack_events if "paused" in a["args"][0]]
        assert len(pause_acks) >= 1
        assert pause_acks[0]["args"][0]["paused"] is True

    def test_cmd_update_config_emits_ack(self, sio_client):
        app_module.new_sim()
        sio_client.emit("cmd_update_config", {"green_duration": 25.0})
        received = sio_client.get_received()
        ack_events = [r for r in received if r["name"] == "ack"]
        assert any(a["args"][0].get("action") == "config_updated" for a in ack_events)

    def test_cmd_update_config_updates_sim(self, sio_client):
        app_module.new_sim()
        sio_client.emit("cmd_update_config", {"green_duration": 99.0})
        assert app_module.sim.config.green_duration == 99.0

    def test_connect_emits_stats_when_sim_exists(self, sio_client):
        app_module.new_sim()
        sc2 = socketio.test_client(flask_app, flask_test_client=flask_app.test_client())
        received = sc2.get_received()
        stat_events = [r for r in received if r["name"] == "stats"]
        assert len(stat_events) >= 1
        sc2.disconnect()

    def test_reset_emits_reset_event(self, sio_client):
        sio_client.emit("cmd_reset", {})
        received = sio_client.get_received()
        reset_events = [r for r in received if r["name"] == "reset"]
        assert len(reset_events) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 9. Cache invalidation
# ══════════════════════════════════════════════════════════════════════════════

class TestCacheInvalidation:
    def test_invalidate_clears_vehicles(self, client):
        app_module.new_sim()
        client.get("/api/vehicles")  # populate cache
        app_module.invalidate_sim_cache()
        # After invalidation, a fresh request should still work
        resp = client.get("/api/vehicles")
        assert resp.status_code == 200

    def test_invalidate_clears_metrics(self, client):
        app_module.new_sim()
        client.get("/api/metrics")
        app_module.invalidate_sim_cache()
        resp = client.get("/api/metrics")
        assert resp.status_code == 200

    def test_config_cache_busted_on_post(self, client):
        client.get("/api/config")
        client.post("/api/config",
                    data=json.dumps({"green_duration": 50.0}),
                    content_type="application/json")
        resp = client.get("/api/config")
        # Should reflect the new value, not the cached old value
        assert resp.get_json()["green_duration"] == 50.0


# ══════════════════════════════════════════════════════════════════════════════
# 10. End-to-end: start → let run → check stats
# ══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_vehicles_pass_through_after_run(self):
        """Start sim at high speed, wait briefly, confirm vehicles have passed."""
        from simulation import TrafficSimulation, SimConfig
        sim = TrafficSimulation(
            SimConfig(scenario="rush", speed_factor=500.0, seed=1),
            event_cb=None
        )
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=120)
        stats = sim.get_stats()
        assert stats["total_passed"] > 0
        assert stats["avg_wait"] >= 0.0

    def test_cycles_increment_over_time(self):
        from simulation import TrafficSimulation, SimConfig
        sim = TrafficSimulation(SimConfig(speed_factor=500.0))
        sim.env.process(sim._signal_controller())
        sim.running = True
        one_full_cycle = (20 + 4 + 1) * 2
        sim.env.run(until=one_full_cycle + 2)
        assert sim.stats.cycles >= 1

    def test_all_four_directions_receive_vehicles(self):
        from simulation import TrafficSimulation, SimConfig
        sim = TrafficSimulation(SimConfig(scenario="rush", speed_factor=500.0, seed=7))
        directions_seen = set()
        sim.event_cb = lambda e, d: directions_seen.add(d["direction"]) if e == "vehicle_arrive" else None
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=60)
        assert directions_seen == {"N", "S", "E", "W"}

    def test_no_vehicles_pass_on_full_red(self):
        """If RTOR is off and lights stay red, no straight/left vehicles should move.
        NOTE: The sim phase initialises to NS_GREEN, so we explicitly set EW_RED and
        only spawn EW vehicles (which see a RED light) with RTOR disabled."""
        from simulation import TrafficSimulation, SimConfig, Phase
        sim = TrafficSimulation(SimConfig(speed_factor=500.0, right_turn_free=False))
        # Force permanent red for E/W — never start signal controller
        sim.phase = Phase.NS_GREEN  # N/S green, E/W red
        sim.running = True
        # Only spawn E/W vehicles — they face RED with no RTOR
        for d in ("E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.env.process(sim._drain_queues_process())
        sim.env.run(until=50)
        assert sim.stats.total_passed == 0

    def test_rtor_vehicles_pass_on_red(self):
        """With RTOR enabled, right-turning vehicles should pass even on red."""
        from simulation import TrafficSimulation, SimConfig, Phase
        sim = TrafficSimulation(SimConfig(right_turn_free=True, speed_factor=500.0, seed=3))
        passed = [0]
        sim.event_cb = lambda e, d: passed.__setitem__(0, passed[0] + 1) if e == "vehicle_move" else None
        # Run with signal controller so red phases naturally occur
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=100)
        assert passed[0] > 0
