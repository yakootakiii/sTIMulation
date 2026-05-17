import json
import random
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from simulation import TrafficSimulation, SimConfig

BASE = Path(__file__).resolve().parents[1]
DOCS = BASE / 'docs'
DETAIL_JSON = DOCS / 'simulation_detailed_results.json'
QUEUE_PNG = DOCS / 'chart_queue_length_over_time.png'
WAIT_PNG = DOCS / 'chart_wait_distribution.png'


def run_detailed_sim(duration: int, scenario: str, green: float = 30.0):
    random.seed(42)
    cfg = SimConfig(green_duration=green, yellow_duration=4.0, red_duration=1.0, scenario=scenario)
    sim = TrafficSimulation(cfg)

    queue_times = []
    queue_lengths = []
    wait_samples = []
    summary = {}

    def on_event(etype, data):
        if etype == 'stats':
            queue_times.append(data.get('sim_time', 0.0))
            queue_lengths.append(sum(data.get('queues', {}).values()))
        elif etype == 'vehicle_move':
            wt = data.get('wait_time')
            if wt is not None:
                wait_samples.append(float(wt))

    sim.event_cb = on_event
    sim._trace_enabled = True

    sim.env.process(sim._signal_controller())
    sim.env.process(sim._stats_reporter())
    for d in ['N', 'S', 'E', 'W']:
        sim.env.process(sim._direction_spawner(d, 0.0))

    sim.env.run(until=duration)
    stats = sim.get_stats()
    metrics = sim.get_metrics()
    summary = {
        'scenario': scenario,
        'duration': duration,
        'stats': stats,
        'metrics': metrics,
        'queue_times': queue_times,
        'queue_lengths': queue_lengths,
        'wait_samples': wait_samples,
    }
    return summary


def main():
    duration = 3600
    scenarios = ['low', 'normal', 'rush']
    detailed = []

    for scenario in scenarios:
        print(f'Running detailed scenario: {scenario}')
        detailed.append(run_detailed_sim(duration, scenario))

    with open(DETAIL_JSON, 'w') as f:
        json.dump(detailed, f, indent=2)

    # Queue length over time
    plt.figure(figsize=(9, 5))
    for row in detailed:
        plt.plot(row['queue_times'], row['queue_lengths'], label=row['scenario'])
    plt.title('Total Queue Length Over Time')
    plt.xlabel('Simulation Time (s)')
    plt.ylabel('Vehicles in Queue')
    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(QUEUE_PNG, dpi=160)
    plt.close()

    # Wait distribution
    plt.figure(figsize=(9, 5))
    bins = 30
    for row in detailed:
        samples = row['wait_samples']
        if samples:
            plt.hist(samples, bins=bins, alpha=0.35, label=row['scenario'])
    plt.title('Wait Time Distribution')
    plt.xlabel('Waiting Time (s)')
    plt.ylabel('Vehicle Count')
    plt.grid(axis='y', alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(WAIT_PNG, dpi=160)
    plt.close()

    print('Wrote', DETAIL_JSON)
    print('Wrote', QUEUE_PNG)
    print('Wrote', WAIT_PNG)


if __name__ == '__main__':
    main()
