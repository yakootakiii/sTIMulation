import sys
import time
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import TrafficSimulation, SimConfig

def run_bench(sim_time=120.0):
    random.seed(42)
    cfg = SimConfig(scenario="rush", speed_factor=1000.0)
    sim = TrafficSimulation(cfg)

    # Start processes but don't use the real-time thread; run env directly
    sim.env.process(sim._signal_controller())
    sim.env.process(sim._drain_queues_process())   # ← add this line
    for d in ["N", "S", "E", "W"]:
        sim.env.process(sim._direction_spawner(d, 0))

    sim.running = True    
    start = time.time()
    sim.env.run(until=sim_time)
    elapsed = time.time() - start

    stats = sim.get_stats()
    print(f"Simulated {sim_time}s in {elapsed:.4f}s wall time")
    print(f"Total passed: {stats['total_passed']}")
    print(f"Avg wait: {stats['avg_wait']}")
    metrics = sim.get_metrics() if hasattr(sim, "get_metrics") else {}
    if metrics:
        print(f"Profile: {metrics['profile']}")
        print(f"Wait samples: {metrics['wait_samples']}")

if __name__ == '__main__':
    run_bench(5000.0)