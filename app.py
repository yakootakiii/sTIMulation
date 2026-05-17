"""
Traffic Simulation — Flask + SocketIO server
"""

import eventlet
# Ensure eventlet monkey-patching runs before other stdlib imports
eventlet.monkey_patch()

import threading
import os
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_caching import Cache
from simulation import TrafficSimulation, SimConfig
from cache_config import CACHE_CONFIG, FALLBACK_CONFIG, CACHE_RULES

app = Flask(__name__)
app.config["SECRET_KEY"] = "traffic-sim-2024"
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

# ─── Cache setup ──────────────────────────────────────────────────────────────
try:
    cache = Cache(app, config=CACHE_CONFIG)
    cache.get("ping")   # test connection
    print("  Cache: Redis connected ✓")
except Exception:
    print("  Cache: Redis unavailable, falling back to SimpleCache")
    cache = Cache(app, config=FALLBACK_CONFIG)

# ─── Global simulation instance ───────────────────────────────────────────────
sim: TrafficSimulation = None
sim_lock = threading.Lock()


def make_event_cb():
    def cb(etype: str, data: dict):
        socketio.emit(etype, data)
    return cb


def new_sim(config: SimConfig = None) -> TrafficSimulation:
    global sim
    with sim_lock:
        if sim and sim.running:
            sim.stop()
        cfg = config or SimConfig()
        s = TrafficSimulation(cfg, event_cb=make_event_cb())
        sim = s
    return s


def invalidate_sim_cache():
    """Clear all simulation-related cache keys on state changes."""
    cache.delete("vehicles")
    cache.delete("metrics")
    cache.delete("status")


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


@app.route("/api/status")
def status():
    cached = cache.get("status")
    if cached is not None:
        return jsonify(cached)

    data = sim.get_status() if sim else {"running": False}
    cache.set("status", data, timeout=CACHE_RULES["status"])
    return jsonify(data)


@app.route("/api/vehicles")
def vehicles():
    cached = cache.get("vehicles")
    if cached is not None:
        return jsonify(cached)

    data = sim.get_vehicles() if sim else []
    cache.set("vehicles", data, timeout=CACHE_RULES["vehicles"])
    return jsonify(data)


@app.route("/api/config", methods=["GET", "POST"])
def config_endpoint():
    """Get or update the simulation configuration."""
    global sim

    if sim is None:
        sim = new_sim(SimConfig())

    if request.method == "GET":
        cached = cache.get("config")
        if cached is not None:
            return jsonify(cached)

        data = {
            "green_duration":  sim.config.green_duration,
            "yellow_duration": sim.config.yellow_duration,
            "red_duration":    sim.config.red_duration,
            "scenario":        sim.config.scenario,
            "road_type":       sim.config.road_type,
            "right_turn_free": sim.config.right_turn_free,
            "speed_factor":    sim.config.speed_factor,
        }
        cache.set("config", data, timeout=CACHE_RULES["config"])
        return jsonify(data)

    # POST: update config — invalidate config cache
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "Payload cannot be empty"}), 400

    allowed = {
        "green_duration":  float,
        "yellow_duration": float,
        "red_duration":    float,
        "scenario":        str,
        "road_type":       int,
        "right_turn_free": bool,
        "speed_factor":    float,
    }

    updates = {}
    for k, cast in allowed.items():
        if k in data:
            try:
                updates[k] = cast(data[k])
            except (TypeError, ValueError):
                return jsonify({"error": f"Invalid value for '{k}'"}), 400

    sim.update_config(**updates)
    cache.delete("config")   # invalidate stale config cache

    return jsonify({
        "message": "Configuration updated successfully",
        "config": {
            "green_duration":  sim.config.green_duration,
            "yellow_duration": sim.config.yellow_duration,
            "red_duration":    sim.config.red_duration,
            "scenario":        sim.config.scenario,
            "road_type":       sim.config.road_type,
            "right_turn_free": sim.config.right_turn_free,
            "speed_factor":    sim.config.speed_factor,
        },
    })


@app.route("/api/metrics")
def metrics_endpoint():
    """Return aggregated metrics/stats snapshot."""
    if sim is None:
        return jsonify({"error": "simulation not started"}), 400

    cached = cache.get("metrics")
    if cached is not None:
        return jsonify(cached)

    data = sim.get_stats()
    cache.set("metrics", data, timeout=CACHE_RULES["metrics"])
    return jsonify(data)


# ─── SocketIO events ──────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    if sim:
        stats = sim.get_status()
        emit("stats", stats)
        emit("vehicles_snapshot", sim.get_vehicles())


@socketio.on("cmd_start")
def on_start(data=None):
    global sim
    invalidate_sim_cache()   # clear stale cache before starting
    cfg = SimConfig()
    if data:
        _apply_cfg(cfg, data)
    s = new_sim(cfg)
    s.start()
    emit("ack", {"ok": True, "action": "start"})
    socketio.emit("log", {"msg": "▶ Simulation started", "cls": "green",
                          "sim_time": 0})


@socketio.on("cmd_pause")
def on_pause():
    if sim:
        paused = sim.pause()
        invalidate_sim_cache()   # status changed — clear cache
        label = "paused" if paused else "resumed"
        socketio.emit("log", {"msg": f"⏸ Simulation {label}", "cls": "yellow",
                              "sim_time": sim.env.now})
        emit("ack", {"ok": True, "paused": paused})


@socketio.on("cmd_reset")
def on_reset(data=None):
    global sim
    invalidate_sim_cache()   # clear all cache on reset
    cfg = SimConfig()
    if data:
        _apply_cfg(cfg, data)
    new_sim(cfg)
    socketio.emit("reset", {})
    socketio.emit("log", {"msg": "↺ Simulation reset", "cls": "red",
                          "sim_time": 0})
    emit("ack", {"ok": True, "action": "reset"})


@socketio.on("cmd_update_config")
def on_update_config(data):
    if sim:
        updates = {}
        for k in ("green_duration", "yellow_duration", "red_duration",
                  "scenario", "road_type", "right_turn_free", "speed_factor", "seed"):
            if k in data:
                updates[k] = data[k]
        sim.update_config(**updates)
        cache.delete("config")   # invalidate config cache on update
        emit("ack", {"ok": True, "action": "config_updated"})


def _apply_cfg(cfg: SimConfig, data: dict):
    mapping = {
        "green":      ("green_duration",  float),
        "yellow":     ("yellow_duration", float),
        "red":        ("red_duration",    float),
        "scenario":   ("scenario",        str),
        "road_type":  ("road_type",       int),
        "right_turn": ("right_turn_free", bool),
        "speed":      ("speed_factor",    float),
    }
    for key, (attr, cast) in mapping.items():
        if key in data:
            setattr(cfg, attr, cast(data[key]))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print("\n  Traffic Intersection Simulator")
    print("  ────────────────────────────────")
    print("  Cache rules:")
    for k, v in CACHE_RULES.items():
        print(f"    {k:<10} {v}s TTL")
    print("  ────────────────────────────────")
    print(f"  Worker running on port {port}")
    print("  Open  http://localhost")
    print("  Press Ctrl+C to stop\n")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)