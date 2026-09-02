from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from server.atomic_deploy import AtomicWorkspaceDeployer, DeploymentFile, validate_deployment


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_validate_all_files_before_staging(tmp_path: Path):
    with pytest.raises(ValueError, match="secret"):
        validate_deployment([
            DeploymentFile("ok.yaml", "ok: true\n"),
            DeploymentFile("secrets.yaml", "token: abc\n"),
        ])
    assert not list(tmp_path.iterdir())


def test_atomic_workspace_deploys_multiple_files(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("old-a\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    result = AtomicWorkspaceDeployer(tmp_path).apply([
        DeploymentFile("a.yaml", "new-a\n", sha("old-a\n")),
        DeploymentFile("b.yaml", "new-b\n", sha("old-b\n")),
    ])
    assert result.verified is True
    assert result.rolled_back is False
    assert (tmp_path / "a.yaml").read_text() == "new-a\n"
    assert (tmp_path / "b.yaml").read_text() == "new-b\n"


def test_sha_conflict_prevents_any_change(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("current\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    with pytest.raises(ValueError, match="sha256 conflict"):
        AtomicWorkspaceDeployer(tmp_path).apply([
            DeploymentFile("a.yaml", "new-a\n", sha("stale\n")),
            DeploymentFile("b.yaml", "new-b\n", sha("old-b\n")),
        ])
    assert (tmp_path / "a.yaml").read_text() == "current\n"
    assert (tmp_path / "b.yaml").read_text() == "old-b\n"


def test_mid_deployment_failure_rolls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    (tmp_path / "a.yaml").write_text("old-a\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    original_replace = __import__("os").replace
    calls = {"n": 0}

    def failing_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated deployment failure")
        return original_replace(src, dst)

    monkeypatch.setattr("os.replace", failing_replace)
    with pytest.raises(OSError, match="simulated deployment failure"):
        AtomicWorkspaceDeployer(tmp_path).apply([
            DeploymentFile("a.yaml", "new-a\n"),
            DeploymentFile("b.yaml", "new-b\n"),
        ])
    assert (tmp_path / "a.yaml").read_text() == "old-a\n"
    assert (tmp_path / "b.yaml").read_text() == "old-b\n"
