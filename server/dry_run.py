from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .sync_engine import FileState, SyncAction, plan_sync


@dataclass(frozen=True)
class DryRunReport:
    actions: tuple[SyncAction, ...]
    mutations: bool = False

    @property
    def conflicts(self) -> tuple[SyncAction, ...]:
        return tuple(a for a in self.actions if a.action == "conflict")


def build_dry_run(
    local: Mapping[str, FileState],
    remote: Mapping[str, FileState],
    baseline: Mapping[str, str],
) -> DryRunReport:
    """Calculate the exact sync plan without performing any mutation."""
    return DryRunReport(tuple(plan_sync(local, remote, baseline)))


def format_dry_run(report: DryRunReport) -> str:
    lines = [f"dry-run: {len(report.actions)} actions; mutations=false"]
    for action in report.actions:
        lines.append(f"{action.action}: {action.path} ({action.reason})")
    return "\n".join(lines)
