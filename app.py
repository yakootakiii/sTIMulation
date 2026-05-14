"""
Traffic Simulation — Flask + SocketIO server
"""

import eventlet
# Ensure eventlet monkey-patching runs before other stdlib imports
eventlet.monkey_patch()

import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from simulation import TrafficSimulation, SimConfig

app = Flask(__name__)
app.config["SECRET_KEY"] = "traffic-sim-2024"
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

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


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    if sim:
        return jsonify({"running": sim.running, "paused": sim.paused, **sim.get_stats()})
    return jsonify({"running": False})


@app.route("/api/vehicles")
def vehicles():
    if sim:
        return jsonify(sim.get_vehicles())
    return jsonify([])


# ─── SocketIO events ──────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    if sim:
        emit("stats", sim.get_stats())
        emit("vehicles_snapshot", sim.get_vehicles())


@socketio.on("cmd_start")
def on_start(data=None):
    global sim
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
        label = "paused" if paused else "resumed"
        socketio.emit("log", {"msg": f"⏸ Simulation {label}", "cls": "yellow",
                            "sim_time": sim.env.now})
        emit("ack", {"ok": True, "paused": paused})


@socketio.on("cmd_reset")
def on_reset(data=None):
    global sim
    cfg = SimConfig()
    if data:
        _apply_cfg(cfg, data)
    new_sim(cfg)   # stops old sim, creates new (not started)
    socketio.emit("reset", {})
    socketio.emit("log", {"msg": "↺ Simulation reset", "cls": "red",
                        "sim_time": 0})
    emit("ack", {"ok": True, "action": "reset"})


@socketio.on("cmd_update_config")
def on_update_config(data):
    if sim:
        updates = {}
        for k in ("green_duration","yellow_duration","red_duration",
                "scenario","road_type","right_turn_free","speed_factor"):
            if k in data:
                updates[k] = data[k]
        sim.update_config(**updates)
        emit("ack", {"ok": True, "action": "config_updated"})


def _apply_cfg(cfg: SimConfig, data: dict):
    mapping = {
        "green":        ("green_duration",  float),
        "yellow":       ("yellow_duration", float),
        "red":          ("red_duration",    float),
        "scenario":     ("scenario",        str),
        "road_type":    ("road_type",       int),
        "right_turn":   ("right_turn_free", bool),
        "speed":        ("speed_factor",    float),
    }
    for key, (attr, cast) in mapping.items():
        if key in data:
            setattr(cfg, attr, cast(data[key]))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  Traffic Intersection Simulator")
    print("  ────────────────────────────────")
    print("  Open  http://localhost:5001")
    print("  Press Ctrl+C to stop\n")
    socketio.run(app, host="0.0.0.0", port=5001, debug=False)
