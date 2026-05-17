import json
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parents[1]
JSON_IN = BASE / 'docs' / 'simulation_results.json'
CSV_OUT = BASE / 'docs' / 'simulation_results_table.csv'
IMG_WAIT = BASE / 'docs' / 'chart_avg_wait.png'
IMG_THROUGHPUT = BASE / 'docs' / 'chart_throughput.png'

with open(JSON_IN, 'r') as f:
    data = json.load(f)

# Normalize into rows
rows = []
for r in data:
    sc = r.get('scenario')
    stats = r.get('stats', {})
    metrics = r.get('metrics', {})
    rows.append({
        'scenario': sc,
        'duration_s': r.get('duration', 0),
        'total_passed': stats.get('total_passed', 0),
        'avg_wait_s': stats.get('avg_wait', 0.0),
        'cycles': stats.get('cycles', 0),
        'throughput_per_hour': round(stats.get('total_passed', 0) / (r.get('duration',1) / 3600),2),
        'wait_samples': metrics.get('wait_samples', 0),
        'avg_wait_sample': metrics.get('avg_wait_sample', 0.0),
    })

# Write CSV
with open(CSV_OUT, 'w', newline='') as csvf:
    writer = csv.DictWriter(csvf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

# Create charts
scenarios = [r['scenario'] for r in rows]
avg_waits = [r['avg_wait_s'] for r in rows]
throughput = [r['throughput_per_hour'] for r in rows]

plt.figure(figsize=(6,4))
plt.bar(scenarios, avg_waits, color=['#2b8cbe','#7bccc4','#a6bddb'])
plt.title('Average Waiting Time by Scenario (s)')
plt.ylabel('Average Wait (s)')
plt.xlabel('Scenario')
plt.grid(axis='y', alpha=0.2)
plt.tight_layout()
plt.savefig(IMG_WAIT)
plt.close()

plt.figure(figsize=(6,4))
plt.bar(scenarios, throughput, color=['#2ca25f','#66c2a4','#99d8c9'])
plt.title('Throughput (vehicles/hour) by Scenario')
plt.ylabel('Vehicles / hour')
plt.xlabel('Scenario')
plt.grid(axis='y', alpha=0.2)
plt.tight_layout()
plt.savefig(IMG_THROUGHPUT)
plt.close()

print('Wrote', CSV_OUT)
print('Wrote', IMG_WAIT)
print('Wrote', IMG_THROUGHPUT)
