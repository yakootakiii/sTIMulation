"""Tim's security hardening utilities."""
import re
from functools import wraps
from flask import request, abort


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    if not isinstance(value, str):
        return str(value)[:max_length]
    
    # Remove potentially dangerous characters
    value = re.sub(r'[<>\"\';&]', '', value)
    return value[:max_length]


def validate_config_input(data: dict) -> dict:
    """Validate and sanitize configuration input."""
    valid_keys = {
        "green_duration", "yellow_duration", "red_duration",
        "scenario", "road_type", "right_turn_free", "speed_factor"
    }
    
    validated = {}
    for k, v in data.items():
        if k not in valid_keys:
            continue
        
        if k in ("green_duration", "yellow_duration", "red_duration", "speed_factor"):
            try:
                val = float(v)
                if 0 < val < 300:  # Reasonable bounds
                    validated[k] = val
            except (TypeError, ValueError):
                pass
        elif k == "scenario":
            if v in ("normal", "rush", "low"):
                validated[k] = v
        elif k == "road_type":
            try:
                val = int(v)
                if val in (2, 4, 6):
                    validated[k] = val
            except (TypeError, ValueError):
                pass
        elif k == "right_turn_free":
            validated[k] = bool(v)
    
    return validated


def require_json(f):
    """Decorator to ensure request has JSON content-type."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH"):
            if not request.is_json:
                abort(400)
        return f(*args, **kwargs)
    return decorated_function
