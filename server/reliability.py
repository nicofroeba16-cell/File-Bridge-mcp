from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class LockInfo:
    owner: str
    acquired_at: float


class LeaseLock:
    """Crash-safe local lease lock with stale-owner recovery."""

    def __init__(self, path: str | Path, stale_after: float = 300.0):
        if stale_after <= 0:
            raise ValueError("stale_after must be positive")
        self.path = Path(path)
        self.stale_after = stale_after
        self.owner = uuid.uuid4().hex

    def _read(self) -> LockInfo | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return LockInfo(str(data["owner"]), float(data["acquired_at"]))
        except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
            return None

    def acquire(self) -> LockInfo:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"owner": self.owner, "acquired_at": time.time()})
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                return LockInfo(self.owner, time.time())
            except FileExistsError:
                info = self._read()
                if info and time.time() - info.acquired_at <= self.stale_after:
                    raise RuntimeError("sync lock is already held")
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    continue
        raise RuntimeError("unable to recover stale sync lock")

    def release(self) -> None:
        info = self._read()
        if info is None:
            return
        if info.owner != self.owner:
            raise RuntimeError("cannot release a lock owned by another process")
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> "LeaseLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.25,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return await operation()
        except Exception as exc:
            last = exc
            if attempt + 1 >= attempts or (retryable and not retryable(exc)):
                raise
            await asyncio.sleep(base_delay * (2**attempt))
    assert last is not None
    raise last
