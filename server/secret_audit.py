from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

try:
    from .secret_scanner import SecretFinding, scan_text
except ImportError:
    from secret_scanner import SecretFinding, scan_text


@dataclass(frozen=True)
class AuditResult:
    findings: tuple[SecretFinding, ...]

    @property
    def clean(self) -> bool:
        return not self.findings


def audit_files(files: Mapping[str, str], *, ignored_paths: Iterable[str] = ()) -> AuditResult:
    """Audit already-versioned/tracked text files without exposing their contents."""
    ignored = set(ignored_paths)
    findings: list[SecretFinding] = []
    for path, content in sorted(files.items()):
        if path in ignored:
            continue
        findings.extend(scan_text(path, content))
    return AuditResult(tuple(findings))


def safe_audit_report(result: AuditResult) -> dict[str, object]:
    """Return only metadata; secret values are never included in reports/logs."""
    return {"clean": result.clean, "finding_count": len(result.findings), "findings": [{"kind": f.kind, "path": f.path, "line": f.line} for f in result.findings]}


def assert_repository_clean(files: Mapping[str, str]) -> None:
    result = audit_files(files)
    if not result.clean:
        first = result.findings[0]
        location = f"{first.path}:{first.line}" if first.line else first.path
        raise ValueError(f"repository secret audit failed: {first.kind} at {location}")
