# API Documentation

## Endpoints

### GET /
Returns the HTML UI.

### GET /api/status
Returns current simulation status (running, paused, stats).

### GET /api/vehicles
Returns list of active vehicles with positions and states.

### GET /api/config
Returns current simulation configuration.

### POST /api/config
Update simulation configuration.

**Payload:**
```json
{
  "green_duration": 20.0,
  "yellow_duration": 4.0,
  "red_duration": 1.0,
  "scenario": "normal",
  "road_type": 4,
  "right_turn_free": true,
  "speed_factor": 1.0
}
```

### GET /api/metrics
Returns aggregated metrics: total_passed, avg_wait, cycles, sim_time, active_vehicles, queues.

## Socket.IO Events

### Client → Server

- `connect` - Client connected
- `cmd_start` - Start simulation
- `cmd_pause` - Pause/resume
- `cmd_reset` - Reset to initial state
- `cmd_update_config` - Update config

### Server → Client

- `stats` - Periodic stats snapshot
- `vehicles_snapshot` - List of vehicles
- `vehicle_arrive` - Vehicle arrived at intersection
- `vehicle_queued` - Vehicle joined queue
- `vehicle_move` - Vehicle cleared intersection
- `vehicle_exit` - Vehicle exited
- `light_change` - Traffic light phase changed
- `log` - Log message
- `reset` - Simulation reset
- `ack` - Command acknowledgment
