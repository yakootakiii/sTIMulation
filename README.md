# Traffic Intersection Simulator

Discrete-event traffic simulator with a Flask and Socket.IO web UI.

Features:
- 4-way intersection with configurable lane count and signal timings
- Real-time dashboard with live queue, vehicle, and phase updates
- Canvas visualization with a Stardew-inspired theme
- API endpoints for status, vehicles, config, and metrics
- Benchmark harness for profiling algorithm changes

Quick start:
1. python3 -m venv .venv
2. source .venv/bin/activate
3. pip install -r requirements.txt
4. python app.py
5. Open http://localhost:5001

Testing:
- source .venv/bin/activate
- python -m pytest -q

Benchmarking:
- source .venv/bin/activate
- python benchmarks/algorithm_bench.py

API:
- GET /api/status
- GET /api/vehicles
- GET or POST /api/config
- GET /api/metrics

Notes:
- The app uses Eventlet for Socket.IO async handling.
- The benchmark path skips real-time Socket.IO logging so throughput comparisons stay focused on the algorithm.
