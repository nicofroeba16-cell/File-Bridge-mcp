import pytest

from server.conflict_resolution import conflicts_from_plan, resolve_conflict, verify_resolution
from server.sync_engine import FileState, plan_sync, sha256_text


def state(path, content):
    return FileState(path, sha256_text(content), content)


def test_conflict_details_and_explicit_local_resolution():
    local = {"a": state("a", "local")}
    remote = {"a": state("a", "remote")}
    baseline = {"a": sha256_text("base")}
    plan = plan_sync(local, remote, baseline)
    conflicts = conflicts_from_plan(plan, local, remote, baseline)
    assert len(conflicts) == 1
    assert conflicts[0].path == "a"
    action = resolve_conflict(conflicts[0], local, remote, "local")
    assert (action.action, action.path) == ("push", "a")


def test_explicit_remote_resolution():
    local = {"a": state("a", "local")}
    remote = {"a": state("a", "remote")}
    conflict = conflicts_from_plan(
        plan_sync(local, remote, {"a": sha256_text("base")}), local, remote, {"a": sha256_text("base")}
    )[0]
    action = resolve_conflict(conflict, local, remote, "remote")
    assert (action.action, action.path) == ("pull", "a")


def test_invalid_resolution_is_rejected():
    local = {"a": state("a", "local")}
    remote = {"a": state("a", "remote")}
    conflict = conflicts_from_plan(
        plan_sync(local, remote, {"a": sha256_text("base")}), local, remote, {"a": sha256_text("base")}
    )[0]
    with pytest.raises(ValueError, match="local.*remote"):
        resolve_conflict(conflict, local, remote, "merge")


def test_resolution_never_mutates_and_verification_is_hash_based():
    local = {"a": state("a", "local")}
    remote = {"a": state("a", "remote")}
    before = (local["a"].content, remote["a"].content)
    conflict = conflicts_from_plan(
        plan_sync(local, remote, {"a": sha256_text("base")}), local, remote, {"a": sha256_text("base")}
    )[0]
    resolve_conflict(conflict, local, remote, "local")
    assert (local["a"].content, remote["a"].content) == before
    assert verify_resolution(local["a"], "local")
    assert not verify_resolution(local["a"], "tampered")
