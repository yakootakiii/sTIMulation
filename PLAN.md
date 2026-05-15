"Analyze the simulation.py file of the sTIMulation project to identify and resolve the following unique technical issues identified during quality assurance reviews:
1. Simulation Logic & Vehicle Behavior
Spawn Position Errors: Vehicles currently spawn at the intersection center rather than road entry points because the Vehicle dataclass lacks a spawn offset
.
Collision & Headway: The system lacks collision detection and headway guards. In rush-hour mode, vehicles overlap and 'clip' through each other because the inter-arrival time is shorter than the clearance time
.
Signal Compliance & RTOR: Correct the logic where vehicles ignore red lights during high-traffic transitions
. Additionally, the Right-Turn-On-Red (RTOR) logic incorrectly triggers during the yellow phase; it must be restricted to red only
.
Queue Drainage: Address the 'incomplete drainage' bug where _release_queues only runs at the start of a green phase. Vehicles arriving mid-green must not be forced to wait for an entire new cycle
.
Teleportation & Exit Logic: Eliminate vehicle 'teleportation' at the front of queues and implement exit corridors so vehicles do not vanish abruptly upon clearing the intersection
.
2. Concurrency, Threading, and SimPy Logic
Sequential Spawning Bug: Fix the _direction_spawner which uses yield from instead of env.process(). This causes vehicle generation to run sequentially across directions rather than independently and concurrently
.
Race Conditions & Deadlocks: Resolve the race condition in _move_vehicle where an early return (if a vehicle ID is missing) can leave the intersection in a permanent 'frozen' state, stalling all subsequent releases
.
Thread Safety: The vehicles and queues dictionaries are accessed by Flask threads and the SimPy thread simultaneously. Implement proper locking (RLock) or deep copies in get_vehicles() and get_stats() to prevent "dictionary changed size during iteration" errors
.
3. System Integrity & Code Quality
Continuous Memory Leak: Remove or prune the _wait_times list, which grows unboundedly every time a vehicle clears the intersection but is never read or cleared
.
State Management: Fix the 'stale state' window where vehicles remain marked as 'queued' in the system even after they have been dequeued but before movement begins
.
Configuration Timing: Document or fix the delay where update_config changes do not take effect until the currently running phase completes
.
Geometric Inconsistencies: Correct the getQueuePos logic which appears to mix left-hand and right-hand traffic conventions
.
Code Cleanup: Remove unused imports such as math and asdict to improve maintainability
.
Please prioritize fixes for the Critical and High-severity bugs involving memory leaks, deadlocks, and sequential spawning."