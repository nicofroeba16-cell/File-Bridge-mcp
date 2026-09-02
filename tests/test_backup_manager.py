import json
from pathlib import Path

import pytest

from server.backup_manager import BackupManager


def test_snapshot_restore_and_hash_verification(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    target = root / "configuration.yaml"
    target.write_text("homeassistant:\n  name: Test\n", encoding="utf-8")
    manager = BackupManager(root, retention=3)

    snapshot = manager.create({"configuration.yaml": str(target)})
    target.write_text("broken: true\n", encoding="utf-8")
    restored = manager.restore(snapshot.backup_id)

    assert restored.files == snapshot.files
    assert target.read_text(encoding="utf-8") == "homeassistant:\n  name: Test\n"


def test_corrupt_snapshot_is_rejected(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    target = root / "a.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    manager = BackupManager(root, retention=3)
    snapshot = manager.create({"a.yaml": str(target)})
    (manager.backup_root / snapshot.backup_id / "a.yaml").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        manager.restore(snapshot.backup_id)


def test_retention_keeps_newest_snapshots(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    target = root / "a.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    manager = BackupManager(root, retention=2)
    ids = []
    for value in ("1", "2", "3"):
        target.write_text(f"a: {value}\n", encoding="utf-8")
        ids.append(manager.create({"a.yaml": str(target)}).backup_id)
    assert len(manager.list()) == 2
    assert ids[-1] in manager.list()
    assert ids[0] not in manager.list()


def test_snapshot_manifest_is_deterministic_and_complete(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    a = root / "a.yaml"
    b = root / "nested" / "b.yaml"
    b.parent.mkdir()
    a.write_text("a: 1\n", encoding="utf-8")
    b.write_text("b: 2\n", encoding="utf-8")
    manager = BackupManager(root, retention=5)
    snapshot = manager.create({"nested/b.yaml": str(b), "a.yaml": str(a)})
    manifest = json.loads((manager.backup_root / snapshot.backup_id / "manifest.json").read_text(encoding="utf-8"))
    assert list(manifest["files"]) == ["a.yaml", "nested/b.yaml"]
    assert set(manifest["files"]) == {"a.yaml", "nested/b.yaml"}
