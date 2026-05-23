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
    NS_LEFT   = "ns_left"
    NS_YELLOW = "ns_yellow"
    NS_RED    = "ns_red"
    EW_GREEN  = "ew_green"
    EW_LEFT   = "ew_left"
    EW_YELLOW = "ew_yellow"
    EW_RED    = "ew_red"
    PED_WALK  = "ped_walk"
    

class LightColor(str, Enum):
    GREEN  = "green"
    YELLOW = "yellow"
    RED    = "red"


# Vehicle finite-state machine
class VehicleState(str, Enum):
    SPAWNING = "spawning"
    DRIVING = "driving"
    FOLLOWING = "following"
    BRAKING = "braking"
    STOPPED_AT_LIGHT = "stopped_at_light"
    YIELDING_TO_PEDESTRIAN = "yielding_to_pedestrian"
    TURNING_LEFT = "turning_left"
    TURNING_RIGHT = "turning_right"
    MERGING = "merging"
    EMERGENCY_STOP = "emergency_stop"
    EXITING = "exiting"


# --- Simple modular managers for deterministic intersection control ---
class IntersectionManager:
    """Simple reservation-based intersection manager.

    Vehicles reserve a sequence of intersection nodes before entering.
    Reservations are exclusive and prevent overlapping paths.
    """
    def __init__(self):
        # node -> vid
        self._reserved: Dict[str, int] = {}
        # crosswalk occupancy
        self._crosswalks: Dict[str, int] = {}

    def reserve_path(self, vid: int, nodes: List[str]) -> bool:
        # atomic check + reserve
        for n in nodes:
            if n in self._reserved:
                return False
            if n in self._crosswalks:
                return False
        for n in nodes:
            self._reserved[n] = vid
        return True

    def release_path(self, vid: int, nodes: List[str]):
        for n in nodes:
            if self._reserved.get(n) == vid:
                del self._reserved[n]

    def reserve_crosswalk(self, pid: int, cw_nodes: List[str]) -> bool:
        for n in cw_nodes:
            if n in self._reserved or n in self._crosswalks:
                return False
        for n in cw_nodes:
            self._crosswalks[n] = pid
        return True

    def release_crosswalk(self, pid: int, cw_nodes: List[str]):
        for n in cw_nodes:
            if self._crosswalks.get(n) == pid:
                del self._crosswalks[n]

    def is_path_clear(self, nodes: List[str]) -> bool:
        return all(n not in self._reserved and n not in self._crosswalks for n in nodes)


class PathfindingManager:
    """Provides abstracted path node lists for simple intersection movements.

    This is intentionally lightweight: nodes are strings representing
    intermediate tiles or entry/exit positions. It enables reservation
    semantics without precise physics.
    """
    def __init__(self, lanes_per_dir: int = 2):
        self.lanes = lanes_per_dir

    def route_nodes(self, direction: str, turn: str, lane_idx: int) -> List[str]:
        # Basic node naming to represent path through intersection
        # Example nodes: 'entry_N_0', 'center_NS', 'exit_S_0'
        nodes = []
        nodes.append(f"entry_{direction}_{lane_idx}")
        # include center tiles depending on movement
        if turn == Turn.STRAIGHT.value:
            nodes.append(f"center_{'NS' if direction in ('N','S') else 'EW'}")
        elif turn == Turn.LEFT.value:
            nodes.append(f"center_left_{direction}")
        else:
            nodes.append(f"center_right_{direction}")
        # exit node based on destination direction
        dest = self._dest_direction(direction, turn)
        nodes.append(f"exit_{dest}_{lane_idx}")
        return nodes

    def crosswalk_nodes(self, direction: str) -> List[str]:
        # crosswalk node naming
        return [f"cross_{direction}_a", f"cross_{direction}_b"]

    def _dest_direction(self, direction: str, turn: str) -> str:
        if turn == Turn.STRAIGHT.value:
            return direction
        if turn == Turn.LEFT.value:
            # map left turn
            return {"N":"W","S":"E","E":"N","W":"S"}[direction]
        # right turn
        return {"N":"E","S":"W","E":"S","W":"N"}[direction]


class CollisionManager:
    """Predictive, reservation-based collision checker.

    Because movement is tile/reservation-driven, collisions are prevented
    by denying overlapping reservations. This manager supplements that
    with simple time-to-collision heuristics for queued vehicles.
    """
    def __init__(self, sim: 'TrafficSimulation'):
        self.sim = sim

    def predict_no_collision(self, v: 'Vehicle', path: List[str]) -> bool:
        # If any node in path is already reserved by another vehicle, reject
        return self.sim.intersection.is_path_clear(path)

VEHICLE_COLORS = [
    "#E24B4A","#378ADD","#639922","#EF9F27","#D4537E",
    "#7F77DD","#1D9E75","#D85A30","#BA7517","#533AB7",
    "#20B2AA","#FF6347","#4169E1","#32CD32","#FF8C00",
]
 
SCENARIOS = {
    # Increased spawn rate: apply half of the rush-hour increase.
    # Rush-hour base changed from 1.4 -> 1.263 (≈ +10.85% spawn rate).
    # Apply half that increase to normal by reducing its base by ~5.43%: 4.0 * (1 - 0.0543) ≈ 3.783.
    "normal": {"arrival_base": 3.783,  "label": "Normal Traffic"},
    # Tuned so expected total input rate across 4 directions ≈ 12,000 veh/hr.
    # _arrival_rate() uses base * U where U ~ Uniform(0.5, 1.4), so E[U] = 0.95.
    # Expected total rate = 4 * 3600 / (base * 0.95). Solve for base:
    # base = 4 * 3600 / (12000 * 0.95) ≈ 1.263.
    "rush":   {"arrival_base": 1.263,  "label": "Rush Hour"},
    "low":    {"arrival_base": 9.0,  "label": "Low Traffic"},
    "emergency": {"arrival_base": 0.7, "label": "Emergency Mode"},
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
    adaptive_control: bool = True
    pedestrian_scramble: bool = True

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
    # Finite state machine state (internal)
    fsm_state:   VehicleState = VehicleState.SPAWNING
    # Kinematic/physical approximations (meters, m/s)
    speed:       float = 0.0
    length:      float = 4.5
    width:       float = 1.8
    queue_pos:   int   = 0
    lane_idx:    int   = 0
    spawn_offset: float = 0.0
    releasing:   bool  = False
    vehicle_type: str = "car"

    def wait_time(self) -> float:
        if self.wait_end > 0:
            return round(self.wait_end - self.wait_start, 2)
        return 0.0

    def to_dict(self):
        return {
            "vid": self.vid, "direction": self.direction,
            "turn": self.turn, "color": self.color,
            "vehicle_type": self.vehicle_type,
            "arrive_time": round(self.arrive_time, 2),
            "wait_time": self.wait_time(),
            "state": self.state,
            "fsm_state": self.fsm_state.value,
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
    sprite_idx: int   = 0
    state:      str   = "waiting"  # waiting | crossing | exited
    cross_pos:  float = 0.0        # 0-100, position along crosswalk
    
    def to_dict(self):
        return {
            "pid": self.pid, "direction": self.direction,
            "cross_dir": self.cross_dir, "arrive_time": round(self.arrive_time, 2),
            "sprite_idx": self.sprite_idx,
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

        # Realistic lane discharge timing: vehicles leave a lane with a small headway.
        self._lane_next_release: Dict[str, List[float]] = {
            d: [0.0 for _ in range(lanes)]
            for d in ["N", "S", "E", "W"]
        }
        self._service_lane_index: Dict[str, int] = {
            d: -1 for d in ["N", "S", "E", "W"]
        }
        self._discharge_headway = 1.6 if self.config.scenario == "rush" else 1.2
        self._moving_vehicle_count = 0
        self._active_approach: Optional[str] = None
        self._phase_mode: str = "through"
        self._pedestrian_walk_active = False
        self._phase_ends_at: float = 0.0
        self._current_vehicle_type: str = "car"
        self._last_served_approach: Optional[str] = None
        self._served_approach_runs: int = 0

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

        # Managers: pathfinding, intersection reservations, collision predictor
        self.intersection = IntersectionManager()
        self.pathfinder = PathfindingManager(lanes)
        self.collision = CollisionManager(self)

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

    def _arrival_rate(self, direction: str) -> float:
        scenario = self.config.scenario
        if scenario == "rush":
            if direction in ("E", "W"):
                return self.random.uniform(0.4, 1.0)
            return self.random.uniform(1.0, 2.2)
        if scenario == "normal":
            return self.random.uniform(1.6, 4.4)
        if scenario == "low":
            return self.random.uniform(5.5, 10.5)
        if scenario == "emergency":
            return self.random.uniform(0.25, 0.7)
        base = SCENARIOS[scenario]["arrival_base"]
        return base * (0.35 + self.random.random() * 0.75)

    def _light_for(self, direction: str) -> str:
        ns = direction in ("N", "S")
        if self.phase in (Phase.NS_GREEN, Phase.NS_LEFT):
            return LightColor.GREEN if ns else LightColor.RED
        if self.phase == Phase.NS_YELLOW:
            return LightColor.YELLOW if ns else LightColor.RED
        if self.phase == Phase.NS_RED:
            return LightColor.RED
        if self.phase in (Phase.EW_GREEN, Phase.EW_LEFT):
            return LightColor.RED if ns else LightColor.GREEN
        if self.phase == Phase.EW_YELLOW:
            return LightColor.RED if ns else LightColor.YELLOW
        if self.phase == Phase.EW_RED:
            return LightColor.RED
        if self.phase == Phase.PED_WALK:
            return LightColor.RED
        return LightColor.RED

    def _can_go(self, direction: str, turn: str) -> bool:
        if getattr(self, "_current_vehicle_type", "car") == "emergency" and not self._pedestrian_walk_active:
            return self._moving_vehicle_count == 0
        lc = self._light_for(direction)
        if lc == LightColor.GREEN:
            if self._phase_mode == "left":
                return turn == Turn.LEFT.value
            if self._phase_mode == "through":
                return turn in (Turn.STRAIGHT.value, Turn.RIGHT.value)
            return True
        # Right-turn-on-red: allow only when the intersection is otherwise clear.
        if turn == Turn.RIGHT.value and self.config.right_turn_free and lc == LightColor.RED and not self._pedestrian_walk_active:
            return self._moving_vehicle_count == 0
        return False

    def _headway_for(self, turn: str) -> float:
        if turn == Turn.LEFT.value:
            return 1.6
        if turn == Turn.RIGHT.value:
            return 1.0
        return self._discharge_headway

    def _travel_duration_for(self, turn: str, vehicle_type: str = "car") -> float:
        base = 2.1 + self.random.uniform(0.3, 0.7)
        if turn == Turn.LEFT.value:
            base = 3.0 + self.random.uniform(0.2, 0.5)
        elif turn == Turn.RIGHT.value:
            base = 1.5 + self.random.uniform(0.2, 0.4)

        type_multiplier = {
            "motorcycle": 0.75,
            "car": 1.0,
            "bus": 1.2,
            "truck": 1.28,
            "emergency": 0.7,
        }.get(vehicle_type, 1.0)
        return base * type_multiplier

    def _vehicle_profile(self, vehicle_type: str) -> dict:
        profiles = {
            "motorcycle": {"length": 2.2, "width": 0.8, "speed": 1.15},
            "car": {"length": 4.5, "width": 1.8, "speed": 1.0},
            "bus": {"length": 12.0, "width": 2.5, "speed": 0.85},
            "truck": {"length": 10.5, "width": 2.4, "speed": 0.82},
            "emergency": {"length": 4.8, "width": 1.9, "speed": 1.35},
        }
        return profiles.get(vehicle_type, profiles["car"])

    def _recompute_queue_positions(self, direction: str):
        all_ids = []
        for lane_q in self.queues[direction]:
            all_ids.extend(list(lane_q))
        self._emit("queue_update", {"direction": direction, "ids": all_ids})

    def _lane_role(self, lane_idx: int) -> str:
        lanes = self._lanes_per_dir()
        if lanes <= 1:
            return "shared"
        if lanes == 2:
            return "through" if lane_idx == 0 else "left"
        if lane_idx == 0:
            return "left"
        if lane_idx == 1:
            return "through"
        return "right"

    def _select_lane_for_vehicle(self, turn: str) -> int:
        lanes = self._lanes_per_dir()
        if lanes <= 1:
            return 0
        if lanes == 2:
            return 1 if turn == Turn.LEFT.value else 0
        if turn == Turn.LEFT.value:
            return 0
        if turn == Turn.RIGHT.value:
            return 2
        return 1

    def _choose_group_order(self) -> List[str]:
        ns_pressure = self._approach_pressure("N") + self._approach_pressure("S")
        ew_pressure = self._approach_pressure("E") + self._approach_pressure("W")
        if ns_pressure > ew_pressure:
            return ["NS", "EW"]
        if ew_pressure > ns_pressure:
            return ["EW", "NS"]
        return ["NS", "EW"] if self.stats.cycles % 2 == 0 else ["EW", "NS"]

    def _approach_pressure(self, direction: str) -> float:
        queue_pressure = sum(len(q) for q in self.queues[direction])
        left_pressure = sum(1 for q in self.vehicles.values() if q.direction == direction and q.turn == Turn.LEFT.value and q.state == "queued")
        return queue_pressure + left_pressure * 1.5

    def _group_pressure(self, group: str) -> float:
        dirs = ["N", "S"] if group == "NS" else ["E", "W"]
        return sum(self._approach_pressure(d) for d in dirs)

    def _choose_active_approach(self, group: str) -> Optional[str]:
        dirs = ["N", "S"] if group == "NS" else ["E", "W"]
        ranked = sorted(dirs, key=lambda d: (self._approach_pressure(d), len(self.queues[d][0]) if self.queues[d] else 0), reverse=True)
        if not ranked or self._approach_pressure(ranked[0]) <= 0:
            return None
        chosen = ranked[0]
        if chosen == self._last_served_approach and self._served_approach_runs >= 2 and len(ranked) > 1 and self._approach_pressure(ranked[1]) > 0:
            chosen = ranked[1]
        return chosen

    def _choose_service_lane(self, direction: str, mode: str) -> int:
        lanes = self._lanes_per_dir()
        if lanes <= 1:
            return 0
        if lanes == 2:
            return 1 if mode == "left" else 0
        if mode == "left":
            return 0
        if mode == "right":
            return 2
        return 1

    def _phase_duration(self, base: float, pressure: float, minimum: float, maximum: float) -> float:
        boosted = base + min(pressure * 0.35, base)
        if self.config.scenario == "low":
            boosted *= 0.75
        elif self.config.scenario == "rush":
            boosted *= 1.25
        return max(minimum, min(boosted, maximum))

    def _pedestrian_duration(self) -> float:
        max_walk = 0.0
        for ped in self.pedestrians.values():
            if ped.state == "waiting":
                if self._lanes_per_dir() <= 1:
                    walk = self.random.uniform(4.0, 5.0)
                elif self._lanes_per_dir() == 2:
                    walk = self.random.uniform(4.5, 5.8)
                else:
                    walk = self.random.uniform(5.2, 7.0)
                max_walk = max(max_walk, walk)
        return max(4.0, max_walk + 0.4)

    def _can_release_lane(self, direction: str, lane_idx: int) -> bool:
        return lane_idx == self._service_lane_index[direction] and self.env.now >= self._lane_next_release[direction][lane_idx]

    def _rotate_service_lane(self, direction: str):
        lanes = self._lanes_per_dir()
        if lanes <= 0:
            self._service_lane_index[direction] = 0
            return
        self._service_lane_index[direction] = (self._service_lane_index[direction] + 1) % lanes

    def _dispatch_vehicle(self, v: Vehicle, lane_idx: int):
        v.state = "moving"
        v.fsm_state = VehicleState.DRIVING if v.turn == Turn.STRAIGHT.value else (
            VehicleState.TURNING_LEFT if v.turn == Turn.LEFT.value else VehicleState.TURNING_RIGHT)
        v.queue_pos = -1
        v.releasing = False
        v.wait_end = self.env.now
        self._moving_vehicle_count += 1
        self._lane_next_release[v.direction][lane_idx] = self.env.now + self._headway_for(v.turn)
        # Emit move without relying on wait_time here; analytics uses the exit event.
        self._emit("vehicle_move", v.to_dict())

    def _emit(self, etype: str, data: dict):
        if self.event_cb:
            data["sim_time"] = round(self.env.now, 2)
            self.event_cb(etype, data)

    # ── SimPy Processes ───────────────────────────────────────────────────────

    def _signal_controller(self):
        """Adaptive, phase-based traffic controller."""
        cfg = self.config
        while True:
            vehicle_demand = any(self._group_pressure(group) > 0 for group in ("NS", "EW"))
            pedestrian_demand = any(p.state == "waiting" for p in self.pedestrians.values())

            if not vehicle_demand and not pedestrian_demand:
                yield self.env.timeout(0.2)
                continue

            served_cycle = False
            for group in self._choose_group_order():
                if self._group_pressure(group) <= 0 and not pedestrian_demand:
                    continue

                active = self._choose_active_approach(group)
                if active is None:
                    continue
                served_cycle = True

                # Through / straight service
                self._active_approach = active
                if self._last_served_approach == active:
                    self._served_approach_runs += 1
                else:
                    self._last_served_approach = active
                    self._served_approach_runs = 1
                self._phase_mode = "through"
                self._service_lane_index[active] = self._choose_service_lane(active, "through")
                self.phase = Phase.NS_GREEN if group == "NS" else Phase.EW_GREEN
                self._update_lights()
                max_green = 28.0 if self.config.scenario == "rush" else 45.0
                green_duration = self._phase_duration(cfg.green_duration, self._approach_pressure(active), 4.0, max_green)
                self._emit("light_change", {"phase": self.phase, "ns": self.stats.ns_light.value, "ew": self.stats.ew_light.value, "active_approach": active, "mode": "through"})
                self._log(f"🟢 {active} THROUGH GREEN ({green_duration:.1f}s)", "green")
                self._phase_ends_at = self.env.now + green_duration
                yield from self._wait_phase(lambda: green_duration)

                # Protected left-turn phase if there is left demand on the active approach
                left_lane = self._choose_service_lane(active, "left")
                left_demand = any(v.direction == active and v.turn == Turn.LEFT.value and v.state == "queued" for v in self.vehicles.values())
                if left_demand and self._lanes_per_dir() > 1:
                    self._phase_mode = "left"
                    self._service_lane_index[active] = left_lane
                    self.phase = Phase.NS_LEFT if group == "NS" else Phase.EW_LEFT
                    self._update_lights()
                    left_duration = self._phase_duration(max(cfg.yellow_duration, 3.0), self._approach_pressure(active) * 0.6, 3.0, 12.0)
                    self._emit("light_change", {"phase": self.phase, "ns": self.stats.ns_light.value, "ew": self.stats.ew_light.value, "active_approach": active, "mode": "left"})
                    self._log(f"⬅️ {active} LEFT ARROW ({left_duration:.1f}s)", "blue")
                    self._phase_ends_at = self.env.now + left_duration
                    yield from self._wait_phase(lambda: left_duration)

                # Yellow transition and all-red clearance
                self.phase = Phase.NS_YELLOW if group == "NS" else Phase.EW_YELLOW
                self._phase_mode = "yellow"
                self._update_lights()
                self._emit("light_change", {"phase": self.phase, "ns": self.stats.ns_light.value, "ew": self.stats.ew_light.value, "active_approach": active, "mode": "yellow"})
                self._log(f"🟡 {active} YELLOW ({cfg.yellow_duration}s)", "yellow")
                self._phase_ends_at = self.env.now + cfg.yellow_duration
                yield from self._wait_phase(lambda: cfg.yellow_duration)

                self.phase = Phase.NS_RED if group == "NS" else Phase.EW_RED
                self._phase_mode = "all_red"
                self._update_lights()
                self._emit("light_change", {"phase": self.phase, "ns": self.stats.ns_light.value, "ew": self.stats.ew_light.value, "active_approach": active, "mode": "all_red"})
                self._log(f"🔴 ALL RED ({cfg.red_duration}s)", "red")
                self._phase_ends_at = self.env.now + cfg.red_duration
                yield from self._wait_phase(lambda: cfg.red_duration)
                self._service_lane_index[active] = -1

                # Pedestrian scramble / walk phase if anyone is waiting
                if self.config.pedestrian_scramble and any(p.state == "waiting" for p in self.pedestrians.values()):
                    self.phase = Phase.PED_WALK
                    self._phase_mode = "ped"
                    self._pedestrian_walk_active = True
                    self._active_approach = None
                    self._update_lights()
                    ped_duration = self._pedestrian_duration()
                    self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red", "mode": "ped"})
                    self._log(f"🚶 PEDESTRIAN WALK ({ped_duration:.1f}s)", "green")
                    self._phase_ends_at = self.env.now + ped_duration
                    # Release all waiting pedestrians to start crossing simultaneously
                    self._release_all_pedestrians()
                    yield from self._wait_phase(lambda: ped_duration)
                    self._pedestrian_walk_active = False
                    self._phase_mode = "through"

            if not served_cycle and pedestrian_demand and self.config.pedestrian_scramble:
                self.phase = Phase.PED_WALK
                self._phase_mode = "ped"
                self._pedestrian_walk_active = True
                self._active_approach = None
                self._update_lights()
                ped_duration = self._pedestrian_duration()
                self._emit("light_change", {"phase": self.phase, "ns": "red", "ew": "red", "mode": "ped"})
                self._log(f"🚶 PEDESTRIAN WALK ({ped_duration:.1f}s)", "green")
                self._phase_ends_at = self.env.now + ped_duration
                self._release_all_pedestrians()
                yield from self._wait_phase(lambda: ped_duration)
                self._pedestrian_walk_active = False
                self._phase_mode = "through"

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

    def _time_until_direction_green(self, direction: str) -> float:
        """Estimate the time until the next green begins for a given direction."""
        if self.phase in (Phase.PED_WALK,):
            return max(0.0, self._phase_ends_at - self.env.now)

        cfg = self.config
        phase_order = [Phase.NS_GREEN, Phase.NS_LEFT, Phase.NS_YELLOW, Phase.NS_RED, Phase.EW_GREEN, Phase.EW_LEFT, Phase.EW_YELLOW, Phase.EW_RED]
        phase_durations = {
            Phase.NS_GREEN: cfg.green_duration,
            Phase.NS_LEFT: max(3.0, cfg.yellow_duration),
            Phase.NS_YELLOW: cfg.yellow_duration,
            Phase.NS_RED: cfg.red_duration,
            Phase.EW_GREEN: cfg.green_duration,
            Phase.EW_LEFT: max(3.0, cfg.yellow_duration),
            Phase.EW_YELLOW: cfg.yellow_duration,
            Phase.EW_RED: cfg.red_duration,
        }

        target_green = Phase.NS_GREEN if direction in ("N", "S") else Phase.EW_GREEN
        if self.phase in (target_green, Phase.NS_LEFT, Phase.EW_LEFT):
            return max(0.0, self._phase_ends_at - self.env.now)

        elapsed = 0.0
        try:
            current_idx = phase_order.index(self.phase)
        except ValueError:
            return cfg.red_duration

        idx = current_idx
        for _ in range(len(phase_order) + 1):
            current_phase = phase_order[idx]
            elapsed += phase_durations[current_phase]
            idx = (idx + 1) % len(phase_order)
            if phase_order[idx] == target_green:
                break
        return elapsed

    def _drain_queues_process(self):
        """Continuously attempts to release vehicles from queues when light is green or RTOR is possible."""
        while True:
            for d in ["N", "S", "E", "W"]:
                # Check if ANY vehicle in this direction can move (either Green or RTOR)
                # Note: We call this regardless of light color because RTOR depends on individual vehicle turn.
                self._release_from_queue(d)
            yield self.env.timeout(0.05)

    def _release_from_queue(self, direction: str):
        """Identifies vehicles that can start moving and starts their movement process."""
        self._metrics["release_calls"] += 1
        with self._lock:
            if self._active_approach != direction or self._phase_mode == "ped":
                return

            lane_idx = self._service_lane_index.get(direction, -1)
            if lane_idx < 0 or lane_idx >= len(self.queues[direction]):
                return

            q = self.queues[direction][lane_idx]
            if not q:
                return

            vid = q[0]
            v = self.vehicles.get(vid)
            if not v or v.releasing:
                return
            if not self._can_release_lane(direction, lane_idx):
                return

            self._current_vehicle_type = v.vehicle_type
            self._metrics["can_go_checks"] += 1
            if self._can_go(v.direction, v.turn):
                q.popleft()
                for pos, qvid in enumerate(q):
                    if qvid in self.vehicles:
                        self.vehicles[qvid].queue_pos = pos
                self._recompute_queue_positions(direction)

                self._dispatch_vehicle(v, lane_idx)
                self.env.process(self._move_vehicle(v, lane_idx))

    def _vehicle_process(self, direction: str):
        """Spawns vehicles for a given direction continuously with lane assignment discipline."""
        while True:
            iat = self._arrival_rate(direction)
            yield self.env.timeout(iat)

            with self._lock:
                vid  = self._next_vid; self._next_vid += 1
                turn = self.random.choice(list(Turn))
                color = self.random.choice(VEHICLE_COLORS)
                vehicle_type = self.random.choices(
                    ["car", "bus", "truck", "motorcycle", "emergency"],
                    weights=[70, 8, 7, 5, 1] if self.config.scenario == "low" else ([70, 10, 10, 9, 1] if self.config.scenario == "rush" else ([68, 8, 8, 6, 10] if self.config.scenario == "emergency" else [78, 8, 7, 6, 1])),
                    k=1,
                )[0]
                profile = self._vehicle_profile(vehicle_type)
                lanes = self._lanes_per_dir()
                
                # Lane selection follows turn behavior and road configuration.
                lane_idx = self._select_lane_for_vehicle(turn.value)
                if lanes == 2 and turn == Turn.LEFT.value:
                    lane_idx = 1
                if lanes == 2 and turn != Turn.LEFT.value:
                    lane_idx = 0
                
                self._lane_counters[direction] += 1

                # Calculate spawn offset (e.g., -250 for N/W, +250 for S/E)
                offset = -250 if direction in ("N", "W") else 250

                q = self.queues[direction][lane_idx]
                
                # Check lane capacity for this specific lane
                if len(q) >= (self._max_queue() // lanes):
                    self._log(f"🚫 Car #{vid} diverted — {direction} lane {lane_idx} full", "red")
                    self._emit("vehicle_diverted", {"vid": vid, "direction": direction})
                    continue

                # Global spawn throttling if congestion is high
                total_queued = sum(sum(len(lq) for lq in self.queues[d]) for d in self.queues)
                if total_queued > (self._max_queue() * 3):
                    # skip spawning to reduce congestion
                    continue

                v = Vehicle(
                    vid=vid, direction=direction, turn=turn.value,
                    color=color, arrive_time=self.env.now,
                    wait_start=self.env.now, lane_idx=lane_idx,
                    queue_pos=len(q),
                    speed=profile["speed"],
                    spawn_offset=offset,
                    length=profile["length"],
                    width=profile["width"],
                    vehicle_type=vehicle_type,
                )

                self.vehicles[vid] = v
                q.append(vid)
                
                self._log(f"🚗 Car #{vid} arrives {direction}→{turn.value} assigned to Lane {lane_idx}", "gray")
                self._emit("vehicle_arrive", v.to_dict())
                self._emit("vehicle_queued", v.to_dict())
                
                all_ids = []
                for lane_q in self.queues[direction]:
                    all_ids.extend(list(lane_q))
                self._emit("queue_update", {"direction": direction, "ids": all_ids})

    def _move_vehicle(self, v: Vehicle, lane_idx: int):
        """Process: vehicle leaves the queue, traverses the intersection, and exits."""
        wait = v.wait_time()
        self._log(f"✅ Car #{v.vid} ({v.direction}→{v.turn}) departs after waiting {wait:.1f}s", "blue")

        travel = self._travel_duration_for(v.turn, v.vehicle_type)
        yield self.env.timeout(travel)

        exit_travel = 0.8 + self.random.uniform(0.1, 0.3)
        yield self.env.timeout(exit_travel)

        with self._lock:
            v.state = "exited"
            v.fsm_state = VehicleState.EXITING
            self._moving_vehicle_count = max(0, self._moving_vehicle_count - 1)
            self.stats.total_wait += wait
            self.stats.total_passed += 1
            # Re-emit vehicle_move with accurate wait_time for analytics
            payload = v.to_dict()
            payload["wait_time"] = wait
            self._emit("vehicle_move", payload)
            self._emit("vehicle_exit", {"vid": v.vid})
            if v.vid in self.vehicles:
                del self.vehicles[v.vid]

    def _check_intersection_clear(self):
        """Check if any vehicles are still crossing; clear intersection if not."""
        return self._moving_vehicle_count == 0
    
    def _pedestrian_process(self, direction: str):
        """Spawns pedestrians for a given crosswalk direction."""
        while True:
            # Pedestrians arrive less frequently than vehicles
            iat = self.random.uniform(3.0, 8.0)
            yield self.env.timeout(iat)

            with self._lock:
                # Throttle spawning if too many pedestrians for this crosswalk
                existing = sum(1 for p in self.pedestrians.values() if p.direction == direction)
                if existing >= 6:
                    continue

                pid = self._next_pid
                self._next_pid += 1
                
                # Pedestrians cross from either left or right (perpendicular to the road)
                cross_dir = self.random.choice(["left", "right"])
                
                ped = Pedestrian(
                    pid=pid,
                    direction=direction,
                    cross_dir=cross_dir,
                    arrive_time=self.env.now,
                    sprite_idx=self.random.randrange(10),
                    state="waiting"
                )
                
                self.pedestrians[pid] = ped
                self._log(f"👤 Pedestrian #{pid} arrives at {direction} crosswalk", "gray")
                self._emit("pedestrian_arrive", ped.to_dict())
                
                # Do not start an individual waiting process; controller will release pedestrians
                # when the pedestrian walk phase begins.

    def _cross_pedestrian(self, ped: Pedestrian):
        """
        Pedestrian crossing logic: Wait until their parallel traffic light is green 
        AND no conflicting vehicles from the perpendicular axis are blocking the box.
        """
        # CORRECTED MAPPING: 
        # Pedestrians walking along the E/W crosswalks move WITH E/W traffic.
        traffic_lights_to_check = {
            "N": ("E", "W"),  # E crosswalk obeys E/W lights
            "S": ("E", "W"),  # W crosswalk obeys E/W lights
            "E": ("N", "S"),  # N crosswalk obeys N/S lights
            "W": ("N", "S"),  # S crosswalk obeys N/S lights
        }
        
        required_dirs = traffic_lights_to_check.get(ped.direction, ("N", "S"))
        crossing_time = self.random.uniform(4.2, 5.8)
        safety_buffer = 0.5
        # This method is kept for backward compatibility but in the new flow the
        # controller will call `_perform_pedestrian_crossing` directly when the
        # pedestrian walk phase begins. We delegate to that implementation here.
        yield from self._perform_pedestrian_crossing(ped)

    def _perform_pedestrian_crossing(self, ped: Pedestrian):
        """Advance a pedestrian across the crosswalk (no waiting)."""
        crossing_time = self.random.uniform(4.2, 5.8)
        safety_buffer = 0.5

        with self._lock:
            if ped.state != "crossing":
                ped.state = "crossing"
                self._emit("pedestrian_move", ped.to_dict())

        self._log(f"👤 Pedestrian #{ped.pid} crossing {ped.direction} crosswalk safely", "blue")

        num_steps = max(1, int(crossing_time / 0.1))
        start_pos = 0.0 if ped.cross_dir == "left" else 100.0
        end_pos = 100.0 if ped.cross_dir == "left" else 0.0
        for i in range(num_steps):
            yield self.env.timeout(0.1)
            with self._lock:
                # If the pedestrian record was removed (e.g., reset/restart), abort.
                if ped.pid not in self.pedestrians:
                    return
                progress = (i + 1) / num_steps
                ped.cross_pos = start_pos + (end_pos - start_pos) * progress
                self._emit("pedestrian_move", ped.to_dict())

        with self._lock:
            ped.state = "exited"
            self._emit("pedestrian_exit", {"pid": ped.pid})
            # release crosswalk reservation if held and remove pedestrian record
            try:
                cw = self.pathfinder.crosswalk_nodes(ped.direction)
                self.intersection.release_crosswalk(ped.pid, cw)
            except Exception:
                pass
            if ped.pid in self.pedestrians:
                del self.pedestrians[ped.pid]

    def _release_all_pedestrians(self):
        """Start crossing for all waiting pedestrians at once."""
        with self._lock:
            waiting = [p for p in list(self.pedestrians.values()) if p.state == "waiting"]
        for ped in waiting:
            # attempt to reserve crosswalk (best-effort)
            try:
                cw = self.pathfinder.crosswalk_nodes(ped.direction)
                _ = self.intersection.reserve_crosswalk(ped.pid, cw)
            except Exception:
                pass
            # mark as crossing and start the crossing worker
            with self._lock:
                ped.state = "crossing"
                self._emit("pedestrian_move", ped.to_dict())
            self.env.process(self._perform_pedestrian_crossing(ped))

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
            offset = self.random.uniform(0, 0.4)
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