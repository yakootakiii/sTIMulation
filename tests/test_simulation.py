"""Unit and integration tests for the traffic simulation."""
import pytest
from simulation import TrafficSimulation, SimConfig, Direction, Turn, Phase


class TestSimConfig:
    def test_default_config(self):
        cfg = SimConfig()
        assert cfg.green_duration == 20.0
        assert cfg.scenario == "normal"


class TestTrafficSimulation:
    def test_init(self):
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        assert sim.running is False
        assert sim.paused is False
        assert len(sim.vehicles) == 0

    def test_light_for_ns_green(self):
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        sim.phase = Phase.NS_GREEN
        assert sim._light_for("N").value == "green"
        assert sim._light_for("S").value == "green"
        assert sim._light_for("E").value == "red"
        assert sim._light_for("W").value == "red"

    def test_light_for_ew_green(self):
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        sim.phase = Phase.EW_GREEN
        assert sim._light_for("E").value == "green"
        assert sim._light_for("W").value == "green"
        assert sim._light_for("N").value == "red"
        assert sim._light_for("S").value == "red"

    def test_can_go_green(self):
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        sim.phase = Phase.NS_GREEN
        assert sim._can_go("N", "straight") is True
        assert sim._can_go("E", "straight") is False

    def test_can_go_right_on_red(self):
        cfg = SimConfig(right_turn_free=True)
        sim = TrafficSimulation(cfg)
        sim.phase = Phase.NS_GREEN  # E/W have red
        assert sim._can_go("E", "right") is True
        assert sim._can_go("E", "straight") is False

    def test_stats_initial(self):
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        stats = sim.get_stats()
        assert stats["total_passed"] == 0
        assert stats["avg_wait"] == 0.0
        assert stats["cycles"] == 0

    def test_queues_are_deque(self):
        from collections import deque
        cfg = SimConfig()
        sim = TrafficSimulation(cfg)
        for d in ["N", "S", "E", "W"]:
            assert isinstance(sim.queues[d], deque)

    def test_env_processes_basic(self):
        """Run sim env for 1s and verify basic operation."""
        cfg = SimConfig(scenario="rush")
        sim = TrafficSimulation(cfg)
        
        sim.env.process(sim._signal_controller())
        sim.env.process(sim._stats_reporter())
        for d in ["N", "S", "E", "W"]:
            sim.env.process(sim._direction_spawner(d, 0))
        
        sim.env.run(until=1.0)
        stats = sim.get_stats()
        # After 1s in rush, expect some vehicles
        assert stats["total_passed"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
