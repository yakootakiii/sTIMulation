# sTIMulation Sprint Playbook

This document is written task-by-task so teammates can understand:
- what each task is,
- why it matters,
- how to do it,
- and which files or code patterns to look at.

It is written for the current `sTIMulation` repo, so the examples point to the same style of code already used here.

## Quick task map

| Task | What it means | Main files |
|---|---|---|
| Security & compliance | Protect the app from unsafe input, unsafe output, and risky dependencies | `security_utils.py`, `app.py`, `templates/index.html` |
| Backend / API | Keep routes, config, and metrics clean and predictable | `app.py`, `simulation.py` |
| Frontend / UI | Make the page clear, readable, and safe to update dynamically | `templates/index.html`, `static/css/stardew_v2.css` |
| Simulation engine | Model traffic flow, queues, and signal timing | `simulation.py` |
| Real-time updates | Send live stats, logs, and light changes to the browser | `socketio_utils.py`, `app.py` |
| Analytics & monitoring | Show wait times, throughput, and system health | `docs/simulation_results*.json`, frontend monitoring UI |
| Testing & validation | Prove the app still works after changes | `tests/` |
| Deployment & DevOps | Run the app consistently with Docker, CI, and health checks | `Dockerfile`, `docker-compose.yml`, `run.sh` |

If you want the long version, the next sections still explain each task in more detail.

---

## 1) John Timothy Carranza — Security & Compliance Lead

### What the task is
John owns the safety layer of the app:
- input validation and sanitization
- XSS/CSRF protection
- security headers
- dependency vulnerability scanning
- API authentication and authorization
- rate limiting and DDoS protection
- security audit reports
- compliance verification
- penetration testing
- third-party security integration

### How he should do it
1. Start at the input boundaries: every request from the browser or API should be checked before the app uses it.
2. Sanitize output before rendering: anything displayed in HTML must be treated as untrusted.
3. Lock down the server response: add headers like `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy`.
4. Protect the API: require valid request content types, validate payloads, and reject unexpected keys.
5. Rate-limit noisy traffic: logs and repeated events should be throttled.
6. Scan dependencies: use `pip-audit` or `safety` in CI so insecure packages are caught early.
7. Document findings: write a short report that explains the risk, the affected file, and the mitigation.
8. Verify compliance: show that secrets are not hard-coded and that user data is not injected into HTML.

### Code pattern to follow
The repo already uses a validation helper like this:

```python
# security_utils.py

def validate_config_input(data: dict) -> dict:
    valid_keys = {
        "green_duration", "yellow_duration", "red_duration",
        "scenario", "road_type", "right_turn_free", "speed_factor"
    }

    validated = {}
    for k, v in data.items():
        if k not in valid_keys:
            continue
        validated[k] = v
    return validated
```

For response hardening, use server-side headers:

```python
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response
```

For browser output, never inject raw user text into `innerHTML`. Use text nodes instead:

```javascript
function renderLog() {
  logScroll.textContent = "";
  STATE.logs.slice(0, 50).forEach((entry) => {
    const row = document.createElement("div");
    row.className = "log-entry";

    const msg = document.createElement("span");
    msg.className = `log-msg c-${entry.cls || "gray"}`;
    msg.textContent = entry.msg;

    row.appendChild(msg);
    logScroll.appendChild(row);
  });
}
```

### How to explain it simply
“Security means checking input early, never trusting browser data, protecting the server with headers and rate limits, and proving the app does not expose secrets or unsafe HTML.”

---

## 2) Ian Emmanuel Comia — Backend Architecture & API Lead

### What the task is
Ian owns the server structure and API behavior:
- RESTful API expansion
- error handling improvements
- request validation
- code structure improvements
- configuration management
- database integration
- event loop optimization
- connection management
- server performance tuning
- logging and monitoring infrastructure
- error recovery mechanisms
- algorithm integration support
- Socket.IO backend support
- backend documentation and standards

### How he should do it
1. Keep routes small and predictable: each endpoint should do one job.
2. Validate all POST/PUT/PATCH requests before touching the simulation.
3. Separate config from logic: use `SimConfig` and helper functions instead of scattering constants.
4. Use Socket.IO for live updates: send stats, light state, and vehicle events in a consistent format.
5. Handle errors gracefully: if metrics or updates fail, return a safe fallback instead of crashing.
6. Keep the backend documented so the frontend knows which fields it can expect.
7. If a database is added later, isolate that code in a separate layer so the web routes stay clean.

### Code pattern to follow
The backend currently exposes structured JSON endpoints:

```python
@app.route("/api/metrics")
def metrics():
    if sim:
        stats = sim.get_stats()
        out = {
            "total_passed": stats["total_passed"],
            "avg_wait": stats["avg_wait"],
            "cycles": stats["cycles"],
            "sim_time": stats["sim_time"],
            "active_vehicles": stats["active_vehicles"],
            "queues": stats["queues"],
        }
        return jsonify(out)
    return jsonify({"total_passed": 0, "avg_wait": 0.0})
```

Use a config helper so updates are centralized:

```python
def _apply_cfg(cfg: SimConfig, data: dict):
    mapping = {
        "green": ("green_duration", float),
        "yellow": ("yellow_duration", float),
        "red": ("red_duration", float),
        "scenario": ("scenario", str),
        "road_type": ("road_type", int),
        "right_turn": ("right_turn_free", bool),
        "speed": ("speed_factor", float),
    }
    for key, (attr, cast) in mapping.items():
        if key in data:
            setattr(cfg, attr, cast(data[key]))
```

For server events, keep the callback thin and route through a single dispatcher:

```python
def _emit_event(event_type: str, data: dict):
    if event_type in {"stats", "light_change", "reset", "ack"}:
        socketio.emit(event_type, data)
        return
    socketio.emit(event_type, data)
```

### How to explain it simply
“The backend is the contract: it validates data, keeps config organized, exposes clean APIs, and sends live updates to the frontend in one predictable format.”

---

## 3) Vince — Deployment, DevOps & Flexible Lead

### What the task is
Vince owns the path from code to runnable system:
- Docker container setup
- Docker Compose configuration
- image optimization
- registry management
- CI/CD pipeline setup
- automated testing pipeline integration
- staging and production deployment
- zero-downtime deployment strategy
- environment configuration management
- monitoring and logging setup
- performance monitoring
- backup and disaster recovery
- system health dashboards
- full-stack assistance
- cross-team coordination
- critical path management

### How he should do it
1. Make the app runnable everywhere: same behavior in local dev, Docker, and CI.
2. Keep the image small and predictable: install only what the app needs.
3. Use Compose for local development so the team can spin it up quickly.
4. Automate validation in CI: run tests and benchmark checks on every push.
5. Add health checks and metrics so deployment status is visible.
6. Plan for rollback and disaster recovery: if deployment fails, the team should know how to revert.
7. Coordinate the critical path by making sure algorithm, backend, and UI dependencies are available when teammates need them.

### Code / config pattern to follow
A good deployment checklist looks like this:

```bash
export PYTHONPATH=$PWD
source .venv/bin/activate
pytest -q
python benchmarks/algorithm_bench.py
```

A Compose service should expose the app port and healthcheck:

```yaml
services:
  web:
    build: .
    ports:
      - "5001:5001"
    environment:
      - SIM_ASYNC_MODE=threading
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/"]
      interval: 30s
      timeout: 5s
      retries: 3
```

For CI, the key idea is simple:

```yaml
- name: Run tests
  run: pytest -q

- name: Run benchmark
  run: python benchmarks/algorithm_bench.py
```

### How to explain it simply
“My role is to make sure the app can be built, run, validated, and shipped without extra setup pain.”

---

## 4) Saludo Noel Zyrence — Algorithm & Performance Lead

### What the task is
Noel owns the traffic engine itself:
- refactor traffic flow calculations
- advanced queuing model implementation
- vehicle routing and pathfinding optimization
- computational complexity reduction
- caching strategy implementation
- performance profiling and benchmarking
- memory optimization
- event loop tuning
- traffic pattern validation
- data structure optimization
- algorithm documentation
- performance testing suite creation

### How he should do it
1. Profile first: find out where the simulation spends time.
2. Reduce repeated scans: replace expensive queue searches with better data structures.
3. Short-circuit early: if a queue is full or a vehicle cannot move, return before doing more work.
4. Keep routing logic deterministic so the benchmark is repeatable.
5. Measure before and after: if a change is not faster or clearer, it may not be worth it.
6. Document the behavior: describe what changed and why the algorithm still matches traffic rules.

### Code pattern to follow
Use a benchmark script to prove improvements:

```python
import random
import time
from simulation import TrafficSimulation, SimConfig

random.seed(42)
cfg = SimConfig(scenario="rush", speed_factor=1000.0)
sim = TrafficSimulation(cfg)

start = time.time()
sim.env.run(until=60.0)
elapsed = time.time() - start

print(f"Simulated 60s in {elapsed:.4f}s")
print(sim.get_stats())
```

A performance-minded optimization usually looks like this:

```python
if len(queue) >= capacity:
    return

# only build the vehicle object after the cheap check passes
vehicle = create_vehicle()
queue.append(vehicle)
```

### How to explain it simply
“First find the slow path, then make the expensive work happen less often, and verify the result with a benchmark.”

---

## 5) Aila Roshiele Donayre — UI/UX Design & Frontend Development Lead

### What the task is
Aila owns the overall user interface system:
- reusable UI component design
- responsive layout system creation
- color scheme and typography design
- glassmorphism / neumorphism implementation
- mockup and prototype design
- style guide documentation
- accessibility compliance
- responsive frontend implementation
- UI component library development
- frontend state management
- drag-and-drop interactions
- real-time frontend updates
- user input handling
- form validation and error handling
- frontend optimization
- lazy loading implementation

### How she should do it
1. Design the UI system first: colors, spacing, typography, and component states.
2. Make controls reusable: buttons, sliders, badges, cards, and panels should share styles.
3. Keep the layout responsive: the app should still work on smaller screens.
4. Connect controls to state: when the user changes a slider or select box, the UI should send an update.
5. Validate inputs visually: show what is active, disabled, connected, or loading.
6. Keep the frontend efficient: use lazy loading where it actually helps, not everywhere.

### Code pattern to follow
The style system can be centralized in CSS:

```css
.btn {
  flex: 1;
  padding: 8px 6px;
  border-radius: 8px;
  background: var(--bg3);
  color: var(--text2);
  cursor: pointer;
}

.btn:hover {
  background: var(--bg4);
  color: var(--text);
}
```

Use state-driven input handling in the browser:

```javascript
function onCfgChange() {
  socket.emit('cmd_update_config', {
    green_duration: +document.getElementById('sl-green').value,
    yellow_duration: +document.getElementById('sl-yellow').value,
    red_duration: +document.getElementById('sl-red').value,
    scenario: document.getElementById('sel-scenario').value,
    road_type: +document.getElementById('sel-road').value,
    right_turn_free: document.getElementById('ck-rturn').checked,
    speed_factor: +document.getElementById('sl-speed').value,
  });
}
```

### How to explain it simply
“The frontend should be reusable, responsive, and state-driven: every control has a purpose, and every visual choice should make the app easier to understand.”

---

## 6) Edricka Paulos — Canvas & Visualization Lead

### What the task is
Edricka owns what users see on the canvas:
- vehicle rendering enhancement
- road lane visualization
- traffic light animations
- pedestrian crossing indicators
- intersection visualization optimization
- zoom and pan functionality
- heatmap overlay implementation
- congestion visualization
- animation smoothing
- canvas rendering optimization
- WebGL scaling research
- GPU acceleration exploration
- efficient redraw cycle optimization

### How to do it
1. Draw the scene in layers: background, road, markings, lights, vehicles.
2. Keep visual state separate from simulation state so animation can interpolate smoothly.
3. Use `requestAnimationFrame` for redraws.
4. Only redraw what you need when possible.
5. Plan for scaling features like zoom, heatmaps, or WebGL, but add them only when the base canvas is stable.

### Code pattern to follow
The canvas loop should be frame-based:

```javascript
let LAST_FRAME = performance.now();
let FRAME_DT = 1 / 60;

function frame(now) {
  FRAME_DT = Math.min((now - LAST_FRAME) / 1000, 0.05);
  LAST_FRAME = now;
  drawScene();
  requestAnimationFrame(frame);
}

requestAnimationFrame(frame);
```

A good vehicle draw function keeps its own transform:

```javascript
function drawVehicle(x, y, angle, color, state, alpha = 1) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, y);
  ctx.rotate(angle);
  // draw body, roof, lights here
  ctx.restore();
}
```

### How to explain it simply
“Canvas work is about layering and animation: draw the world in order, then move vehicles smoothly on top of it.”

---

## 7) Jan Mayen Mallen — Analytics & Data Visualization Lead

### What the task is
Jan owns the numbers and reporting layer:
- real-time metrics dashboard
- historical data charting
- traffic flow visualization
- congestion analytics
- vehicle wait time analytics
- throughput metrics calculation
- phase timing analysis
- KPI tracking
- CSV/JSON export functionality
- PDF report generation
- session recording and playback
- data persistence implementation

### How to do it
1. Pull live stats from the backend rather than guessing in the UI.
2. Display the key KPIs first: passed cars, average wait, cycles, active vehicles, queue lengths.
3. Make the dashboard easy to scan with cards or charts.
4. Poll or subscribe to updates depending on how frequently the data changes.
5. Export data cleanly in a structured format like JSON or CSV.
6. If you add persistence, separate live simulation state from archived session data.

### Code pattern to follow
A simple metrics poller looks like this:

```javascript
async function pollMetrics() {
  const res = await fetch('/api/metrics', { cache: 'no-store' });
  const data = await res.json();
  document.getElementById('mon-api').textContent = 'live';
  document.getElementById('m-passed').textContent = data.total_passed;
}
```

The backend endpoint should return a compact payload:

```python
@app.route("/api/metrics")
def metrics():
    stats = sim.get_stats()
    return jsonify({
        "total_passed": stats["total_passed"],
        "avg_wait": stats["avg_wait"],
        "cycles": stats["cycles"],
        "sim_time": stats["sim_time"],
        "active_vehicles": stats["active_vehicles"],
        "queues": stats["queues"],
    })
```

### How to explain it simply
“Analytics is about turning the raw simulation into numbers people can understand quickly.”

---

## 8) Ayelet D'arcy De Castro — Backend API & Real-time Communication Lead

### What the task is
Ayelet owns the live communication layer:
- RESTful API endpoint expansion
- WebSocket optimization
- API versioning strategy
- rate limiting implementation
- API documentation
- event batching optimization
- connection pooling and management
- HTTP long-polling fallback
- broadcasting optimization
- real-time data streaming
- message queue implementation
- error recovery systems
- connection state management
- load balancing preparation

### How to do it
1. Keep the event contract stable: use the same event names and payload shapes.
2. Batch repeated updates so the browser gets fewer messages.
3. Rate-limit logs and noisy events so the socket stays responsive.
4. Flush batches on important state changes like stats updates or resets.
5. Add fallbacks if websocket transport is not available.
6. Document payloads so the frontend knows what to expect.

### Code pattern to follow
The batcher/rate limiter pattern is a good base:

```python
def _emit_event(event_type: str, data: dict):
    if event_type == "log" and not rate_limiter.allow(event_type):
        return

    if event_type in {"vehicle_arrive", "vehicle_queued", "vehicle_move", "vehicle_exit"}:
        event_batcher.add(event_type, data)
        event_batcher.flush_if_due()
        return

    if event_type in {"stats", "light_change", "reset", "ack"}:
        event_batcher.flush()
        socketio.emit(event_type, data)
        return
```

And the batcher itself should be lock-safe and predictable:

```python
class RateLimiter:
    def allow(self, event_type: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self.last_emit.get(event_type, 0.0)
            if (now - last) >= self.min_interval:
                self.last_emit[event_type] = now
                return True
            return False
```

### How to explain it simply
“Real-time communication should reduce noise, keep the socket stable, and only send what the browser actually needs.”

---

## 9) Jerzha Ara Lalu — Testing & Quality Assurance Lead

### What the task is
Jerzha owns confidence in the code:
- unit testing
- integration testing
- E2E testing
- performance testing
- automated testing pipeline
- bug tracking and management
- regression testing
- cross-browser testing
- accessibility testing
- load and stress testing
- user documentation
- Swagger / OpenAPI documentation
- test coverage reporting
- quality metrics tracking

### How to do it
1. Write tests at the right level: unit tests for small logic, integration tests for routes, and E2E tests for the user flow.
2. Run tests often: after each meaningful change.
3. Keep performance checks deterministic so results can be compared.
4. Report failures clearly so the next person knows what broke and where.
5. Include accessibility and browser checks for the UI.
6. Document the test commands so the team can reproduce them.

### Code pattern to follow
A simple pytest shape looks like this:

```python
def test_metrics_endpoint(client):
    response = client.get('/api/metrics')
    assert response.status_code == 200
    data = response.get_json()
    assert 'total_passed' in data
```

A deterministic benchmark complements the tests:

```python
random.seed(42)
sim = TrafficSimulation(SimConfig(scenario="rush", speed_factor=1000.0))
sim.env.run(until=60.0)
assert sim.get_stats()["total_passed"] >= 0
```

### How to explain it simply
“Testing proves the app still works after changes, and the benchmark proves it still performs well.”

---

## 10) Anda Vael — Infrastructure & DevOps Support

### What the task is
Anda owns the platform and operations side:
- server provisioning
- database configuration
- cache layer setup
- load balancer configuration
- backup automation
- disaster recovery planning
- log aggregation setup
- monitoring integration
- system performance tuning
- system architecture documentation
- runbook creation
- incident response procedures
- deployment guide documentation

### How to do it
1. Make the deployment repeatable with clear steps and scripts.
2. Keep runtime config explicit: use environment variables and documented defaults.
3. Add health checks and logs so operators can see whether the app is healthy.
4. Document recovery steps for failures, restarts, and rollbacks.
5. Plan for observability: logs, metrics, and dashboards should tell a clear story.
6. If you add a cache or DB later, keep those settings separate from app logic.

### Code pattern to follow
A deployment checklist should look like this:

```bash
docker-compose up --build -d
curl -sS http://localhost:5001/api/metrics
```

A basic runbook entry should be simple and concrete:

```text
1. Check whether the container is healthy.
2. Confirm /api/metrics responds.
3. Review recent logs.
4. Restart only after confirming config values.
```

### How to explain it simply
“Infrastructure work is about making the app easy to run, easy to inspect, and easy to recover when something goes wrong.”

---

## Short team summary
If you want to explain the whole project in a simple way, say:

> “Each person owned one slice of the app — security, backend, deployment, algorithm, frontend, canvas, analytics, real-time messaging, testing, or infrastructure — and we tied everything together with live updates, metrics, Docker, and tests so the app could run cleanly end to end.”

---

## Files worth showing while explaining
- `simulation.py` — core simulation logic and profiling
- `app.py` — Flask routes, config handling, and Socket.IO server
- `security_utils.py` — validation and security helpers
- `socketio_utils.py` — event batching and rate limiting
- `templates/index.html` — UI, canvas, log rendering, and monitoring panel
- `static/css/stardew_v2.css` — theme and layout polish
- `benchmarks/algorithm_bench.py` — deterministic performance benchmark
- `docs/TASK_EXPLANATION_DETAILED.md` — this guide

---

## Final note
Use the following rule when presenting any task:
1. say **what the task is**,  
2. say **how to do it**,  
3. show **a code example**,  
4. and point to the **file in this repo** where that idea lives.
