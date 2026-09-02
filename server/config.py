from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PROTECTED_EXCLUSIONS = (
    ".storage/", ".cloud/", ".ssh/", ".cache/", "backups/", "tts/", "media/",
    "*.db", "*.sqlite*", "*.log", "*.pem", "*.key", "*.p12", "*.pfx", "secrets.yaml",
)


@dataclass(frozen=True)
class BridgeConfig:
    repository: str = "nicofroeba16-cell/ha-grok-bridge"
    branch: str = "main"
    backup_retention: int = 10
    github_retries: int = 3
    retry_backoff_seconds: float = 0.5
    poll_seconds: float = 3.0
    lock_stale_seconds: int = 300
    exclusions: tuple[str, ...] = field(default_factory=lambda: PROTECTED_EXCLUSIONS)

    def validate(self) -> "BridgeConfig":
        if not self.repository or "/" not in self.repository:
            raise ValueError("repository must be owner/name")
        if not self.branch or any(ch in self.branch for ch in " \t\n"):
            raise ValueError("branch must be a non-empty git ref")
        if not 1 <= self.backup_retention <= 1000:
            raise ValueError("backup_retention must be between 1 and 1000")
        if not 1 <= self.github_retries <= 10:
            raise ValueError("github_retries must be between 1 and 10")
        if not 0.05 <= self.retry_backoff_seconds <= 60:
            raise ValueError("retry_backoff_seconds must be between 0.05 and 60")
        if not 0.1 <= self.poll_seconds <= 300:
            raise ValueError("poll_seconds must be between 0.1 and 300")
        if not 1 <= self.lock_stale_seconds <= 86400:
            raise ValueError("lock_stale_seconds must be between 1 and 86400")
        normalized = tuple(dict.fromkeys(self.exclusions))
        missing = [item for item in PROTECTED_EXCLUSIONS if item not in normalized]
        if missing:
            raise ValueError("mandatory protected exclusions cannot be removed")
        return BridgeConfig(
            repository=self.repository,
            branch=self.branch,
            backup_retention=self.backup_retention,
            github_retries=self.github_retries,
            retry_backoff_seconds=self.retry_backoff_seconds,
            poll_seconds=self.poll_seconds,
            lock_stale_seconds=self.lock_stale_seconds,
            exclusions=normalized,
        )

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "BridgeConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown configuration keys: {', '.join(unknown)}")
        values = dict(data)
        if "exclusions" in values:
            values["exclusions"] = tuple(str(x) for x in values["exclusions"])
        return cls(**values).validate()

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        exclusions = tuple(x for x in os.environ.get("HA_EXCLUSIONS", "").split(",") if x) or PROTECTED_EXCLUSIONS
        return cls(
            repository=os.environ.get("GITHUB_REPOSITORY", cls.repository),
            branch=os.environ.get("GITHUB_BRANCH", cls.branch),
            backup_retention=int(os.environ.get("HA_BACKUP_RETENTION", cls.backup_retention)),
            github_retries=int(os.environ.get("GITHUB_RETRIES", cls.github_retries)),
            retry_backoff_seconds=float(os.environ.get("HA_RETRY_BACKOFF", cls.retry_backoff_seconds)),
            poll_seconds=float(os.environ.get("BRIDGE_POLL_SECONDS", cls.poll_seconds)),
            lock_stale_seconds=int(os.environ.get("HA_LOCK_STALE_SECONDS", cls.lock_stale_seconds)),
            exclusions=exclusions,
        ).validate()

    @classmethod
    def load_json(cls, path: str | Path) -> "BridgeConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("configuration root must be an object")
        return cls.from_mapping(data)
