from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class BridgeStatus:
    state: str = "idle"
    last_success: str | None = None
    last_failure: str | None = None
    conflict_count: int = 0
    lock_held: bool = False
    message: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StatusStore:
    """Small atomic JSON health/state store with crash-safe replacement."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> BridgeStatus:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return BridgeStatus(**{k: data[k] for k in BridgeStatus.__dataclass_fields__ if k in data})
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return BridgeStatus()

    def save(self, status: BridgeStatus) -> BridgeStatus:
        status.updated_at = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(status), fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return status

    def update(self, **changes: object) -> BridgeStatus:
        status = self.load()
        for key, value in changes.items():
            if key not in BridgeStatus.__dataclass_fields__:
                raise ValueError(f"unknown status field: {key}")
            setattr(status, key, value)
        return self.save(status)

    def mark_success(self, message: str | None = None) -> BridgeStatus:
        return self.update(state="ok", last_success=datetime.now(timezone.utc).isoformat(), message=message)

    def mark_failure(self, message: str) -> BridgeStatus:
        return self.update(state="error", last_failure=datetime.now(timezone.utc).isoformat(), message=message)
