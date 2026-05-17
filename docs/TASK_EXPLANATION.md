# sTIMulation Task Explanation Guide

This guide is written so you can explain the sprint work to the team in simple terms:
- what each person’s task was,
- how to approach it,
- and where it was implemented in this repo.

## How to explain the work in one sentence
We turned a basic traffic simulator into a tested, monitored, containerized, real-time web app by splitting the work into algorithm, backend, frontend, security, testing, and deployment tasks.

## Team task breakdown

### Noel — Algorithm & Performance Lead
**Task:** Improve the traffic simulation engine so cars move faster, queues behave better, and the simulation runs efficiently.

**How to do it:**
1. Look at `simulation.py` first.
2. Identify the slow parts with profiling.
3. Reduce repeated work by changing queue handling and movement logic.
4. Measure results using `benchmarks/algorithm_bench.py`.
5. Keep behavior correct by re-running the test suite.

**What was done in this repo:**
- Added lightweight profiling counters in `simulation.py`.
- Improved queue handling so vehicles are tracked more efficiently.
- Reduced unnecessary work in movement and spawning.
- Added a deterministic benchmark in `benchmarks/algorithm_bench.py`.

**How to explain it to others:**
“Start with the simulation engine, find the expensive loops, replace repeated scans with better data structures, and prove the improvement with a benchmark.”

---

### Ian — Backend Architecture & API Lead
**Task:** Keep the Flask backend organized, expose clean endpoints, and make sure the server sends the right data to the UI.

**How to do it:**
1. Review `app.py` and list every route the frontend needs.
2. Make sure responses are JSON and stable.
3. Validate inputs before they reach the simulation.
4. Keep server state synchronized with the UI through Socket.IO.

**What was done in this repo:**
- Kept `/api/status`, `/api/vehicles`, `/api/config`, and `/api/metrics` available.
- Added validated config handling.
- Exposed simulation metrics so the UI can display runtime information.

**How to explain it to others:**
“The backend is the source of truth. It should validate user input, expose only the needed endpoints, and push state to the frontend in a predictable format.”

---

### Vince — Deployment, DevOps, and Flexible Lead
**Task:** Make the project easy to run, test, deploy, and maintain.

**How to do it:**
1. Containerize the app with Docker.
2. Add a Compose file for local development.
3. Add CI so tests and benchmark checks run automatically.
4. Make sure the app can be launched reliably in a consistent environment.
5. Add monitoring and health checks.

**What was done in this repo:**
- Updated `Dockerfile` and `docker-compose.yml`.
- Added CI validation in the workflow.
- Kept the app runnable locally and in containers.
- Added monitoring support through `/api/metrics` and the UI panel.

**How to explain it to others:**
“My job was to make sure the app can be built, run, validated, and shipped without extra setup pain.”

---

### Tim — Security & Compliance Lead
**Task:** Protect the app from unsafe input, hard-coded secrets, and common web risks.

**How to do it:**
1. Review every user-facing input path.
2. Sanitize input before it reaches HTML or config updates.
3. Add security headers.
4. Remove hard-coded secrets from source.
5. Limit noisy or unsafe traffic where needed.

**What was done in this repo:**
- Replaced the hard-coded secret fallback with environment-based configuration.
- Added security headers in `app.py`.
- Used validation helpers from `security_utils.py`.
- Reworked the log renderer so it no longer injects raw HTML.

**How to explain it to others:**
“Security work means making sure inputs are checked, secrets are not exposed in code, and the browser never receives unsafe HTML.”

---

### Aila — UI/UX Design & Frontend Lead
**Task:** Make the app look polished, modern, and easy to use.

**How to do it:**
1. Define the visual style first.
2. Build reusable controls for buttons, sliders, panels, and badges.
3. Keep spacing, colors, and typography consistent.
4. Make sure the UI still works on smaller screens.

**What was done in this repo:**
- Refined the dashboard layout and theme in `templates/index.html`.
- Adjusted styles in `static/css/stardew_v2.css`.
- Kept the controls, stats cards, and status bar visually consistent.

**How to explain it to others:**
“Design first, then build the interface around reusable, consistent components so the app feels intentional instead of random.”

---

### Aicka — Canvas & Visualization Lead
**Task:** Draw the traffic intersection, vehicles, lights, and road scene in the browser.

**How to do it:**
1. Work inside the canvas code in `templates/index.html`.
2. Draw the road, lanes, and traffic lights before the vehicles.
3. Keep movement smooth by separating simulation state from visual state.
4. Use animation frames for drawing, not direct blocking loops.

**What was done in this repo:**
- Built the canvas rendering pipeline.
- Added lane, light, and vehicle drawing.
- Added deterministic tile-style background rendering for the map.

**How to explain it to others:**
“Canvas work is about layering: background first, then roads, then lights, then vehicles, while keeping animation smooth.”

---

### Mayen — Analytics & Data Visualization Lead
**Task:** Show the important traffic metrics clearly so users can understand how the simulation is performing.

**How to do it:**
1. Pull metrics from `/api/metrics`.
2. Display totals, wait time, cycles, and queue sizes.
3. Update the dashboard in real time.
4. Keep the display simple enough to understand at a glance.

**What was done in this repo:**
- Added metric output from the backend.
- Added a monitoring panel in `templates/index.html`.
- Polled `/api/metrics` and displayed runtime info in the UI.

**How to explain it to others:**
“Analytics is not just graphs — it’s showing the right numbers at the right time so users can tell what the system is doing.”

---

### D'arcy — Backend API & Real-time Communication Lead
**Task:** Make the browser update live without reloading and keep event traffic efficient.

**How to do it:**
1. Use Socket.IO event handlers for live updates.
2. Batch repeated events so the server does not spam the browser.
3. Rate-limit noisy events like logs.
4. Flush queued events when important state changes happen.

**What was done in this repo:**
- Added `socketio_utils.py` with batching and rate limiting.
- Routed vehicle and log events through the batcher in `app.py`.
- Kept the frontend synchronized with `stats`, `light_change`, and vehicle events.

**How to explain it to others:**
“Real-time updates should be efficient: batch repeated messages, limit noise, and only push what the browser really needs.”

---

### Jerzha — Testing & Quality Assurance Lead
**Task:** Make sure the app behaves correctly and stays stable after changes.

**How to do it:**
1. Write tests for the backend and simulation logic.
2. Re-run tests after every meaningful change.
3. Use benchmark runs to catch regressions in performance.
4. Keep tests deterministic where possible.

**What was done in this repo:**
- Kept the test suite passing.
- Added/kept simulation and API coverage.
- Used the benchmark to verify performance after optimizations.

**How to explain it to others:**
“Testing means proving the app still works after each change, not just at the very end.”

---

### Anda — Infrastructure & DevOps Support
**Task:** Support the environment, deployment readiness, and operational reliability.

**How to do it:**
1. Make sure the app can be deployed reliably.
2. Set up container and environment defaults.
3. Add health checks and runtime observability.
4. Keep local and production-like environments aligned.

**What was done in this repo:**
- Helped align Docker and Compose behavior.
- Added healthcheck-friendly deployment setup.
- Exposed runtime data through metrics and the UI.

**How to explain it to others:**
“Infrastructure work is about making the app easy to run repeatedly, safely, and with visibility into what it’s doing.”

---

## Short version you can say to the team
- **Noel:** optimize the simulation engine.
- **Ian:** make the backend and APIs stable.
- **Vince:** make it runnable, deployable, and monitored.
- **Tim:** secure the app and validate inputs.
- **Aila:** design the UI and style system.
- **Aicka:** render the canvas and vehicles.
- **Mayen:** show analytics and metrics.
- **D’arcy:** handle live Socket.IO communication.
- **Jerzha:** test everything and catch regressions.
- **Anda:** support infrastructure and reliability.

## Files to point to when explaining the work
- `simulation.py` — core simulation logic and profiling
- `app.py` — Flask routes and Socket.IO server
- `socketio_utils.py` — event batching and rate limiting
- `templates/index.html` — UI, canvas, log rendering, metrics panel
- `static/css/stardew_v2.css` — theme and layout polish
- `benchmarks/algorithm_bench.py` — deterministic performance benchmark
- `security_utils.py` — validation and security helpers

## Final note
If you want to explain the work simply, say this:

> “Each teammate owned one slice of the app — simulation, backend, UI, security, testing, or infrastructure — and we tied everything together with live updates, metrics, Docker, and tests so the app could run cleanly end to end.”
