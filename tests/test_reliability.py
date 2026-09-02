import asyncio
import time

import pytest

from server.reliability import LeaseLock, retry_async


def test_lock_blocks_second_owner_and_releases(tmp_path):
    path = tmp_path / ".sync.lock"
    first = LeaseLock(path, stale_after=60)
    second = LeaseLock(path, stale_after=60)
    first.acquire()
    with pytest.raises(RuntimeError, match="already held"):
        second.acquire()
    first.release()
    second.acquire()
    second.release()


def test_stale_lock_is_recovered(tmp_path):
    path = tmp_path / ".sync.lock"
    old = LeaseLock(path, stale_after=1)
    old.acquire()
    data = path.read_text(encoding="utf-8").replace(str(time.time()), "0")
    path.write_text('{"owner":"dead","acquired_at":0}', encoding="utf-8")
    current = LeaseLock(path, stale_after=1)
    current.acquire()
    current.release()


def test_wrong_owner_cannot_release(tmp_path):
    path = tmp_path / ".sync.lock"
    first = LeaseLock(path, stale_after=60)
    second = LeaseLock(path, stale_after=60)
    first.acquire()
    with pytest.raises(RuntimeError, match="another process"):
        second.release()
    first.release()


def test_retry_async_retries_then_succeeds():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("temporary")
        return "ok"

    assert asyncio.run(retry_async(operation, attempts=3, base_delay=0)) == "ok"
    assert calls == 3


def test_retry_async_does_not_retry_non_retryable():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        asyncio.run(retry_async(operation, attempts=5, base_delay=0, retryable=lambda exc: isinstance(exc, ConnectionError)))
    assert calls == 1
