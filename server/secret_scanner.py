from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

SECRET_FILE_NAMES = {"secrets.yaml", "secrets.yml", ".env"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

@dataclass(frozen=True)
class SecretFinding:
    kind: str
    path: str
    line: int | None = None

def scan_path(path: str) -> SecretFinding | None:
    p = PurePosixPath(path)
    if p.name in SECRET_FILE_NAMES or p.suffix.lower() in SECRET_SUFFIXES:
        return SecretFinding("protected-secret-file", path)
    return None

def scan_text(path: str, content: str) -> list[SecretFinding]:
    finding = scan_path(path)
    if finding:
        return [finding]
    out: list[SecretFinding] = []
    for line_no, line in enumerate(content.splitlines(), 1):
        if any(pattern.search(line) for pattern in PATTERNS):
            out.append(SecretFinding("secret-pattern", path, line_no))
    return out

def assert_safe(path: str, content: str) -> None:
    findings = scan_text(path, content)
    if findings:
        f = findings[0]
        location = f"{f.path}:{f.line}" if f.line else f.path
        raise ValueError(f"secret scan blocked: {f.kind} at {location}")
