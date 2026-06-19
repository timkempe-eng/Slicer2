"""Per-IP rate limiting, backed by Redis.

Fixed-window counters keyed by client IP. Enforced only when ``REDIS_URL`` is
configured; **fails open** (allows the request) when Redis is absent or errors,
so a Redis hiccup never takes the API down. The client IP comes from Caddy's
``X-Forwarded-For`` (left-most hop).
"""
from __future__ import annotations

import time

from fastapi import HTTPException, Request

from . import config

_redis = None


def _client():
    global _redis
    if _redis is None and config.REDIS_URL:
        from redis import Redis

        _redis = Redis.from_url(config.REDIS_URL, socket_timeout=1)
    return _redis


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, name: str, limit: int, window_seconds: int) -> None:
    """Raise 429 if this IP exceeded ``limit`` requests in the current window."""
    if limit <= 0:
        return
    r = _client()
    if r is None:
        return  # no Redis (dev) -> no limiting
    ip = client_ip(request)
    bucket = int(time.time() // window_seconds)
    key = f"rl:{name}:{ip}:{bucket}"
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)
    except Exception:
        return  # fail open on any Redis error
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests — please slow down and try again shortly.",
            headers={"Retry-After": str(window_seconds)},
        )
