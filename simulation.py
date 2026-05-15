"""
Traffic Intersection Simulation Engine
Uses SimPy for discrete-event simulation of a 4-way intersection.
"""

import simpy
import random
import threading
import time
from dataclasses import dataclass, field
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
    spawn_offset: float = 0.0
    releasing:   bool  = False

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
            "spawn_offset": self.spawn_offset,
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
        self._lock    = threading.RLock()

        # State
        self.stats    = SimStats()
        self.vehicles: Dict[int, Vehicle] = {}
        self.queues:   Dict[str, List[int]] = {"N":[],"S":[],"E":[],"W":[]}
        self.phase    = Phase.NS_GREEN
        self._next_vid = 1
        self._lane_counters: Dict[str, int] = {"N":0,"S":0,"E":0,"W":0}

        # SimPy resources: per-lane resources for each direction
        self._lane_resources: Dict[str, List[simpy.Resource]] = {
            d: [simpy.Resource(self.env, capacity=1) for _ in range(self._lanes_per_dir())]
            for d in ["N", "S", "E", "W"]
        }

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
        # Right-turn-on-red: specifically restricted to RED (not yellow)
        if turn == Turn.RIGHT.value and self.config.right_turn_free and lc == LightColor.RED:
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
            yield from self._wait_phase(lambda: cfg.green_duration)

            # NS Yellow
            self.phase = Phase.NS_YELLOW
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "yellow", "ew": "red"})
            self._log(f"🟡 N-S YELLOW ({cfg.yellow_duration}s)", "yellow")
            yield from self._wait_phase(lambda: cfg.yellow_duration)

            # All-red clearance
            self.phase = Phase.NS_RED
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red"})
            self._log(f"🔴 ALL RED ({cfg.red_duration}s)", "red")
            yield from self._wait_phase(lambda: cfg.red_duration)

            # EW Green
            self.phase = Phase.EW_GREEN
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "green"})
            self._log(f"🟢 E-W GREEN ({cfg.green_duration}s)", "green")
            yield from self._wait_phase(lambda: cfg.green_duration)

            # EW Yellow
            self.phase = Phase.EW_YELLOW
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "yellow"})
            self._log(f"🟡 E-W YELLOW ({cfg.yellow_duration}s)", "yellow")
            yield from self._wait_phase(lambda: cfg.yellow_duration)

            # All-red clearance
            self.phase = Phase.EW_RED
            self._update_lights()
            self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red"})
            self._log(f"🔴 ALL RED ({cfg.red_duration}s)", "red")
            yield from self._wait_phase(lambda: cfg.red_duration)

            self.stats.cycles += 1

    def _wait_phase(self, duration_fn: Callable[[], float]):
        """Helper to wait for a phase duration, checking periodically for config updates."""
        elapsed = 0.0
        step = 0.5
        while elapsed < duration_fn():
            yield self.env.timeout(min(step, duration_fn() - elapsed))
            elapsed += step

    def _update_lights(self):
        self.stats.phase    = self.phase
        self.stats.ns_light = self._light_for("N")
        self.stats.ew_light = self._light_for("E")

    def _drain_queues_process(self):
        """Continuously attempts to release vehicles from queues when light is green or RTOR is possible."""
        while True:
            for d in ["N", "S", "E", "W"]:
                # Check if ANY vehicle in this direction can move (either Green or RTOR)
                # Note: We call this regardless of light color because RTOR depends on individual vehicle turn.
                self._release_from_queue(d)
            yield self.env.timeout(0.2)

    def _release_from_queue(self, direction: str):
        """Identifies vehicles that can start moving and starts their movement process."""
        with self._lock:
            if not self.queues[direction]:
                return

            lanes = self._lanes_per_dir()
            lane_busy = [False] * lanes
            
            # A lane is busy if a vehicle is already moving or is in the process of starting
            for vid in self.queues[direction]:
                v = self.vehicles.get(vid)
                if v and v.releasing:
                    lane_busy[v.lane_idx] = True
            
            # Scan the queue and start movement for the first available vehicle in each lane
            for vid in self.queues[direction]:
                v = self.vehicles.get(vid)
                if v and not v.releasing and not lane_busy[v.lane_idx]:
                    # Check if this specific vehicle can go (Green or RTOR)
                    if self._can_go(v.direction, v.turn):
                        v.releasing = True
                        lane_busy[v.lane_idx] = True
                        self.env.process(self._move_vehicle(v))
                    else:
                        # If the front vehicle in this lane cannot go, the lane is blocked
                        lane_busy[v.lane_idx] = True

    def _vehicle_process(self, direction: str):
        """Spawns vehicles for a given direction continuously."""
        while True:
            iat = self._arrival_rate()
            yield self.env.timeout(iat)

            with self._lock:
                # All state updates must be atomic to ensure arrival order == queue order
                vid  = self._next_vid; self._next_vid += 1
                turn = random.choice(list(Turn))
                color = random.choice(VEHICLE_COLORS)
                lanes = self._lanes_per_dir()
                
                lane_idx = self._lane_counters[direction] % lanes
                self._lane_counters[direction] += 1

                # Calculate spawn offset (e.g., -250 for N/W, +250 for S/E)
                offset = -250 if direction in ("N", "W") else 250

                v = Vehicle(
                    vid=vid, direction=direction, turn=turn.value,
                    color=color, arrive_time=self.env.now,
                    wait_start=self.env.now, lane_idx=lane_idx,
                    queue_pos=0, # Will be set below
                    spawn_offset=offset
                )

                # Check queue capacity
                if len(self.queues[direction]) >= self._max_queue():
                    self._log(f"🚫 Car #{vid} diverted — {direction} queue full", "red")
                    self._emit("vehicle_diverted", {"vid": vid, "direction": direction})
                    continue

                self.vehicles[vid] = v
                self.queues[direction].append(vid)
                
                # Recalculate all queue positions in this direction
                for pos, qvid in enumerate(self.queues[direction]):
                    if qvid in self.vehicles:
                        self.vehicles[qvid].queue_pos = pos

                self._log(f"🚗 Car #{vid} arrives {direction}→{turn.value}", "gray")
                self._emit("vehicle_arrive", v.to_dict())
                self._emit("vehicle_queued", v.to_dict())
                self._emit("queue_update", {"direction": direction, "ids": list(self.queues[direction])})

    def _move_vehicle(self, v: Vehicle):
        """Process: vehicle waits for resource and moves through intersection."""
        res = self._lane_resources[v.direction][v.lane_idx]
        
        # 1. Wait for lane resource (physical space at the stop line)
        with res.request() as req:
            yield req

            # 2. Check signal compliance (Double-check after potential wait)
            if not self._can_go(v.direction, v.turn):
                v.releasing = False
                return

            # 3. Transition to moving state and remove from queue
            with self._lock:
                if v.vid in self.queues[v.direction]:
                    self.queues[v.direction].remove(v.vid)
                    # Recalculate all queue positions in this direction
                    for pos, qvid in enumerate(self.queues[v.direction]):
                        if qvid in self.vehicles:
                            self.vehicles[qvid].queue_pos = pos
                    
                    self._emit("queue_update", {"direction": v.direction, "ids": list(self.queues[v.direction])})

                v.state    = "moving"
                v.queue_pos = -1
                v.releasing = False
                v.wait_end = self.env.now
                wait       = v.wait_time()
                self.stats.total_wait  += wait
                self.stats.total_passed += 1
                self._emit("vehicle_move", v.to_dict())

            self._log(f"✅ Car #{v.vid} ({v.direction}→{v.turn}) clears — waited {wait:.1f}s", "blue")

            # Travel through intersection
            travel = 2.0 + random.uniform(0.5, 1.5)
            yield self.env.timeout(travel)

            # Exit corridor: ensure vehicle is visually clear before removal
            exit_travel = 1.0 + random.uniform(0.2, 0.4)
            yield self.env.timeout(exit_travel)

            with self._lock:
                v.state = "exited"
                self._emit("vehicle_exit", {"vid": v.vid})
                if v.vid in self.vehicles:
                    del self.vehicles[v.vid]

    def _stats_reporter(self):
        """Emits stats snapshot every 0.5 sim-seconds."""
        while True:
            yield self.env.timeout(0.5)
            with self._lock:
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
        self.env.process(self._drain_queues_process())
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
        self.env.process(self._vehicle_process(direction))

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

    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "paused": self.paused,
                **self.get_stats()
            }

    def get_vehicles(self) -> List[dict]:
        with self._lock:
            return [v.to_dict() for v in self.vehicles.values()]

    def get_stats(self) -> dict:
        with self._lock:
            self.stats.sim_time       = round(self.env.now, 1)
            self.stats.queues         = {d: len(q) for d, q in self.queues.items()}
            self.stats.active_vehicles = len(self.vehicles)
            return self.stats.to_dict()
