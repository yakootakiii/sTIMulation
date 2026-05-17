"""
Cache Configuration
Separates cache rules from business logic.
"""

# Cache TTL (Time-To-Live) expiration rules in seconds — must be whole integers
CACHE_RULES = {
    "vehicles":  1,    # was 0.5 — Redis requires integers
    "metrics":   1,    # was 1.0
    "status":    2,    # was 2.0
    "config":   10,    # was 10.0
}

# Redis connection config
CACHE_CONFIG = {
    "CACHE_TYPE":            "RedisCache",
    "CACHE_REDIS_URL":       "redis://redis:6379",
    "CACHE_DEFAULT_TIMEOUT":  5,
    "CACHE_KEY_PREFIX":      "stim_",
}

# Fallback to simple in-memory cache if Redis is unavailable
FALLBACK_CONFIG = {
    "CACHE_TYPE":            "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT":  5,
}