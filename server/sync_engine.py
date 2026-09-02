from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


@dataclass(frozen=True)
class FileState:
    path: str
    sha256: str
    content: str | None = None


@dataclass(frozen=True)
class SyncAction:
    action: str  # push, pull, delete_remote, delete_local, conflict, noop
    path: str
    reason: str


class SyncWorkspace(Protocol):
    async def inventory(self) -> Mapping[str, FileState]: ...
    async def write(self, path: str, content: str) -> None: ...
    async def delete(self, path: str) -> None: ...


class SyncRemote(Protocol):
    async def inventory(self) -> Mapping[str, FileState]: ...
    async def write(self, path: str, content: str) -> None: ...
    async def delete(self, path: str) -> None: ...


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_initial_sync(
    local: Mapping[str, FileState],
    remote: Mapping[str, FileState],
    *,
    direction: str,
) -> list[SyncAction]:
    """Build an explicit first-sync plan; no ambiguous side is chosen implicitly."""
    if direction not in {"ha-to-github", "github-to-ha"}:
        raise ValueError("initial sync direction must be 'ha-to-github' or 'github-to-ha'")
    actions: list[SyncAction] = []
    for path in sorted(set(local) | set(remote)):
        l = local.get(path)
        r = remote.get(path)
        if l is not None and r is not None and l.sha256 == r.sha256:
            actions.append(SyncAction("noop", path, "both sides identical"))
        elif direction == "ha-to-github":
            if l is None:
                actions.append(SyncAction("delete_remote", path, "initial HA-to-GitHub mirror deletion"))
            else:
                actions.append(SyncAction("push", path, "initial HA-to-GitHub mirror"))
        else:
            if r is None:
                actions.append(SyncAction("delete_local", path, "initial GitHub-to-HA mirror deletion"))
            else:
                actions.append(SyncAction("pull", path, "initial GitHub-to-HA mirror"))
    return actions


def plan_sync(
    local: Mapping[str, FileState],
    remote: Mapping[str, FileState],
    baseline: Mapping[str, str],
) -> list[SyncAction]:
    """Build a conservative two-way plan from the last successful sync manifest.

    A file changed on both sides is never overwritten automatically. Missing entries
    in the baseline are treated as an initial-sync case and only auto-resolve when
    one side has the file or both sides have identical content.
    """
    actions: list[SyncAction] = []
    for path in sorted(set(local) | set(remote) | set(baseline)):
        l = local.get(path)
        r = remote.get(path)
        base = baseline.get(path)
        lh = l.sha256 if l else None
        rh = r.sha256 if r else None
        local_changed = lh != base
        remote_changed = rh != base

        if lh == rh and lh is not None:
            actions.append(SyncAction("noop", path, "both sides identical"))
        elif l is not None and r is not None:
            if base is None:
                actions.append(SyncAction("conflict", path, "file exists on both sides without baseline"))
            elif local_changed and remote_changed:
                actions.append(SyncAction("conflict", path, "file changed on both sides"))
            elif local_changed:
                actions.append(SyncAction("push", path, "local changed since last sync"))
            elif remote_changed:
                actions.append(SyncAction("pull", path, "remote changed since last sync"))
            else:
                actions.append(SyncAction("noop", path, "unchanged from baseline"))
        elif l is not None:
            if base is None:
                actions.append(SyncAction("push", path, "new local file"))
            elif local_changed and not remote_changed:
                actions.append(SyncAction("push", path, "remote file deleted; local changed"))
            elif not local_changed and remote_changed:
                actions.append(SyncAction("delete_local", path, "remote deletion"))
            else:
                actions.append(SyncAction("conflict", path, "local/remote deletion conflict"))
        elif r is not None:
            if base is None:
                actions.append(SyncAction("pull", path, "new remote file"))
            elif remote_changed and not local_changed:
                actions.append(SyncAction("pull", path, "local file deleted; remote changed"))
            elif not remote_changed and local_changed:
                actions.append(SyncAction("delete_remote", path, "local deletion"))
            else:
                actions.append(SyncAction("conflict", path, "local/remote deletion conflict"))
        else:
            actions.append(SyncAction("noop", path, "deleted on both sides"))
    return actions


def next_baseline(
    local: Mapping[str, FileState], remote: Mapping[str, FileState], actions: Iterable[SyncAction]
) -> dict[str, str]:
    """Return a manifest only when the action is safely resolved."""
    result: dict[str, str] = {}
    conflicts = {a.path for a in actions if a.action == "conflict"}
    for path in set(local) | set(remote):
        if path in conflicts:
            continue
        state = local.get(path) or remote.get(path)
        if state is not None:
            result[path] = state.sha256
    return dict(sorted(result.items()))


async def execute_plan(
    plan: Iterable[SyncAction],
    workspace: SyncWorkspace,
    remote: SyncRemote,
    *,
    dry_run: bool = False,
) -> list[SyncAction]:
    """Apply a safe plan; conflicts and no-ops are never mutated."""
    actions = list(plan)
    if dry_run:
        return actions
    for action in actions:
        if action.action == "push":
            state = (await workspace.inventory())[action.path]
            if state.content is None:
                raise ValueError(f"local content unavailable: {action.path}")
            await remote.write(action.path, state.content)
        elif action.action == "pull":
            state = (await remote.inventory())[action.path]
            if state.content is None:
                raise ValueError(f"remote content unavailable: {action.path}")
            await workspace.write(action.path, state.content)
        elif action.action == "delete_remote":
            await remote.delete(action.path)
        elif action.action == "delete_local":
            await workspace.delete(action.path)
    return actions
