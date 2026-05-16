"""SocketIO event batching and rate limiting utilities."""
import time
import threading
from collections import deque
from typing import Dict, Callable, Optional


class EventBatcher:
    """Batches Socket.IO events and emits them at intervals to reduce overhead."""
    
    def __init__(self, batch_size: int = 10, flush_interval: float = 0.05):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches: Dict[str, deque] = {}
        self.last_flush = time.monotonic()
        self.emit_fn: Optional[Callable[[str, dict], None]] = None
        self._lock = threading.Lock()
    
    def add(self, event_type: str, data: dict):
        """Add an event to the batch."""
        with self._lock:
            if event_type not in self.batches:
                self.batches[event_type] = deque()

            self.batches[event_type].append(data)

            # Flush if batch is full
            if len(self.batches[event_type]) >= self.batch_size:
                # call flush without holding the lock to avoid re-entrancy
                pass

        # perform flush outside lock
        if len(self.batches.get(event_type, ())) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Emit all batched events."""
        # Snapshot and clear under lock, then emit without holding the lock
        if not self.emit_fn:
            return

        with self._lock:
            snapshot = {k: list(v) for k, v in self.batches.items() if v}
            self.batches.clear()
            self.last_flush = time.monotonic()

        for event_type, events in snapshot.items():
            payload = {
                "type": event_type,
                "events": events,
                "count": len(events),
            }
            try:
                self.emit_fn("events_batch", payload)
            except Exception:
                # never allow an emit failure to crash the batcher
                pass
    
    def should_flush(self) -> bool:
        """Check if enough time has elapsed to flush."""
        return (time.monotonic() - self.last_flush) >= self.flush_interval

    def flush_if_due(self):
        """Flush only when the flush interval has elapsed."""
        if self.should_flush():
            self.flush()


class RateLimiter:
    """Simple rate limiter per event type."""
    
    def __init__(self, max_per_second: int = 100):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.last_emit: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def allow(self, event_type: str) -> bool:
        """Check if event should be emitted."""
        now = time.monotonic()
        with self._lock:
            last = self.last_emit.get(event_type, 0.0)

            if (now - last) >= self.min_interval:
                self.last_emit[event_type] = now
                return True

            return False
