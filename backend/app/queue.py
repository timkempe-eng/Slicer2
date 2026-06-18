"""Task-queue seam.

When ``REDIS_URL`` is set, ``enqueue`` pushes the job onto an RQ queue that a
separate ``rq worker`` process drains (production). Otherwise the callable runs
inline, synchronously, in the web process — fine for dev/test and a single
small host, and what keeps the API tests hermetic (no Redis needed).
"""
from __future__ import annotations

from typing import Callable

from . import config

_queue = None


def _get_queue():
    global _queue
    if _queue is None:
        from redis import Redis  # imported lazily so no-Redis dev needs neither
        from rq import Queue

        _queue = Queue(config.RQ_QUEUE, connection=Redis.from_url(config.REDIS_URL))
    return _queue


def enqueue(func: Callable, *args) -> None:
    if config.REDIS_URL:
        _get_queue().enqueue(func, *args)
    else:
        func(*args)
