# 🚦 Traffic Intersection Simulator

A full discrete-event simulation of a 4-way intersection, built with **SimPy** (Python) and a **Flask + SocketIO** real-time web interface.

## Architecture

```
traffic_sim/
├── simulation.py      # SimPy DES engine — vehicles, signals, queues
├── app.py             # Flask + SocketIO server — real-time bridge
├── templates/
│   └── index.html     # Canvas renderer + control panel + live dashboard
└── requirements.txt
```

## Quick Start

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the server
python app.py

# Open in browser
http://localhost:5001
```

## Features

### Simulation (SimPy)
- Discrete-event simulation with real SimPy environment
- 4-way N-S / E-W signal cycling: Green → Yellow → all-red clearance
- Vehicle arrival modelled with Poisson-like inter-arrival times
- Per-direction queue management with configurable lane capacity
- Right-turn-on-red rule (toggleable)
- Per-vehicle wait time tracking and statistics

### Scenarios
| Scenario     | Arrival Rate |
|-------------|-------------|
| Normal      | ~4s avg     |
| Rush Hour   | ~1.4s avg   |
| Low Traffic | ~9s avg     |

### Road Types
| Type   | Lanes | Queue Capacity |
|--------|-------|----------------|
| 2-lane | 1/dir | 8 vehicles     |
| 4-lane | 2/dir | 16 vehicles    |
| 6-lane | 3/dir | 24 vehicles    |

### Controls
- Start / Pause / Reset
- Speed: 0.5× to 15× real-time
- Green / Yellow / all-red clearance duration sliders
- Scenario selector
- Road type selector
- Right-turn-on-red toggle

### Dashboard
- Live queue bar per direction (N, S, E, W)
- Metrics: total cars passed, average wait time, signal cycles, active vehicles
- Phase timer progress bar
- Live event log (last 80 events)
- Per-direction traffic light state in canvas visualization

## Technical Notes
- SimPy runs in a background thread, stepping 0.1 sim-seconds per tick
- SocketIO pushes events to browser in real time (eventlet async)
- Canvas renderer runs at ~60fps with smooth vehicle interpolation
- Vehicle colors are randomized per car; turning direction is randomized
# sTIMulation
