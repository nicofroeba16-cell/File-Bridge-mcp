import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parents[1] / "server"))
from local_workspace import LocalWorkspace
from security import MAX_TEXT_BYTES, safe_config_path


def test_more_runtime_files_are_protected():
    for bad in ("home.db-wal", "home.sqlite-wal", "home.sqlite-shm", "x.pem", "x.pfx"):
        with pytest.raises(HTTPException):
            safe_config_path(bad)


def test_path_length_is_bounded():
    with pytest.raises(HTTPException):
        safe_config_path("a" * 501)


def test_invalid_utf8_is_rejected(tmp_path):
    ws = LocalWorkspace(tmp_path)
    p = tmp_path / "binary.txt"
    p.write_bytes(b"\xff\xfe")
    with pytest.raises(HTTPException) as exc:
        ws.read("binary.txt")
    assert exc.value.status_code == 415


def test_symlink_is_rejected(tmp_path):
    ws = LocalWorkspace(tmp_path)
    target = tmp_path / "target.yaml"
    target.write_text("ok: true\n", encoding="utf-8")
    (tmp_path / "link.yaml").symlink_to(target)
    with pytest.raises(HTTPException) as exc:
        ws.read("link.yaml")
    assert exc.value.status_code == 403


def test_write_size_limit(tmp_path):
    ws = LocalWorkspace(tmp_path)
    with pytest.raises(HTTPException) as exc:
        ws.write("large.yaml", "x" * (MAX_TEXT_BYTES + 1))
    assert exc.value.status_code == 413


def test_invalid_regex_is_rejected(tmp_path):
    ws = LocalWorkspace(tmp_path)
    (tmp_path / "x.yaml").write_text("value: true\n", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        ws.search("[", regex=True)
    assert exc.value.status_code == 400


def test_backup_ids_remain_unique(tmp_path):
    ws = LocalWorkspace(tmp_path)
    (tmp_path / "x.yaml").write_text("value: true\n", encoding="utf-8")
    first = ws.backup()
    second = ws.backup()
    assert first["backup_id"] != second["backup_id"]
