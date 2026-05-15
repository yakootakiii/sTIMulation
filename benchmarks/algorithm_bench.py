"""Simple benchmark for the simulation algorithm.
Runs the simulation environment for a fixed simulated time and reports wall-clock time and passed vehicles.
"""
import time
from simulation import TrafficSimulation, SimConfig

def run_bench(sim_time=60.0):
    cfg = SimConfig(scenario="rush", speed_factor=1000.0)
    sim = TrafficSimulation(cfg)

    # Start processes but don't use the real-time thread; run env directly
    sim.env.process(sim._signal_controller())
    sim.env.process(sim._stats_reporter())
    for d in ["N","S","E","W"]:
        sim.env.process(sim._direction_spawner(d, 0))

    start = time.time()
    sim.env.run(until=sim_time)
    elapsed = time.time() - start

    stats = sim.get_stats()
    print(f"Simulated {sim_time}s in {elapsed:.2f}s wall time")
    print(f"Total passed: {stats['total_passed']}")
    print(f"Avg wait: {stats['avg_wait']}")

if __name__ == '__main__':
    run_bench(60.0)
