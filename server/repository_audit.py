from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .secret_audit import audit_files
from .secret_scanner import SECRET_FILE_NAMES, SECRET_SUFFIXES


@dataclass(frozen=True)
class RepositoryAudit:
    tracked_files: tuple[str, ...]
    protected_tracked: tuple[str, ...]
    secret_findings: tuple[dict[str, object], ...]
    history_protected: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not self.protected_tracked and not self.secret_findings and not self.history_protected


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout


def _is_protected(path: str) -> bool:
    parts = path.split("/")
    if any(part in {".storage", ".cloud", ".ssh", ".cache", "backups", "tts", "media"} for part in parts):
        return True
    name = parts[-1]
    return name in SECRET_FILE_NAMES or any(name.lower().endswith(suffix) for suffix in SECRET_SUFFIXES) or name.lower().endswith((".db", ".sqlite", ".sqlite3", ".log"))


def audit_repository(root: str | Path) -> RepositoryAudit:
    repo = Path(root).resolve()
    tracked = tuple(x for x in _git(repo, "ls-files").splitlines() if x)
    protected = tuple(x for x in tracked if _is_protected(x))
    contents: dict[str, str] = {}
    for path in tracked:
        if _is_protected(path):
            continue
        file_path = repo / path
        try:
            contents[path] = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    findings = audit_files(contents)
    history_objects = _git(repo, "rev-list", "--objects", "--all").splitlines()
    history_paths = tuple(sorted({line.split(" ", 1)[1] for line in history_objects if " " in line and _is_protected(line.split(" ", 1)[1])}))
    report = tuple({"kind": f.kind, "path": f.path, "line": f.line} for f in findings)
    return RepositoryAudit(tracked, protected, report, history_paths)
