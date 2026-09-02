from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .sync_engine import FileState, SyncAction, sha256_text


@dataclass(frozen=True)
class Conflict:
    path: str
    local_sha256: str | None
    remote_sha256: str | None
    baseline_sha256: str | None
    reason: str


def conflicts_from_plan(
    plan: Iterable[SyncAction],
    local: Mapping[str, FileState],
    remote: Mapping[str, FileState],
    baseline: Mapping[str, str],
) -> list[Conflict]:
    result: list[Conflict] = []
    for action in plan:
        if action.action != "conflict":
            continue
        result.append(
            Conflict(
                path=action.path,
                local_sha256=local.get(action.path).sha256 if local.get(action.path) else None,
                remote_sha256=remote.get(action.path).sha256 if remote.get(action.path) else None,
                baseline_sha256=baseline.get(action.path),
                reason=action.reason,
            )
        )
    return result


def resolve_conflict(
    conflict: Conflict,
    local: Mapping[str, FileState],
    remote: Mapping[str, FileState],
    choice: str,
) -> SyncAction:
    if choice not in {"local", "remote"}:
        raise ValueError("conflict resolution must be 'local' or 'remote'")
    source = local if choice == "local" else remote
    target = remote if choice == "local" else local
    source_state = source.get(conflict.path)
    if source_state is None:
        raise ValueError(f"cannot resolve {conflict.path}: selected side is missing")
    if source_state.content is None:
        raise ValueError(f"cannot resolve {conflict.path}: selected content unavailable")
    action = "push" if choice == "local" else "pull"
    if conflict.path not in target:
        reason = f"explicit {choice} resolution creates the missing file"
    else:
        reason = f"explicit {choice} resolution overwrites the other side"
    return SyncAction(action, conflict.path, reason)


def verify_resolution(state: FileState, expected_content: str) -> bool:
    return state.sha256 == sha256_text(expected_content) and state.content == expected_content
