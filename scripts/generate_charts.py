#!/usr/bin/env python3
"""
Generate professional publication-quality charts from Mermaid diagram data.
Outputs PNG files matching academic paper standards.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np
from pathlib import Path
import json

sns.set_style("whitegrid")
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.figsize': (10, 6),
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'lines.linewidth': 2.5,
})

out_dir = Path('assets/paper_charts')
out_dir.mkdir(parents=True, exist_ok=True)

# Chart 1: Average Wait Time by Scenario and Road Type (F.1a)
def chart_01_wait_time():
    scenarios = ['Low', 'Normal', 'Rush Hour', 'Emergency']
    data = {
        '2-lane': [2.3, 4.1, 15.2, 35.7],
        '4-lane': [1.8, 2.9, 8.6, 28.4],
        '6-lane': [1.5, 2.3, 5.2, 19.2],
    }
    
    x = np.arange(len(scenarios))
    width = 0.25
    fig, ax = plt.subplots()
    
    for i, (lane, values) in enumerate(data.items()):
        ax.bar(x + i*width, values, width, label=lane, alpha=0.85)
    
    ax.set_ylabel('Average Wait Time (seconds)', fontweight='bold')
    ax.set_xlabel('Traffic Scenario', fontweight='bold')
    ax.set_title('Average Wait Time by Scenario and Road Configuration', fontweight='bold', pad=20)
    ax.set_xticks(x + width)
    ax.set_xticklabels(scenarios)
    ax.legend(title='Road Type', loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_01_wait_time.png')
    plt.close()
    print('✓ chart_01_wait_time.png')

# Chart 2: Vehicles Passed Per Cycle (F.1b)
def chart_02_throughput():
    scenarios = ['Low', 'Normal', 'Rush Hour', 'Emergency']
    data = {
        '2-lane': [3.2, 4.1, 2.8, 3.1],
        '4-lane': [5.8, 7.3, 5.2, 6.9],
        '6-lane': [8.1, 10.4, 7.6, 10.2],
    }
    
    x = np.arange(len(scenarios))
    width = 0.25
    fig, ax = plt.subplots()
    
    for i, (lane, values) in enumerate(data.items()):
        ax.bar(x + i*width, values, width, label=lane, alpha=0.85)
    
    ax.set_ylabel('Vehicles Per Cycle', fontweight='bold')
    ax.set_xlabel('Traffic Scenario', fontweight='bold')
    ax.set_title('Intersection Throughput by Scenario and Road Configuration', fontweight='bold', pad=20)
    ax.set_xticks(x + width)
    ax.set_xticklabels(scenarios)
    ax.legend(title='Road Type', loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_02_throughput.png')
    plt.close()
    print('✓ chart_02_throughput.png')

# Chart 3: Maximum Queue Depth (F.1c)
def chart_03_queue_depth():
    scenarios = ['Low', 'Normal', 'Rush Hour', 'Emergency']
    data = {
        '2-lane': [2, 5, 18, 42],
        '4-lane': [1, 3, 10, 28],
        '6-lane': [1, 2, 6, 15],
    }
    
    x = np.arange(len(scenarios))
    width = 0.25
    fig, ax = plt.subplots()
    
    for i, (lane, values) in enumerate(data.items()):
        ax.bar(x + i*width, values, width, label=lane, alpha=0.85)
    
    ax.set_ylabel('Maximum Queue Depth (vehicles)', fontweight='bold')
    ax.set_xlabel('Traffic Scenario', fontweight='bold')
    ax.set_title('Maximum Queue Length by Scenario and Road Configuration', fontweight='bold', pad=20)
    ax.set_xticks(x + width)
    ax.set_xticklabels(scenarios)
    ax.legend(title='Road Type', loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_03_queue_depth.png')
    plt.close()
    print('✓ chart_03_queue_depth.png')

# Chart 4: Cumulative Vehicle Throughput Over Time (F.2)
def chart_04_cumulative_throughput():
    time_steps = [60, 120, 180, 240, 300, 360, 420, 480]
    low = [8, 19, 31, 62, 73, 85, 94, 102]
    normal = [15, 42, 78, 125, 165, 198, 228, 255]
    rush = [25, 68, 128, 195, 268, 335, 295, 312]
    emergency = [45, 120, 215, 298, 355, 372, 380, 385]
    
    fig, ax = plt.subplots()
    ax.plot(time_steps, low, marker='o', label='Low Traffic', linewidth=2.5)
    ax.plot(time_steps, normal, marker='s', label='Normal Traffic', linewidth=2.5)
    ax.plot(time_steps, rush, marker='^', label='Rush Hour', linewidth=2.5)
    ax.plot(time_steps, emergency, marker='d', label='Emergency', linewidth=2.5)
    
    ax.set_xlabel('Simulation Time (seconds)', fontweight='bold')
    ax.set_ylabel('Cumulative Vehicles Passed', fontweight='bold')
    ax.set_title('Cumulative Vehicle Throughput Over Time', fontweight='bold', pad=20)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_04_cumulative_throughput.png')
    plt.close()
    print('✓ chart_04_cumulative_throughput.png')

# Chart 5: Fundamental Diagram (F.4)
def chart_05_fundamental_diagram():
    density = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    flow = [0, 8, 15, 22, 28, 35, 40, 45, 50, 48, 45]
    
    fig, ax = plt.subplots()
    ax.plot(density, flow, marker='o', linewidth=2.5, markersize=8, color='#2E86AB')
    ax.fill_between(density, 0, flow, alpha=0.2, color='#2E86AB')
    
    # Annotate regions
    ax.axvline(x=20, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='Critical Density')
    ax.text(10, 35, 'Uncongested\nRegion', fontsize=10, ha='center', style='italic')
    ax.text(32, 35, 'Congested\nRegion', fontsize=10, ha='center', style='italic')
    
    ax.set_xlabel('Density (vehicles/250m)', fontweight='bold')
    ax.set_ylabel('Flow Rate (vehicles/min)', fontweight='bold')
    ax.set_title('Fundamental Traffic Flow Diagram', fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_05_fundamental_diagram.png')
    plt.close()
    print('✓ chart_05_fundamental_diagram.png')

# Chart 6: Green Duration Impact (F.5)
def chart_06_green_duration_impact():
    green_durations = [10, 15, 20, 25, 30, 35, 40]
    wait_times = [8.4, 5.2, 3.1, 2.8, 2.6, 2.5, 2.4]
    cycles = [29, 39, 49, 59, 69, 79, 89]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Wait time
    ax1.plot(green_durations, wait_times, marker='o', linewidth=2.5, markersize=8, color='#A23B72')
    ax1.fill_between(green_durations, 0, wait_times, alpha=0.2, color='#A23B72')
    ax1.axvline(x=25, color='green', linestyle='--', alpha=0.7, linewidth=2, label='Optimal Zone')
    ax1.set_xlabel('Green Duration (seconds)', fontweight='bold')
    ax1.set_ylabel('Average Wait Time (seconds)', fontweight='bold')
    ax1.set_title('Wait Time vs. Green Duration', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Cycle time
    ax2.plot(green_durations, cycles, marker='s', linewidth=2.5, markersize=8, color='#F18F01')
    ax2.fill_between(green_durations, 0, cycles, alpha=0.2, color='#F18F01')
    ax2.set_xlabel('Green Duration (seconds)', fontweight='bold')
    ax2.set_ylabel('Total Cycle Time (seconds)', fontweight='bold')
    ax2.set_title('Cycle Time vs. Green Duration', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_06_green_duration_impact.png')
    plt.close()
    print('✓ chart_06_green_duration_impact.png')

# Chart 7: Signal Timing Heatmap (F.3)
def chart_07_optimization_heatmap():
    all_red = ['0.5s', '0.8s', '1.0s', '1.2s', '1.5s']
    green_durations = ['15s', '20s', '25s', '30s', '35s']
    
    data = np.array([
        [16.2, 12.1, 9.8, 8.4, 8.2],
        [15.8, 11.5, 8.6, 7.9, 7.6],
        [15.5, 11.2, 8.2, 7.5, 7.2],
        [16.1, 11.6, 8.7, 8.1, 7.9],
        [17.2, 12.3, 9.5, 8.8, 8.5],
    ]).T
    
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(data, cmap='RdYlGn_r', aspect='auto', vmin=7, vmax=17)
    
    ax.set_xticks(np.arange(len(green_durations)))
    ax.set_yticks(np.arange(len(all_red)))
    ax.set_xticklabels(green_durations)
    ax.set_yticklabels(all_red)
    
    ax.set_xlabel('Green Duration', fontweight='bold')
    ax.set_ylabel('All-Red Clearance', fontweight='bold')
    ax.set_title('Average Wait Time Heatmap: Green Duration vs. All-Red Clearance', fontweight='bold', pad=20)
    
    # Add text annotations
    for i in range(len(all_red)):
        for j in range(len(green_durations)):
            text = ax.text(j, i, f'{data[i, j]:.1f}', ha="center", va="center", color="black", fontsize=9)
    
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Wait Time (seconds)', rotation=270, labelpad=20, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_07_optimization_heatmap.png')
    plt.close()
    print('✓ chart_07_optimization_heatmap.png')

# Chart 8: Parameter Sensitivity (F.7)
def chart_08_sensitivity():
    parameters = ['Green\nDuration', 'Lane\nCapacity', 'Yellow\nDuration', 'All-Red\nClearance', 'Arrival\nRate', 'RTOR']
    elasticity = [-0.63, -0.50, -0.18, -0.15, 0.08, -0.10]
    colors = ['#d62728' if e < -0.3 else '#ff7f0e' if e < 0 else '#2ca02c' for e in elasticity]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(parameters, elasticity, color=colors, alpha=0.8)
    
    ax.set_xlabel('Elasticity (% Δ Wait Time / % Δ Parameter)', fontweight='bold')
    ax.set_title('Parameter Sensitivity Analysis: Impact on Average Wait Time', fontweight='bold', pad=20)
    ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax.grid(axis='x', alpha=0.3)
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, elasticity)):
        ax.text(val - 0.05 if val < 0 else val + 0.02, i, f'{val:.2f}', 
                va='center', ha='right' if val < 0 else 'left', fontweight='bold')
    
    # Legend for colors
    red_patch = mpatches.Patch(color='#d62728', label='CRITICAL', alpha=0.8)
    orange_patch = mpatches.Patch(color='#ff7f0e', label='MAJOR/MODERATE', alpha=0.8)
    green_patch = mpatches.Patch(color='#2ca02c', label='MINOR', alpha=0.8)
    ax.legend(handles=[red_patch, orange_patch, green_patch], loc='lower right')
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_08_sensitivity.png')
    plt.close()
    print('✓ chart_08_sensitivity.png')

# Chart 9: Webster Comparison (F.6)
def chart_09_webster_comparison():
    metrics = ['Optimal\nCycle (s)', 'Green\nDuration (s)', 'Avg Delay\n(s)', 'Vehicles/\nCycle']
    webster = [40, 24, 15.2, 0]
    simulation = [55, 26, 3.1, 4.1]
    
    x = np.arange(len(metrics))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars1 = ax.bar(x - width/2, webster, width, label='Webster Formula', alpha=0.85, color='#1f77b4')
    bars2 = ax.bar(x + width/2, simulation, width, label='Simulation Actual', alpha=0.85, color='#ff7f0e')
    
    ax.set_ylabel('Value', fontweight='bold')
    ax.set_title("Webster's Formula vs. Simulation Results (Normal Traffic, 4-lane)", fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(out_dir / 'chart_09_webster_comparison.png')
    plt.close()
    print('✓ chart_09_webster_comparison.png')

if __name__ == '__main__':
    print('Generating professional publication-quality charts...\n')
    chart_01_wait_time()
    chart_02_throughput()
    chart_03_queue_depth()
    chart_04_cumulative_throughput()
    chart_05_fundamental_diagram()
    chart_06_green_duration_impact()
    chart_07_optimization_heatmap()
    chart_08_sensitivity()
    chart_09_webster_comparison()
    print(f'\n✓ All 9 charts generated to {out_dir}/')
