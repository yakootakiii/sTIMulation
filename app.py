"""
Traffic Simulation — Flask + SocketIO server
"""

import eventlet
# Ensure eventlet monkey-patching runs before other stdlib imports
eventlet.monkey_patch()

import threading
import os
import math
import time
from collections import defaultdict, deque
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_caching import Cache
from simulation import TrafficSimulation, SimConfig, SCENARIOS
from cache_config import CACHE_CONFIG, FALLBACK_CONFIG, CACHE_RULES

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config.setdefault("TEMPLATES_AUTO_RELOAD", True)
app.jinja_env.auto_reload = True

_origins = os.environ.get(
    "SOCKETIO_ALLOWED_ORIGINS",
    "http://localhost,http://127.0.0.1,http://localhost:5001,http://127.0.0.1:5001",
)
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
)

ALLOWED_CONFIG_KEYS = {
    "green_duration", "yellow_duration", "red_duration", "scenario",
    "road_type", "right_turn_free", "speed_factor", "seed",
}
START_RESET_KEY_MAP = {
    "green": "green_duration",
    "yellow": "yellow_duration",
    "red": "red_duration",
    "scenario": "scenario",
    "road_type": "road_type",
    "right_turn": "right_turn_free",
    "speed": "speed_factor",
    "seed": "seed",
}
STRUCTURAL_CONFIG_KEYS = {"road_type"}
SOCKET_RATE_LIMIT = {"limit": 20, "window": 10.0}
_socket_events = defaultdict(deque)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'",
    )
    if response.mimetype == "text/html":
        response.headers.setdefault("Cache-Control", "no-store, max-age=0")
        response.headers.setdefault("Pragma", "no-cache")
    return response

@app.route("/assets/<path:filename>")
def asset_file(filename):
    return send_from_directory(os.path.join(app.root_path, "assets"), filename)

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
    cache.delete("config")


def _config_to_dict(cfg: SimConfig) -> dict:
    return {
        "green_duration": cfg.green_duration,
        "yellow_duration": cfg.yellow_duration,
        "red_duration": cfg.red_duration,
        "scenario": cfg.scenario,
        "road_type": cfg.road_type,
        "right_turn_free": cfg.right_turn_free,
        "speed_factor": cfg.speed_factor,
        "seed": cfg.seed,
    }


def _public_config(cfg: SimConfig) -> dict:
    data = _config_to_dict(cfg)
    data.pop("seed", None)
    return data


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _as_finite_float(name: str, value, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid value for '{name}'")
    if not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        raise ValueError(f"'{name}' must be between {minimum} and {maximum}")
    return parsed


def _as_int(name: str, value, *, allowed=None, minimum=None, maximum=None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Invalid value for '{name}'")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid value for '{name}'")
    if allowed is not None and parsed not in allowed:
        raise ValueError(f"'{name}' must be one of {sorted(allowed)}")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"'{name}' must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"'{name}' must be at most {maximum}")
    return parsed


def _as_bool(name: str, value) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"'{name}' must be a boolean")
    return value


def _validate_config_payload(data: dict, *, aliases: dict = None, allow_empty: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object")
    if not data and not allow_empty:
        raise ValueError("Payload cannot be empty")

    key_map = aliases or {k: k for k in ALLOWED_CONFIG_KEYS}
    unexpected = set(data) - set(key_map)
    if unexpected:
        raise ValueError(f"Unexpected configuration key(s): {', '.join(sorted(unexpected))}")

    updates = {}
    for incoming_key, value in data.items():
        key = key_map[incoming_key]
        if key == "green_duration":
            updates[key] = _as_finite_float(key, value, minimum=1.0, maximum=3600.0)
        elif key == "yellow_duration":
            updates[key] = _as_finite_float(key, value, minimum=1.0, maximum=300.0)
        elif key == "red_duration":
            updates[key] = _as_finite_float(key, value, minimum=0.0, maximum=300.0)
        elif key == "speed_factor":
            updates[key] = _as_finite_float(key, value, minimum=0.1, maximum=100.0)
        elif key == "scenario":
            if not isinstance(value, str) or value not in SCENARIOS:
                raise ValueError(f"'scenario' must be one of {sorted(SCENARIOS)}")
            updates[key] = value
        elif key == "road_type":
            updates[key] = _as_int(key, value, allowed={2, 4, 6})
        elif key == "right_turn_free":
            updates[key] = _as_bool(key, value)
        elif key == "seed":
            updates[key] = _as_int(key, value, minimum=0, maximum=2**32 - 1)

    return updates


def _config_with_updates(cfg: SimConfig, updates: dict) -> SimConfig:
    merged = _config_to_dict(cfg)
    merged.update(updates)
    return SimConfig(**merged)


def _apply_updates_to_sim(updates: dict):
    """Apply validated updates, recreating stopped sims for lane-shape changes."""
    global sim
    if not updates:
        return

    if STRUCTURAL_CONFIG_KEYS & updates.keys():
        if sim and sim.running:
            raise ValueError("road_type cannot be changed while the simulation is running")
        sim = new_sim(_config_with_updates(sim.config, updates))
        return

    sim.update_config(**updates)


def _rate_limited(event_name: str) -> bool:
    sid = getattr(request, "sid", request.remote_addr or "anonymous")
    key = (sid, event_name)
    now = time.monotonic()
    events = _socket_events[key]
    while events and now - events[0] > SOCKET_RATE_LIMIT["window"]:
        events.popleft()
    if len(events) >= SOCKET_RATE_LIMIT["limit"]:
        return True
    events.append(now)
    return False


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

        data = _public_config(sim.config)
        cache.set("config", data, timeout=CACHE_RULES["config"])
        return jsonify(data)

    if not request.is_json:
        return _json_error("Content-Type must be application/json", 415)

    data = request.get_json(silent=True)
    try:
        updates = _validate_config_payload(
            data,
            aliases={k: k for k in ALLOWED_CONFIG_KEYS if k != "seed"},
        )
        _apply_updates_to_sim(updates)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    invalidate_sim_cache()
    return jsonify({
        "message": "Configuration updated successfully",
        "config": _public_config(sim.config),
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
    if _rate_limited("cmd_start"):
        emit("ack", {"ok": False, "error": "Rate limit exceeded"})
        return
    invalidate_sim_cache()   # clear stale cache before starting
    try:
        updates = _validate_config_payload(
            data if data is not None else {},
            aliases=START_RESET_KEY_MAP,
            allow_empty=True,
        )
        cfg = _config_with_updates(SimConfig(), updates)
    except ValueError as exc:
        emit("ack", {"ok": False, "error": str(exc)})
        return
    s = new_sim(cfg)
    s.start()
    emit("ack", {"ok": True, "action": "start"})
    socketio.emit("log", {"msg": "▶ Simulation started", "cls": "green",
                          "sim_time": 0})


@socketio.on("cmd_pause")
def on_pause():
    if _rate_limited("cmd_pause"):
        emit("ack", {"ok": False, "error": "Rate limit exceeded"})
        return
    if sim:
        paused = sim.pause()
        invalidate_sim_cache()   # status changed — clear cache
        label = "paused" if paused else "resumed"
        socketio.emit("log", {"msg": f"⏸ Simulation {label}", "cls": "yellow",
                              "sim_time": sim.env.now})
        emit("ack", {"ok": True, "paused": paused})


@socketio.on("cmd_stop")
def on_stop():
    if _rate_limited("cmd_stop"):
        emit("ack", {"ok": False, "error": "Rate limit exceeded"})
        return
    if sim:
        sim.stop()
        invalidate_sim_cache()   # status changed — clear cache
        socketio.emit("log", {"msg": "⏹ Simulation stopped", "cls": "red",
                              "sim_time": sim.env.now})
        emit("ack", {"ok": True, "action": "stop"})


@socketio.on("cmd_reset")
def on_reset(data=None):
    global sim
    if _rate_limited("cmd_reset"):
        emit("ack", {"ok": False, "error": "Rate limit exceeded"})
        return
    invalidate_sim_cache()   # clear all cache on reset
    try:
        updates = _validate_config_payload(
            data if data is not None else {},
            aliases=START_RESET_KEY_MAP,
            allow_empty=True,
        )
        cfg = _config_with_updates(SimConfig(), updates)
    except ValueError as exc:
        emit("ack", {"ok": False, "error": str(exc)})
        return
    new_sim(cfg)
    socketio.emit("reset", {})
    socketio.emit("log", {"msg": "↺ Simulation reset", "cls": "red",
                          "sim_time": 0})
    emit("ack", {"ok": True, "action": "reset"})


@socketio.on("cmd_update_config")
def on_update_config(data):
    if _rate_limited("cmd_update_config"):
        emit("ack", {"ok": False, "error": "Rate limit exceeded"})
        return
    if sim:
        try:
            updates = _validate_config_payload(data if data is not None else {}, allow_empty=True)
            _apply_updates_to_sim(updates)
        except ValueError as exc:
            emit("ack", {"ok": False, "error": str(exc)})
            return
        invalidate_sim_cache()
        emit("ack", {"ok": True, "action": "config_updated"})


def _apply_cfg(cfg: SimConfig, data: dict):
    # Backward-compatible helper for tests and internal callers; socket handlers
    # use strict validation before this point.
    data = {k: v for k, v in (data or {}).items() if k in START_RESET_KEY_MAP}
    updates = _validate_config_payload(
        data,
        aliases=START_RESET_KEY_MAP,
        allow_empty=True,
    )
    for attr, value in updates.items():
        setattr(cfg, attr, value)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("\n  Traffic Intersection Simulator")
    print("  ────────────────────────────────")
    print("  Cache rules:")
    for k, v in CACHE_RULES.items():
        print(f"    {k:<10} {v}s TTL")
    print("  ────────────────────────────────")
    print(f"  Open  http://localhost:{port}")
    print("  Press Ctrl+C to stop\n")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
