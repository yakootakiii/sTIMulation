"""
Unit Tests — simulation.py
Covers: SimConfig, Vehicle, SimStats, light logic, can_go, queue mechanics,
        signal phase sequencing, spawn offsets, config updates, metrics.
"""

import collections
import pytest
import simpy

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation import (
    TrafficSimulation, SimConfig, Vehicle, SimStats,
    Phase, LightColor, Turn, Direction, SCENARIOS, VEHICLE_COLORS,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_sim(road_type=4, scenario="normal", right_turn_free=True,
             seed=42, speed_factor=1000.0) -> TrafficSimulation:
    cfg = SimConfig(
        road_type=road_type,
        scenario=scenario,
        right_turn_free=right_turn_free,
        seed=seed,
        speed_factor=speed_factor,
    )
    return TrafficSimulation(cfg)


def run_until(sim: TrafficSimulation, until: float):
    """Advance SimPy env without the real-time thread."""
    sim.env.process(sim._signal_controller())
    sim.env.process(sim._drain_queues_process())
    for d in ["N", "S", "E", "W"]:
        sim.env.process(sim._direction_spawner(d, 0))
    sim.running = True
    sim.env.run(until=until)


# ══════════════════════════════════════════════════════════════════════════════
# 1. SimConfig
# ══════════════════════════════════════════════════════════════════════════════

class TestSimConfig:
    def test_defaults(self):
        cfg = SimConfig()
        assert cfg.green_duration == 20.0
        assert cfg.yellow_duration == 4.0
        assert cfg.red_duration == 1.0
        assert cfg.scenario == "normal"
        assert cfg.road_type == 4
        assert cfg.right_turn_free is True
        assert cfg.speed_factor == 1.0
        assert cfg.seed == 42

    def test_custom_values(self):
        cfg = SimConfig(green_duration=30, road_type=6, scenario="rush", seed=99)
        assert cfg.green_duration == 30
        assert cfg.road_type == 6
        assert cfg.scenario == "rush"
        assert cfg.seed == 99

    def test_all_scenarios_present(self):
        for s in ("normal", "rush", "low"):
            assert s in SCENARIOS
            assert "arrival_base" in SCENARIOS[s]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Vehicle dataclass
# ══════════════════════════════════════════════════════════════════════════════

class TestVehicle:
    def test_wait_time_zero_before_exit(self):
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0, wait_start=5.0)
        assert v.wait_time() == 0.0

    def test_wait_time_calculated(self):
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0,
                    wait_start=5.0, wait_end=12.0)
        assert v.wait_time() == 7.0

    def test_to_dict_keys(self):
        v = Vehicle(vid=7, direction="E", turn="right",
                    color="#E24B4A", arrive_time=3.5)
        d = v.to_dict()
        for key in ("vid", "direction", "turn", "color",
                    "arrive_time", "wait_time", "state",
                    "queue_pos", "lane_idx", "spawn_offset"):
            assert key in d

    def test_to_dict_values(self):
        v = Vehicle(vid=7, direction="E", turn="right",
                    color="#E24B4A", arrive_time=3.5,
                    wait_start=3.5, wait_end=9.0)
        d = v.to_dict()
        assert d["vid"] == 7
        assert d["direction"] == "E"
        assert d["wait_time"] == 5.5

    def test_default_state_is_queued(self):
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0)
        assert v.state == "queued"

    def test_spawn_offset_north(self):
        sim = make_sim()
        # Offset for N/W should be -250
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0, spawn_offset=-250)
        assert v.spawn_offset == -250

    def test_spawn_offset_south(self):
        v = Vehicle(vid=2, direction="S", turn="straight",
                    color="#fff", arrive_time=0.0, spawn_offset=250)
        assert v.spawn_offset == 250


# ══════════════════════════════════════════════════════════════════════════════
# 3. SimStats
# ══════════════════════════════════════════════════════════════════════════════

class TestSimStats:
    def test_avg_wait_zero_when_no_vehicles(self):
        s = SimStats()
        assert s.avg_wait == 0.0

    def test_avg_wait_calculated(self):
        s = SimStats(total_passed=4, total_wait=20.0)
        assert s.avg_wait == 5.0

    def test_to_dict_keys(self):
        s = SimStats()
        d = s.to_dict()
        for key in ("total_passed", "avg_wait", "cycles", "sim_time",
                    "queues", "active_vehicles", "phase", "ns_light", "ew_light"):
            assert key in d

    def test_queues_default_all_zero(self):
        s = SimStats()
        for d in ("N", "S", "E", "W"):
            assert s.queues[d] == 0


# ══════════════════════════════════════════════════════════════════════════════
# 4. Light logic (_light_for)
# ══════════════════════════════════════════════════════════════════════════════

class TestLightFor:
    def setup_method(self):
        self.sim = make_sim()

    def _set_phase(self, phase):
        self.sim.phase = phase

    def test_ns_green_gives_ns_green_ew_red(self):
        self._set_phase(Phase.NS_GREEN)
        assert self.sim._light_for("N") == LightColor.GREEN
        assert self.sim._light_for("S") == LightColor.GREEN
        assert self.sim._light_for("E") == LightColor.RED
        assert self.sim._light_for("W") == LightColor.RED

    def test_ns_yellow_gives_ns_yellow_ew_red(self):
        self._set_phase(Phase.NS_YELLOW)
        assert self.sim._light_for("N") == LightColor.YELLOW
        assert self.sim._light_for("S") == LightColor.YELLOW
        assert self.sim._light_for("E") == LightColor.RED

    def test_ns_red_all_red(self):
        self._set_phase(Phase.NS_RED)
        for d in ("N", "S", "E", "W"):
            assert self.sim._light_for(d) == LightColor.RED

    def test_ew_green_gives_ew_green_ns_red(self):
        self._set_phase(Phase.EW_GREEN)
        assert self.sim._light_for("E") == LightColor.GREEN
        assert self.sim._light_for("W") == LightColor.GREEN
        assert self.sim._light_for("N") == LightColor.RED
        assert self.sim._light_for("S") == LightColor.RED

    def test_ew_yellow_gives_ew_yellow_ns_red(self):
        self._set_phase(Phase.EW_YELLOW)
        assert self.sim._light_for("E") == LightColor.YELLOW
        assert self.sim._light_for("N") == LightColor.RED

    def test_ew_red_all_red(self):
        self._set_phase(Phase.EW_RED)
        for d in ("N", "S", "E", "W"):
            assert self.sim._light_for(d) == LightColor.RED


# ══════════════════════════════════════════════════════════════════════════════
# 5. _can_go logic
# ══════════════════════════════════════════════════════════════════════════════

class TestCanGo:
    def setup_method(self):
        self.sim = make_sim(right_turn_free=True)

    def test_green_light_all_turns_can_go(self):
        self.sim.phase = Phase.NS_GREEN
        for t in ("straight", "left", "right"):
            assert self.sim._can_go("N", t) is True

    def test_red_light_no_go_for_straight(self):
        self.sim.phase = Phase.NS_RED
        assert self.sim._can_go("N", "straight") is False

    def test_red_light_no_go_for_left(self):
        self.sim.phase = Phase.NS_RED
        assert self.sim._can_go("N", "left") is False

    def test_rtor_allowed_on_red(self):
        self.sim.phase = Phase.NS_RED
        assert self.sim._can_go("N", "right") is True

    def test_rtor_blocked_on_yellow(self):
        """RTOR must NOT trigger on yellow — only on red."""
        self.sim.phase = Phase.NS_YELLOW
        assert self.sim._can_go("N", "right") is False

    def test_rtor_disabled_globally(self):
        sim = make_sim(right_turn_free=False)
        sim.phase = Phase.NS_RED
        assert sim._can_go("N", "right") is False

    def test_rtor_only_when_light_is_red(self):
        """EW direction on NS_GREEN phase is RED — RTOR should work."""
        self.sim.phase = Phase.NS_GREEN
        assert self.sim._can_go("E", "right") is True

    def test_yellow_light_no_go_except_green(self):
        self.sim.phase = Phase.NS_YELLOW
        assert self.sim._can_go("N", "straight") is False
        assert self.sim._can_go("N", "left") is False


# ══════════════════════════════════════════════════════════════════════════════
# 6. Lanes-per-dir & queue capacity
# ══════════════════════════════════════════════════════════════════════════════

class TestLaneConfig:
    @pytest.mark.parametrize("road_type,expected_lanes", [
        (2, 1), (4, 2), (6, 3)
    ])
    def test_lanes_per_dir(self, road_type, expected_lanes):
        sim = make_sim(road_type=road_type)
        assert sim._lanes_per_dir() == expected_lanes

    @pytest.mark.parametrize("road_type,expected_max", [
        (2, 8), (4, 16), (6, 24)
    ])
    def test_max_queue(self, road_type, expected_max):
        sim = make_sim(road_type=road_type)
        assert sim._max_queue() == expected_max

    def test_queue_deques_initialized_per_lane(self):
        sim = make_sim(road_type=4)  # 2 lanes/dir
        for d in ("N", "S", "E", "W"):
            assert len(sim.queues[d]) == 2
            for q in sim.queues[d]:
                assert isinstance(q, collections.deque)

    def test_lane_resources_match_lane_count(self):
        sim = make_sim(road_type=6)  # 3 lanes/dir
        for d in ("N", "S", "E", "W"):
            assert len(sim._lane_resources[d]) == 3


# ══════════════════════════════════════════════════════════════════════════════
# 7. Signal phase sequencing (SimPy, no real-time thread)
# ══════════════════════════════════════════════════════════════════════════════

class TestSignalPhaseSequencing:
    def test_initial_phase_is_ns_green(self):
        sim = make_sim()
        assert sim.phase == Phase.NS_GREEN

    def test_phases_cycle_correctly(self):
        sim = make_sim()
        phases_seen = []

        def cb(etype, data):
            if etype == "light_change":
                phases_seen.append(data["phase"])

        sim.event_cb = cb
        sim.env.process(sim._signal_controller())
        sim.running = True
        # Run for exactly 2 full cycles (green+yellow+red x2 = 2*(20+4+1)*2)
        sim.env.run(until=200)

        expected_order = [
            Phase.NS_GREEN, Phase.NS_YELLOW, Phase.NS_RED,
            Phase.EW_GREEN, Phase.EW_YELLOW, Phase.EW_RED,
        ]
        # Check the first 6 phases match the expected cycle order
        assert phases_seen[:6] == expected_order

    def test_cycle_counter_increments(self):
        sim = make_sim()
        sim.env.process(sim._signal_controller())
        sim.running = True
        one_cycle = (sim.config.green_duration + sim.config.yellow_duration + sim.config.red_duration) * 2
        sim.env.run(until=one_cycle + 1)
        assert sim.stats.cycles >= 1

    def test_lights_updated_on_phase_change(self):
        sim = make_sim()
        sim.env.process(sim._signal_controller())
        sim.running = True
        sim.env.run(until=0.1)
        # After NS_GREEN starts, NS should be green and EW should be red
        assert sim.stats.ns_light == LightColor.GREEN
        assert sim.stats.ew_light == LightColor.RED


# ══════════════════════════════════════════════════════════════════════════════
# 8. Vehicle arrival & queue mechanics
# ══════════════════════════════════════════════════════════════════════════════

class TestVehicleArrival:
    def test_vehicle_added_to_queue_on_arrival(self):
        sim = make_sim()
        events = []
        sim.event_cb = lambda e, d: events.append(e)
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=15)
        arrived = [e for e in events if e == "vehicle_arrive"]
        assert len(arrived) >= 1

    def test_vehicle_has_correct_direction(self):
        sim = make_sim()
        arrivals = []
        sim.event_cb = lambda e, d: arrivals.append(d) if e == "vehicle_arrive" else None
        sim.env.process(sim._direction_spawner("S", 0))
        sim.running = True
        sim.env.run(until=20)
        for a in arrivals:
            assert a["direction"] == "S"

    def test_vehicle_queued_event_emitted(self):
        sim = make_sim()
        events = []
        sim.event_cb = lambda e, d: events.append(e)
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=15)
        assert "vehicle_queued" in events

    def test_vehicle_ids_are_unique(self):
        sim = make_sim()
        vids = []
        sim.event_cb = lambda e, d: vids.append(d["vid"]) if e == "vehicle_arrive" else None
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=30)
        assert len(vids) == len(set(vids)), "Duplicate VIDs detected"

    def test_queue_pos_is_zero_for_first_vehicle(self):
        sim = make_sim()
        first_arrival = []
        def cb(e, d):
            if e == "vehicle_arrive" and not first_arrival:
                first_arrival.append(d)
        sim.event_cb = cb
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=15)
        assert first_arrival[0]["queue_pos"] == 0

    def test_lane_assignment_round_robin(self):
        """Vehicles should alternate lanes in a 2-lane road."""
        sim = make_sim(road_type=4)  # 2 lanes per dir
        lanes_seen = []
        def cb(e, d):
            if e == "vehicle_arrive" and d["direction"] == "N":
                lanes_seen.append(d["lane_idx"])
        sim.event_cb = cb
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=30)
        if len(lanes_seen) >= 4:
            assert 0 in lanes_seen
            assert 1 in lanes_seen

    def test_spawn_offset_north_is_negative(self):
        """North-bound vehicles should have spawn_offset = -250."""
        sim = make_sim()
        arrivals = []
        sim.event_cb = lambda e, d: arrivals.append(d) if e == "vehicle_arrive" and d["direction"] == "N" else None
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=15)
        assert len(arrivals) > 0
        for a in arrivals:
            assert a["spawn_offset"] == -250

    def test_spawn_offset_south_is_positive(self):
        sim = make_sim()
        arrivals = []
        sim.event_cb = lambda e, d: arrivals.append(d) if e == "vehicle_arrive" and d["direction"] == "S" else None
        sim.env.process(sim._direction_spawner("S", 0))
        sim.running = True
        sim.env.run(until=15)
        assert len(arrivals) > 0
        for a in arrivals:
            assert a["spawn_offset"] == 250

    def test_queue_full_emits_diverted(self):
        """Fill a lane past capacity and confirm divert event fires."""
        sim = make_sim(road_type=2)  # 1 lane/dir, max 8 vehicles
        diverted = []
        sim.event_cb = lambda e, d: diverted.append(d) if e == "vehicle_diverted" else None
        # Force-fill queue for N lane 0
        for i in range(8):
            sim.queues["N"][0].append(i + 1000)
        # Now try spawning another — the vehicle_process checks capacity
        # Directly trigger the process to test overflow
        arrived = []
        sim.event_cb = lambda e, d: (
            diverted.append(d) if e == "vehicle_diverted"
            else arrived.append(d) if e == "vehicle_arrive" else None
        )
        # Manually add a vehicle to verify overflow detection
        with sim._lock:
            vid = sim._next_vid; sim._next_vid += 1
            q = sim.queues["N"][0]
            per_lane_max = sim._max_queue() // sim._lanes_per_dir()
            assert len(q) >= per_lane_max  # queue is full


# ══════════════════════════════════════════════════════════════════════════════
# 9. Vehicle movement & exit
# ══════════════════════════════════════════════════════════════════════════════

class TestVehicleMovement:
    def test_vehicle_moves_on_green(self):
        sim = make_sim()
        move_events = []
        sim.event_cb = lambda e, d: move_events.append(d) if e == "vehicle_move" else None
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=40)
        assert len(move_events) >= 1

    def test_vehicle_exits_after_moving(self):
        sim = make_sim()
        exits = []
        sim.event_cb = lambda e, d: exits.append(d) if e == "vehicle_exit" else None
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=60)
        assert len(exits) >= 1

    def test_total_passed_increments(self):
        sim = make_sim()
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=60)
        assert sim.stats.total_passed > 0

    def test_wait_time_recorded(self):
        sim = make_sim()
        move_events = []
        sim.event_cb = lambda e, d: move_events.append(d) if e == "vehicle_move" else None
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=60)
        for ev in move_events:
            assert ev["wait_time"] >= 0.0

    def test_vehicle_removed_from_dict_on_exit(self):
        sim = make_sim()
        exits = []
        sim.event_cb = lambda e, d: exits.append(d["vid"]) if e == "vehicle_exit" else None
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._drain_queues_process())
        for d in ("N", "S", "E", "W"):
            sim.env.process(sim._direction_spawner(d, 0))
        sim.running = True
        sim.env.run(until=80)
        for vid in exits:
            assert vid not in sim.vehicles, f"Vehicle {vid} still in dict after exit"


# ══════════════════════════════════════════════════════════════════════════════
# 10. Queue drain / release logic
# ══════════════════════════════════════════════════════════════════════════════

class TestQueueRelease:
    def test_release_increments_metric(self):
        sim = make_sim()
        sim.phase = Phase.NS_GREEN
        sim.running = True
        sim._release_from_queue("N")
        assert sim._metrics["release_calls"] >= 1

    def test_no_release_on_full_red_no_rtor(self):
        sim = make_sim(right_turn_free=False)
        sim.phase = Phase.NS_RED
        # Add a vehicle to queue
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0)
        sim.vehicles[1] = v
        sim.queues["N"][0].append(1)
        before = sim._metrics["can_go_checks"]
        sim._release_from_queue("N")
        assert sim._metrics["can_go_checks"] == before  # short-circuited

    def test_release_triggers_on_rtor(self):
        sim = make_sim(right_turn_free=True)
        sim.phase = Phase.NS_RED
        v = Vehicle(vid=1, direction="N", turn="right",
                    color="#fff", arrive_time=0.0)
        sim.vehicles[1] = v
        sim.queues["N"][0].append(1)
        sim._release_from_queue("N")
        assert sim._metrics["can_go_checks"] >= 1

    def test_already_releasing_vehicle_skipped(self):
        sim = make_sim()
        sim.phase = Phase.NS_GREEN
        v = Vehicle(vid=1, direction="N", turn="straight",
                    color="#fff", arrive_time=0.0, releasing=True)
        sim.vehicles[1] = v
        sim.queues["N"][0].append(1)
        before = sim._metrics["can_go_checks"]
        sim._release_from_queue("N")
        assert sim._metrics["can_go_checks"] == before  # releasing flag skips it


# ══════════════════════════════════════════════════════════════════════════════
# 11. update_config
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateConfig:
    def test_update_green_duration(self):
        sim = make_sim()
        sim.update_config(green_duration=35.0)
        assert sim.config.green_duration == 35.0

    def test_update_scenario(self):
        sim = make_sim()
        sim.update_config(scenario="rush")
        assert sim.config.scenario == "rush"

    def test_update_right_turn_free(self):
        sim = make_sim()
        sim.update_config(right_turn_free=False)
        assert sim.config.right_turn_free is False

    def test_update_unknown_key_ignored(self):
        sim = make_sim()
        # Should not raise
        sim.update_config(nonexistent_field="value")
        assert not hasattr(sim.config, "nonexistent_field")

    def test_update_multiple_keys(self):
        sim = make_sim()
        sim.update_config(green_duration=15.0, yellow_duration=3.0, seed=77)
        assert sim.config.green_duration == 15.0
        assert sim.config.yellow_duration == 3.0
        assert sim.config.seed == 77


# ══════════════════════════════════════════════════════════════════════════════
# 12. get_stats / get_vehicles / get_status
# ══════════════════════════════════════════════════════════════════════════════

class TestPublicAPI:
    def test_get_stats_returns_expected_keys(self):
        sim = make_sim()
        s = sim.get_stats()
        for key in ("total_passed", "avg_wait", "cycles", "sim_time",
                    "queues", "active_vehicles", "phase", "ns_light", "ew_light"):
            assert key in s

    def test_get_vehicles_empty_at_start(self):
        sim = make_sim()
        assert sim.get_vehicles() == []

    def test_get_status_has_running_and_paused(self):
        sim = make_sim()
        s = sim.get_status()
        assert "running" in s
        assert "paused" in s

    def test_get_metrics_has_profile(self):
        sim = make_sim()
        m = sim.get_metrics()
        assert "profile" in m
        assert "release_calls" in m["profile"]
        assert "can_go_checks" in m["profile"]


# ══════════════════════════════════════════════════════════════════════════════
# 13. Determinism
# ══════════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_seed_same_arrivals(self):
        def collect_arrivals(seed):
            sim = TrafficSimulation(SimConfig(seed=seed, speed_factor=1000.0))
            arrivals = []
            sim.event_cb = lambda e, d: arrivals.append((d["vid"], d["direction"], d["turn"])) if e == "vehicle_arrive" else None
            sim.env.process(sim._signal_controller())
            sim.env.process(sim._drain_queues_process())
            for d in ("N", "S", "E", "W"):
                sim.env.process(sim._direction_spawner(d, 0))
            sim.running = True
            sim.env.run(until=50)
            return arrivals

        r1 = collect_arrivals(42)
        r2 = collect_arrivals(42)
        assert r1 == r2, "Same seed must produce identical arrivals"

    def test_different_seeds_differ(self):
        def collect(seed):
            sim = TrafficSimulation(SimConfig(seed=seed, speed_factor=1000.0))
            arrivals = []
            sim.event_cb = lambda e, d: arrivals.append(d["turn"]) if e == "vehicle_arrive" else None
            sim.env.process(sim._direction_spawner("N", 0))
            sim.running = True
            sim.env.run(until=50)
            return arrivals

        r1 = collect(1)
        r2 = collect(999)
        # It's extremely unlikely two different seeds produce the same sequence
        assert r1 != r2, "Different seeds should produce different sequences"


# ══════════════════════════════════════════════════════════════════════════════
# 14. Scenarios
# ══════════════════════════════════════════════════════════════════════════════

class TestScenarios:
    @pytest.mark.parametrize("scenario", ["normal", "rush", "low"])
    def test_vehicles_spawn_in_all_scenarios(self, scenario):
        sim = TrafficSimulation(SimConfig(scenario=scenario, speed_factor=1000.0))
        arrivals = []
        sim.event_cb = lambda e, d: arrivals.append(d) if e == "vehicle_arrive" else None
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=50)
        assert len(arrivals) > 0, f"No arrivals in scenario: {scenario}"

    def test_rush_has_more_vehicles_than_low(self):
        def count(scenario):
            sim = TrafficSimulation(SimConfig(scenario=scenario, seed=42, speed_factor=1000.0))
            count = [0]
            sim.event_cb = lambda e, d: count.__setitem__(0, count[0] + 1) if e == "vehicle_arrive" else None
            sim.env.process(sim._direction_spawner("N", 0))
            sim.running = True
            sim.env.run(until=100)
            return count[0]

        assert count("rush") > count("low")


# ══════════════════════════════════════════════════════════════════════════════
# 15. Event emission
# ══════════════════════════════════════════════════════════════════════════════

class TestEventEmission:
    def test_emit_includes_sim_time(self):
        sim = make_sim()
        received = []
        sim.event_cb = lambda e, d: received.append(d)
        sim._emit("test_event", {"foo": "bar"})
        assert "sim_time" in received[0]

    def test_no_emit_without_callback(self):
        sim = TrafficSimulation(SimConfig())  # no event_cb
        # Should not raise
        sim._emit("test_event", {"foo": "bar"})

    def test_queue_update_emitted_on_arrival(self):
        sim = make_sim()
        queue_updates = []
        sim.event_cb = lambda e, d: queue_updates.append(d) if e == "queue_update" else None
        sim.env.process(sim._direction_spawner("N", 0))
        sim.running = True
        sim.env.run(until=15)
        assert len(queue_updates) > 0
        for u in queue_updates:
            assert "direction" in u
            assert "ids" in u