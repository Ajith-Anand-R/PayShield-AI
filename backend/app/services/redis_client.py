import os
import time
# `redis` is optional: if not installed, MemoryRedis is used automatically.
try:
    import redis as _redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _redis_lib = None  # type: ignore
    _REDIS_AVAILABLE = False


_client = None

class MemoryRedis:
    def __init__(self):
        self._store = {}
        self._expiry = {}
    
    def _purge(self, key):
        expires_at = self._expiry.get(key)
        if expires_at and time.time() >= expires_at:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
    
    def get(self, key):
        self._purge(key)
        return self._store.get(key)
    
    def setex(self, key, ttl, value):
        self._store[key] = str(value)
        self._expiry[key] = time.time() + ttl
    
    def incr(self, key):
        self._purge(key)
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val
    
    def expire(self, key, ttl):
        self._expiry[key] = time.time() + ttl

def get_redis():
    global _client
    if _client is None:
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            redis_url = "redis://localhost:6379"

        if redis_url.startswith("memory://") or redis_url == "memory":
            print("[PayShield] Using configured in-memory Redis client.")
            _client = MemoryRedis()
        elif not _REDIS_AVAILABLE:
            print("[PayShield] `redis` package not installed. Falling back to in-memory Redis client.")
            _client = MemoryRedis()
        else:
            try:
                client_candidate = _redis_lib.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
                client_candidate.ping()
                _client = client_candidate
                print("[PayShield] Successfully connected to Redis.")
            except Exception as e:
                print(f"[PayShield] Redis connection failed to {redis_url} ({e}). Falling back to in-memory Redis client.")
                _client = MemoryRedis()
    return _client


def increment_txn_count(user_id: str) -> int:
    r = get_redis()
    key = f"user:{user_id}:txn_count_1h"
    count = r.incr(key)
    r.expire(key, 3600)
    return count

def get_txn_count(user_id: str) -> int:
    r = get_redis()
    key = f"user:{user_id}:txn_count_1h"
    val = r.get(key)
    return int(val) if val else 0

def set_last_ip(user_id: str, ip: str):
    r = get_redis()
    r.setex(f"user:{user_id}:last_ip", 3600, ip)

def get_last_ip(user_id: str) -> str:
    r = get_redis()
    return r.get(f"user:{user_id}:last_ip") or ""
