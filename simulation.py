"""
Traffic Intersection Simulation Engine
Uses SimPy for discrete-event simulation of a 4-way intersection.
"""

import simpy
import random
import threading
import time
import math
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable
from enum import Enum

# ─── Enums & Constants ────────────────────────────────────────────────────────

class Direction(str, Enum):
    NORTH = "N"
    SOUTH = "S"
    EAST  = "E"
    WEST  = "W"

class Turn(str, Enum):
    STRAIGHT = "straight"
    LEFT     = "left"
    RIGHT    = "right"

class Phase(str, Enum):
    NS_GREEN  = "ns_green"
    NS_YELLOW = "ns_yellow"
    NS_RED    = "ns_red"
    EW_GREEN  = "ew_green"
    EW_YELLOW = "ew_yellow"
    EW_RED    = "ew_red"

class LightColor(str, Enum):
    GREEN  = "green"
    YELLOW = "yellow"
    RED    = "red"

VEHICLE_COLORS = [
    "#E24B4A","#378ADD","#639922","#EF9F27","#D4537E",
    "#7F77DD","#1D9E75","#D85A30","#BA7517","#533AB7",
    "#20B2AA","#FF6347","#4169E1","#32CD32","#FF8C00",
]

SCENARIOS = {
    "normal": {"arrival_base": 4.0,  "label": "Normal Traffic"},
    "rush":   {"arrival_base": 1.4,  "label": "Rush Hour"},
    "low":    {"arrival_base": 9.0,  "label": "Low Traffic"},
}

# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class SimConfig:
    green_duration:  float = 20.0
    yellow_duration: float = 4.0
    red_duration:    float = 1.0
    scenario:        str   = "normal"
    road_type:       int   = 4       # total lanes (2, 4, 6)
    right_turn_free: bool  = True
    speed_factor:    float = 1.0

@dataclass
class Vehicle:
    vid:        int
    direction:  str
    turn:       str
    color:      str
    arrive_time: float
    wait_start:  float = 0.0
    wait_end:    float = 0.0
    state:       str   = "queued"   # queued | moving | exited
    queue_pos:   int   = 0
    lane_idx:    int   = 0

    def wait_time(self) -> float:
        if self.wait_end > 0:
            return round(self.wait_end - self.wait_start, 2)
        return 0.0

    def to_dict(self):
        return {
            "vid": self.vid, "direction": self.direction,
            "turn": self.turn, "color": self.color,
            "arrive_time": round(self.arrive_time, 2),
            "wait_time": self.wait_time(),
            "state": self.state,
            "queue_pos": self.queue_pos,
            "lane_idx": self.lane_idx,
        }

@dataclass
class SimStats:
    total_passed:   int   = 0
    total_wait:     float = 0.0
    cycles:         int   = 0
    sim_time:       float = 0.0
    queues:         Dict  = field(default_factory=lambda: {"N":0,"S":0,"E":0,"W":0})
    active_vehicles: int  = 0
    phase:          str   = Phase.NS_GREEN
    ns_light:       str   = LightColor.GREEN
    ew_light:       str   = LightColor.RED

    @property
    def avg_wait(self) -> float:
        if self.total_passed == 0:
            return 0.0
        return round(self.total_wait / self.total_passed, 2)

    def to_dict(self):
        return {
            "total_passed":   self.total_passed,
            "avg_wait":       self.avg_wait,
            "cycles":         self.cycles,
            "sim_time":       round(self.sim_time, 1),
            "queues":         self.queues,
            "active_vehicles": self.active_vehicles,
            "phase":          self.phase,
            "ns_light":       self.ns_light,
            "ew_light":       self.ew_light,
        }

# ─── Main Simulation Class ────────────────────────────────────────────────────

class TrafficSimulation:
    def __init__(self, config: SimConfig, event_cb: Optional[Callable] = None):
        self.config   = config
        self.event_cb = event_cb  # callback(type, data)

        # SimPy environment runs in its own thread
        self.env      = simpy.Environment()
        self.running  = False
        self.paused   = False
        self._thread  = None
        self._lock    = threading.Lock()

        # State
        self.stats    = SimStats()
        self.vehicles: Dict[int, Vehicle] = {}
        # Use deque for efficient popleft/appendleft operations
        self.queues:   Dict[str, deque] = {"N":deque(),"S":deque(),"E":deque(),"W":deque()}
        self.phase    = Phase.NS_GREEN
        self._next_vid = 1
        self._wait_times: List[float] = []

        # SimPy resources (one per direction for queue discipline)
        self._lane_resources: Dict[str, simpy.Resource] = {}
        # cached turn values to avoid recreating lists
        self._turn_values = tuple(t.value for t in Turn)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lanes_per_dir(self) -> int:
        return self.config.road_type // 2

    def _max_queue(self) -> int:
        return self._lanes_per_dir() * 8

    def _arrival_rate(self) -> float:
        base = SCENARIOS[self.config.scenario]["arrival_base"]
        return base * (0.5 + random.random() * 0.9)

    def _light_for(self, direction: str) -> str:
        ns = direction in ("N", "S")
        if self.phase == Phase.NS_GREEN:
            return LightColor.GREEN if ns else LightColor.RED
        if self.phase == Phase.NS_YELLOW:
            return LightColor.YELLOW if ns else LightColor.RED
        if self.phase == Phase.NS_RED:
            return LightColor.RED
        if self.phase == Phase.EW_GREEN:
            return LightColor.RED if ns else LightColor.GREEN
        if self.phase == Phase.EW_YELLOW:
            return LightColor.RED if ns else LightColor.YELLOW
        if self.phase == Phase.EW_RED:
            return LightColor.RED
        return LightColor.RED

    def _can_go(self, direction: str, turn: str) -> bool:
        lc = self._light_for(direction)
        if lc == LightColor.GREEN:
            return True
        if turn == Turn.RIGHT.value and self.config.right_turn_free:
            return True
        return False

    def _emit(self, etype: str, data: dict):
        if self.event_cb:
            data["sim_time"] = round(self.env.now, 2)
            self.event_cb(etype, data)

    # ── SimPy Processes ───────────────────────────────────────────────────────

    def _signal_controller(self):
        """Main traffic light state machine."""
        cfg = self.config
        while True:
            # NS Green
            self.phase = Phase.NS_GREEN
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "green", "ew": "red"})
            self._log(f"🟢 N-S GREEN ({cfg.green_duration}s)", "green")
            self._release_queues(["N", "S"])
            yield self.env.timeout(cfg.green_duration)

            # NS Yellow
            self.phase = Phase.NS_YELLOW
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "yellow", "ew": "red"})
            self._log(f"🟡 N-S YELLOW ({cfg.yellow_duration}s)", "yellow")
            yield self.env.timeout(cfg.yellow_duration)

            # All-red clearance
            self.phase = Phase.NS_RED
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red"})
            self._log(f"🔴 ALL RED ({cfg.red_duration}s)", "red")
            yield self.env.timeout(cfg.red_duration)

            # EW Green
            self.phase = Phase.EW_GREEN
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "green"})
            self._log(f"🟢 E-W GREEN ({cfg.green_duration}s)", "green")
            self._release_queues(["E", "W"])
            yield self.env.timeout(cfg.green_duration)

            # EW Yellow
            self.phase = Phase.EW_YELLOW
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "yellow"})
            self._log(f"🟡 E-W YELLOW ({cfg.yellow_duration}s)", "yellow")
            yield self.env.timeout(cfg.yellow_duration)

            # All-red clearance
            self.phase = Phase.EW_RED
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red"})
            self._log(f"🔴 ALL RED ({cfg.red_duration}s)", "red")
            yield self.env.timeout(cfg.red_duration)

            self.stats.cycles += 1

    def _update_lights(self):
        self.stats.phase    = self.phase
        self.stats.ns_light = self._light_for("N")
        self.stats.ew_light = self._light_for("E")

    def _release_queues(self, dirs: List[str]):
        """Release waiting vehicles when light goes green."""
        lanes = self._lanes_per_dir()
        for d in dirs:
            batch = min(len(self.queues[d]), lanes * 2)
            # pop left batch times and schedule moves
            for i in range(batch):
                try:
                    vid = self.queues[d].popleft()
                except IndexError:
                    break
                v = self.vehicles.get(vid)
                if v:
                    delay = i * 1.8 + random.uniform(0, 0.4)
                    self.env.process(self._move_vehicle(v, delay, require_green=True))
            # Update queue positions for remaining vehicles
            for pos, vid in enumerate(self.queues[d]):
                if vid in self.vehicles:
                    self.vehicles[vid].queue_pos = pos

    def _vehicle_process(self, direction: str):
        """Spawns vehicles for a given direction continuously."""
        while True:
            iat = self._arrival_rate()
            yield self.env.timeout(iat)

            vid  = self._next_vid; self._next_vid += 1
            turn = random.choice(self._turn_values)
            color = random.choice(VEHICLE_COLORS)
            lanes = self._lanes_per_dir()
            lane_idx = (vid - 1) % lanes

            v = Vehicle(
                vid=vid, direction=direction, turn=turn,
                color=color, arrive_time=self.env.now,
                wait_start=self.env.now, lane_idx=lane_idx,
                queue_pos=len(self.queues[direction]),
            )

            # Check queue capacity
            if len(self.queues[direction]) >= self._max_queue():
                self._log(f"🚫 Car #{vid} diverted — {direction} queue full", "red")
                self._emit("vehicle_diverted", {"vid": vid, "direction": direction})
                continue

            self.vehicles[vid] = v
            self._log(f"🚗 Car #{vid} arrives {direction}→{turn}", "gray")
            self._emit("vehicle_arrive", v.to_dict())

            # Right turn on red: skip queue
            if v.turn == Turn.RIGHT.value and self.config.right_turn_free and self._light_for(direction) != LightColor.GREEN:
                v.wait_end = self.env.now
                self._log(f"↪  Car #{vid} free right turn at {direction}", "blue")
                self.env.process(self._move_vehicle(v, 0))
                continue

            if self._can_go(direction, v.turn) and not self.queues[direction]:
                # Light is green, enter intersection immediately
                self.env.process(self._move_vehicle(v, 0))
            else:
                # Join queue
                self.queues[direction].append(vid)
                v.state = "queued"
                self._emit("vehicle_queued", v.to_dict())

    def _move_vehicle(self, v: Vehicle, delay: float, require_green: bool = False):
        """Process: vehicle moves through intersection."""
        if delay > 0:
            yield self.env.timeout(delay)

        if v.vid not in self.vehicles:
            return
        if require_green and self._light_for(v.direction) != LightColor.GREEN:
            if v.vid not in self.queues[v.direction]:
                self.queues[v.direction].appendleft(v.vid)
            for pos, vid in enumerate(self.queues[v.direction]):
                if vid in self.vehicles:
                    self.vehicles[vid].queue_pos = pos
            v.state = "queued"
            self._emit("vehicle_queued", v.to_dict())
            return

        v.state    = "moving"
        v.wait_end = self.env.now
        wait       = v.wait_time()
        self._wait_times.append(wait)
        self.stats.total_wait  += wait
        self.stats.total_passed += 1

        self._log(f"✅ Car #{v.vid} ({v.direction}→{v.turn}) clears — waited {wait:.1f}s", "blue")
        self._emit("vehicle_move", v.to_dict())

        # Travel through intersection
        travel = 2.5 + random.uniform(0.5, 2.0)
        yield self.env.timeout(travel)

        v.state = "exited"
        self._emit("vehicle_exit", {"vid": v.vid})
        if v.vid in self.vehicles:
            del self.vehicles[v.vid]

    def _stats_reporter(self):
        """Emits stats snapshot every 0.5 sim-seconds."""
        while True:
            yield self.env.timeout(0.5)
            self.stats.sim_time       = self.env.now
            self.stats.queues         = {d: len(q) for d, q in self.queues.items()}
            self.stats.active_vehicles = len(self.vehicles)
            self._emit("stats", self.stats.to_dict())

    def _log(self, msg: str, cls: str = "gray"):
        self._emit("log", {"msg": msg, "cls": cls})

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self.paused  = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        """Run SimPy env in real-time, honouring speed_factor & pause."""
        # Start all processes
        self.env.process(self._signal_controller())
        self.env.process(self._stats_reporter())
        for d in ["N", "S", "E", "W"]:
            offset = random.uniform(0, 1.5)
            self.env.process(self._direction_spawner(d, offset))

        # Step the simulation in small increments
        STEP = 0.1  # sim-seconds per tick
        while self.running:
            if self.paused:
                time.sleep(0.05)
                continue
            wall_step = STEP / max(self.config.speed_factor, 0.1)
            self.env.run(until=self.env.now + STEP)
            time.sleep(wall_step)

    def _direction_spawner(self, direction: str, offset: float):
        yield self.env.timeout(offset)
        yield from self._vehicle_process(direction)

    def pause(self):
        self.paused = not self.paused
        return self.paused

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def update_config(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)

    def get_vehicles(self) -> List[dict]:
        return [v.to_dict() for v in self.vehicles.values()]

    def get_stats(self) -> dict:
        self.stats.sim_time       = round(self.env.now, 1)
        self.stats.queues         = {d: len(q) for d, q in self.queues.items()}
        self.stats.active_vehicles = len(self.vehicles)
        return self.stats.to_dict()
