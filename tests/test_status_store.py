from __future__ import annotations

import json
from pathlib import Path

from server.status_store import BridgeStatus, StatusStore


def test_status_store_round_trip_and_atomic_json(tmp_path: Path):
    path = tmp_path / "health" / "status.json"
    store = StatusStore(path)
    status = store.mark_success("sync complete")
    assert status.state == "ok"
    assert status.last_success is not None
    loaded = store.load()
    assert loaded.state == "ok"
    assert loaded.message == "sync complete"
    assert json.loads(path.read_text()) ["state"] == "ok"


def test_status_store_failure_and_conflict_count(tmp_path: Path):
    store = StatusStore(tmp_path / "status.json")
    store.update(conflict_count=2, lock_held=True)
    status = store.mark_failure("network unavailable")
    assert status.state == "error"
    assert status.last_failure is not None
    assert status.conflict_count == 2
    assert status.lock_held is True


def test_unknown_status_field_is_rejected(tmp_path: Path):
    store = StatusStore(tmp_path / "status.json")
    try:
        store.update(not_a_field=True)
    except ValueError as exc:
        assert "unknown status field" in str(exc)
    else:
        raise AssertionError("unknown field accepted")


def test_default_status_is_safe_when_file_is_corrupt(tmp_path: Path):
    path = tmp_path / "status.json"
    path.write_text("not-json")
    status = StatusStore(path).load()
    assert isinstance(status, BridgeStatus)
    assert status.state == "idle"
