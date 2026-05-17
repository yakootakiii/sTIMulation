import json
import random
from simulation import TrafficSimulation, SimConfig


def run_sim(duration, scenario, green=30.0, yellow=4.0, red=1.0):
    cfg = SimConfig(green_duration=green, yellow_duration=yellow, red_duration=red, scenario=scenario)
    sim = TrafficSimulation(cfg)
    # seed for reproducibility
    random.seed(42)

    # start core processes in the SimPy environment
    sim.env.process(sim._signal_controller())
    sim.env.process(sim._stats_reporter())
    for d in ["N", "S", "E", "W"]:
        sim.env.process(sim._direction_spawner(d, 0.0))

    # run headless until `duration` simulated seconds
    sim.env.run(until=duration)

    stats = sim.get_stats()
    metrics = sim.get_metrics()
    return {"scenario": scenario, "duration": duration, "stats": stats, "metrics": metrics}


if __name__ == '__main__':
    durations = 3600
    scenarios = ["low", "normal", "rush"]
    results = []
    for s in scenarios:
        print(f"Running scenario: {s} (duration={durations}s)")
        r = run_sim(durations, s, green=30.0)
        results.append(r)
        # summary
        st = r['stats']
        met = r['metrics']
        passed = st.get('total_passed', 0)
        avg_wait = st.get('avg_wait', 0.0)
        cycles = st.get('cycles', 0)
        throughput_per_hour = round(passed / (durations / 3600) if durations else 0, 2)
        print(json.dumps({
            'scenario': s,
            'total_passed': passed,
            'avg_wait_s': avg_wait,
            'cycles': cycles,
            'throughput_per_hour': throughput_per_hour,
            'wait_samples': met.get('wait_samples', 0),
            'avg_wait_sample': met.get('avg_wait_sample', 0.0)
        }, indent=2))
        print('---')

    # save results to file
    with open('docs/simulation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print('Results saved to docs/simulation_results.json')
