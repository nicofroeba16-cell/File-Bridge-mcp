from __future__ import annotations

import subprocess
from pathlib import Path

from server.repository_audit import audit_repository


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def test_repository_audit_tracks_inventory_and_secrets(tmp_path: Path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Audit Test")
    (tmp_path / "configuration.yaml").write_text("safe: true\n")
    (tmp_path / "bad.yaml").write_text("api_key: abcdefghijk\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "initial")
    report = audit_repository(tmp_path)
    assert "configuration.yaml" in report.tracked_files
    assert any(item["path"] == "bad.yaml" for item in report.secret_findings)
    assert report.clean is False


def test_repository_audit_detects_protected_history(tmp_path: Path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Audit Test")
    (tmp_path / "configuration.yaml").write_text("safe: true\n")
    (tmp_path / "old.log").write_text("old log\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "history artifact")
    report = audit_repository(tmp_path)
    assert "old.log" in report.protected_tracked
    assert "old.log" in report.history_protected
