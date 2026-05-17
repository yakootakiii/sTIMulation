
import time
from simulation import TrafficSimulation, SimConfig, Turn

def test_determinism():
    print("Testing simulation determinism...")
    
    seed = 123
    config = SimConfig(seed=seed, speed_factor=10.0) # Run fast
    
    # Run 1
    events1 = []
    def cb1(etype, data):
        if etype == "vehicle_arrive":
            events1.append((data["vid"], data["direction"], data["turn"]))
            
    sim1 = TrafficSimulation(config, event_cb=cb1)
    sim1.start()
    
    # Wait for some vehicles to spawn (simulated time)
    timeout = 10 # real seconds
    start_real = time.time()
    while sim1.env.now < 50 and (time.time() - start_real) < timeout:
        time.sleep(0.1)
    
    sim1.stop()
    print(f"Run 1 spawned {len(events1)} vehicles.")

    # Run 2
    events2 = []
    def cb2(etype, data):
        if etype == "vehicle_arrive":
            events2.append((data["vid"], data["direction"], data["turn"]))
            
    sim2 = TrafficSimulation(config, event_cb=cb2)
    sim2.start()
    
    start_real = time.time()
    while sim2.env.now < 50 and (time.time() - start_real) < timeout:
        time.sleep(0.1)
        
    sim2.stop()
    print(f"Run 2 spawned {len(events2)} vehicles.")

    # Compare
    assert len(events1) > 0, "No vehicles spawned in Run 1"
    assert events1 == events2, f"Runs differ!\nRun 1: {events1}\nRun 2: {events2}"
    
    print("✅ Determinism test passed! Both runs produced identical vehicle sequences.")

if __name__ == "__main__":
    test_determinism()
