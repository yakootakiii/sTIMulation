"""
Traffic Intersection Simulation Engine
Uses SimPy for discrete-event simulation of a 4-way intersection.
"""

import simpy
import random
import threading
import time
import collections
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
    seed:            int   = 42

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
class Pedestrian:
    pid:        int
    direction:  str      # N, S, E, or W (direction of crosswalk)
    cross_dir:  str      # direction crossing (perpendicular to direction)
    arrive_time: float
    state:      str   = "waiting"  # waiting | crossing | exited
    cross_pos:  float = 0.0        # 0-100, position along crosswalk
    
    def to_dict(self):
        return {
            "pid": self.pid, "direction": self.direction,
            "cross_dir": self.cross_dir, "arrive_time": round(self.arrive_time, 2),
            "state": self.state, "cross_pos": round(self.cross_pos, 2),
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
        self.random   = random.Random(config.seed)
        self.running  = False
        self.paused   = False
        self._thread  = None
        self._lock    = threading.RLock()

        # Profiling metrics
        self._metrics = {
            "release_calls": 0,
            "can_go_checks": 0,
        }

        # State
        self.stats    = SimStats()
        self.vehicles: Dict[int, Vehicle] = {}
        self.pedestrians: Dict[int, Pedestrian] = {}
        
        # New: per-lane deques for O(1) access and O(Lanes) releasing logic
        lanes = self._lanes_per_dir()
        self.queues: Dict[str, List[collections.deque]] = {
            d: [collections.deque() for _ in range(lanes)]
            for d in ["N", "S", "E", "W"]
        }

        self.phase    = Phase.NS_GREEN
        self._next_vid = 1
        self._next_pid = 1  # Pedestrian ID counter
        self._lane_counters: Dict[str, int] = {"N":0,"S":0,"E":0,"W":0}

        # SimPy resources: per-lane resources for each direction
        self._lane_resources: Dict[str, List[simpy.Resource]] = {
            d: [simpy.Resource(self.env, capacity=1) for _ in range(lanes)]
            for d in ["N", "S", "E", "W"]
        }
        
        # Intersection occupancy tracking: track which axis is in use (None, 'NS', or 'EW')
        self._intersection_axis = None  # None='free', 'NS'='N/S crossing', 'EW'='E/W crossing'

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lanes_per_dir(self) -> int:
        return self.config.road_type // 2

    def get_metrics(self) -> dict:
        """Returns profiling metrics."""
        with self._lock:
            return {
                "profile": self._metrics,
                "total_vehicles": self.stats.total_passed + len(self.vehicles)
            }

    def _max_queue(self) -> int:
        return self._lanes_per_dir() * 8

    def _arrival_rate(self) -> float:
        base = SCENARIOS[self.config.scenario]["arrival_base"]
        return base * (0.5 + self.random.random() * 0.9)

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
        self._metrics["release_calls"] += 1
        with self._lock:
            # Short-circuit: if the entire direction is red and RTOR is off, skip
            # (Actually RTOR depends on individual vehicle turn, but if all lights are RED and RTOR is off, nothing can move)
            if not self.config.right_turn_free and self._light_for(direction) == LightColor.RED:
                return

            lane_deques = self.queues[direction]
            
            # Scan only the front of each lane deque
            for lane_idx, q in enumerate(lane_deques):
                if not q:
                    continue
                
                vid = q[0]
                v = self.vehicles.get(vid)
                if not v or v.releasing:
                    continue
                
                # Check if this specific vehicle can go (Green or RTOR)
                self._metrics["can_go_checks"] += 1
                if self._can_go(v.direction, v.turn):
                    v.releasing = True
                    self.env.process(self._move_vehicle(v))

    def _vehicle_process(self, direction: str):
        """Spawns vehicles for a given direction continuously."""
        while True:
            iat = self._arrival_rate()
            yield self.env.timeout(iat)

            with self._lock:
                # All state updates must be atomic to ensure arrival order == queue order
                vid  = self._next_vid; self._next_vid += 1
                turn = self.random.choice(list(Turn))
                color = self.random.choice(VEHICLE_COLORS)
                lanes = self._lanes_per_dir()
                
                lane_idx = self._lane_counters[direction] % lanes
                self._lane_counters[direction] += 1

                # Calculate spawn offset (e.g., -250 for N/W, +250 for S/E)
                offset = -250 if direction in ("N", "W") else 250

                q = self.queues[direction][lane_idx]
                
                # Check lane capacity
                if len(q) >= (self._max_queue() // lanes):
                    self._log(f"🚫 Car #{vid} diverted — {direction} lane {lane_idx} full", "red")
                    self._emit("vehicle_diverted", {"vid": vid, "direction": direction})
                    continue

                v = Vehicle(
                    vid=vid, direction=direction, turn=turn.value,
                    color=color, arrive_time=self.env.now,
                    wait_start=self.env.now, lane_idx=lane_idx,
                    queue_pos=len(q),
                    spawn_offset=offset
                )

                self.vehicles[vid] = v
                q.append(vid)
                
                self._log(f"🚗 Car #{vid} arrives {direction}→{turn.value}", "gray")
                self._emit("vehicle_arrive", v.to_dict())
                self._emit("vehicle_queued", v.to_dict())
                
                # Emit flattened list of IDs for the entire direction to keep frontend in sync
                all_ids = []
                for lane_q in self.queues[direction]:
                    all_ids.extend(list(lane_q))
                self._emit("queue_update", {"direction": direction, "ids": all_ids})

    def _move_vehicle(self, v: Vehicle):
        """Process: vehicle waits for resource and moves through intersection."""
        res = self._lane_resources[v.direction][v.lane_idx]
        
        # 1. Wait for lane resource (physical space at the stop line)
        with res.request() as req:
            yield req

            # 2. Strict signal compliance: verify light is still legal
            if not self._can_go(v.direction, v.turn):
                v.releasing = False
                return
            
            # 3. Wait until intersection is clear of cross-traffic
            my_axis = 'NS' if v.direction in ('N', 'S') else 'EW'
            while self._intersection_axis is not None and self._intersection_axis != my_axis:
                yield self.env.timeout(0.05)  # Check every 0.05 sim-seconds
                # Re-check light in case it changed while waiting
                if not self._can_go(v.direction, v.turn):
                    v.releasing = False
                    return

            # 4. Transition to moving state and remove from queue
            with self._lock:
                q = self.queues[v.direction][v.lane_idx]
                if q and q[0] == v.vid:
                    q.popleft()
                    # Recalculate queue positions only for the affected lane
                    for pos, qvid in enumerate(q):
                        if qvid in self.vehicles:
                            self.vehicles[qvid].queue_pos = pos
                    
                    # Emit flattened list of IDs for the entire direction to keep frontend in sync
                    all_ids = []
                    for lane_q in self.queues[v.direction]:
                        all_ids.extend(list(lane_q))
                    self._emit("queue_update", {"direction": v.direction, "ids": all_ids})

                v.state    = "moving"
                v.queue_pos = -1
                v.releasing = False
                v.wait_end = self.env.now
                wait       = v.wait_time()
                self.stats.total_wait  += wait
                self.stats.total_passed += 1
                self._intersection_axis = my_axis  # Mark intersection as occupied by this axis
                self._emit("vehicle_move", v.to_dict())

            self._log(f"✅ Car #{v.vid} ({v.direction}→{v.turn}) clears — waited {wait:.1f}s", "blue")

            # Travel through intersection
            travel = 2.0 + self.random.uniform(0.5, 1.5)
            yield self.env.timeout(travel)

            # Exit corridor: ensure vehicle is visually clear before removal
            exit_travel = 1.0 + self.random.uniform(0.2, 0.4)
            yield self.env.timeout(exit_travel)

            with self._lock:
                v.state = "exited"
                # Only clear intersection if no other vehicles are crossing
                self._check_intersection_clear()
                self._emit("vehicle_exit", {"vid": v.vid})
                if v.vid in self.vehicles:
                    del self.vehicles[v.vid]

    def _check_intersection_clear(self):
        """Check if any vehicles are still crossing; clear intersection if not."""
        # Count moving vehicles
        moving_count = sum(1 for v in self.vehicles.values() if v.state == 'moving')
        if moving_count == 0:
            self._intersection_axis = None
    
    def _pedestrian_process(self, direction: str):
        """Spawns pedestrians for a given crosswalk direction."""
        while True:
            # Pedestrians arrive less frequently than vehicles
            iat = self.random.uniform(3.0, 8.0)
            yield self.env.timeout(iat)

            with self._lock:
                pid = self._next_pid
                self._next_pid += 1
                
                # Pedestrians cross from either left or right (perpendicular to the road)
                cross_dir = self.random.choice(["left", "right"])
                
                ped = Pedestrian(
                    pid=pid,
                    direction=direction,
                    cross_dir=cross_dir,
                    arrive_time=self.env.now,
                    state="waiting"
                )
                
                self.pedestrians[pid] = ped
                self._log(f"👤 Pedestrian #{pid} arrives at {direction} crosswalk", "gray")
                self._emit("pedestrian_arrive", ped.to_dict())
                
                # Start crossing process for this pedestrian
                self.env.process(self._cross_pedestrian(ped))

    def _cross_pedestrian(self, ped: Pedestrian):
        """Pedestrian crossing logic: wait for safe crossing (perpendicular traffic light red)."""
        # Determine which light the pedestrian needs to cross
        # N/S crosswalks cross when E/W traffic is red, E/W crosswalks cross when N/S traffic is red
        can_cross_directions = {
            "N": ("E", "W"),  # N/S crosswalk: cross when E/W red
            "S": ("E", "W"),
            "E": ("N", "S"),  # E/W crosswalk: cross when N/S red
            "W": ("N", "S"),
        }
        
        required_dirs = can_cross_directions.get(ped.direction, ("N", "S"))
        
        # Wait until it's safe to cross
        while True:
            light_safe = all(self._light_for(d) == LightColor.RED for d in required_dirs)
            if light_safe:
                break
            yield self.env.timeout(0.2)  # Check every 0.2 seconds
        
        # Start crossing
        with self._lock:
            ped.state = "crossing"
            self._emit("pedestrian_move", ped.to_dict())
        
        self._log(f"👤 Pedestrian #{ped.pid} crossing {ped.direction} crosswalk", "blue")
        
        # Crossing takes 4-6 seconds
        cross_time = self.random.uniform(4.0, 6.0)
        num_steps = int(cross_time / 0.1)
        
        for i in range(num_steps):
            yield self.env.timeout(0.1)
            with self._lock:
                ped.cross_pos = (i + 1) / num_steps * 100.0
                if ped.pid in self.pedestrians:
                    self._emit("pedestrian_move", ped.to_dict())
        
        # Pedestrian exits
        with self._lock:
            ped.state = "exited"
            self._emit("pedestrian_exit", {"pid": ped.pid})
            if ped.pid in self.pedestrians:
                del self.pedestrians[ped.pid]

    def _stats_reporter(self):
        """Emits stats snapshot every 0.5 sim-seconds."""
        while True:
            yield self.env.timeout(0.5)
            with self._lock:
                self.stats.sim_time       = self.env.now
                self.stats.queues         = {
                    d: sum(len(q) for q in self.queues[d]) 
                    for d in self.queues
                }
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
            offset = self.random.uniform(0, 1.5)
            self.env.process(self._direction_spawner(d, offset))
            # Pedestrian crossing process for each direction
            self.env.process(self._pedestrian_process(d))

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
            self.stats.queues         = {
                d: sum(len(q) for q in self.queues[d]) 
                for d in self.queues
            }
            self.stats.active_vehicles = len(self.vehicles)
            return self.stats.to_dict()
