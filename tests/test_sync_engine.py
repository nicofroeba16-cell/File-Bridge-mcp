import asyncio

from server.sync_engine import FileState, execute_plan, plan_sync, sha256_text


def state(path, content):
    return FileState(path, sha256_text(content), content)


def test_local_change_pushes_and_remote_change_pulls():
    local = {"a.yaml": state("a.yaml", "local\n"), "b.yaml": state("b.yaml", "old-local\n")}
    remote = {"a.yaml": state("a.yaml", "old\n"), "b.yaml": state("b.yaml", "remote\n")}
    baseline = {"a.yaml": sha256_text("old\n"), "b.yaml": sha256_text("old-local\n")}
    plan = plan_sync(local, remote, baseline)
    assert [(x.action, x.path) for x in plan] == [("push", "a.yaml"), ("pull", "b.yaml")]


def test_both_changed_is_conflict():
    local = {"a": state("a", "local")}
    remote = {"a": state("a", "remote")}
    plan = plan_sync(local, remote, {"a": sha256_text("base")})
    assert plan == [plan[0]]
    assert plan[0].action == "conflict"


def test_new_and_deleted_files():
    local = {"new-local": state("new-local", "x"), "deleted-local": None}
    local = {k: v for k, v in local.items() if v is not None}
    remote = {"new-remote": state("new-remote", "y")}
    plan = plan_sync(local, remote, {"deleted-local": sha256_text("gone")})
    by_path = {x.path: x.action for x in plan}
    assert by_path["new-local"] == "push"
    assert by_path["new-remote"] == "pull"
    assert by_path["deleted-local"] == "delete_local"


def test_initial_sync_same_file_is_noop_and_dual_new_is_conflict():
    local = {"same": state("same", "x"), "both": state("both", "local")}
    remote = {"same": state("same", "x"), "both": state("both", "remote")}
    plan = plan_sync(local, remote, {})
    by_path = {x.path: x.action for x in plan}
    assert by_path["same"] == "noop"
    assert by_path["both"] == "conflict"


def test_dry_run_does_not_mutate():
    class Fake:
        def __init__(self, items): self.items = dict(items); self.calls = []
        async def inventory(self): return self.items
        async def write(self, path, content): self.calls.append(("write", path))
        async def delete(self, path): self.calls.append(("delete", path))

    local = Fake({"a": state("a", "new")})
    remote = Fake({"a": state("a", "old")})
    plan = plan_sync(local.items, remote.items, {"a": sha256_text("old")})
    asyncio.run(execute_plan(plan, local, remote, dry_run=True))
    assert local.calls == [] and remote.calls == []
