from server.sync_engine import FileState, plan_sync, sha256_text


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
    assert plan[0].action == "conflict"


def test_new_and_deleted_files():
    local = {"new-local": state("new-local", "x")}
    remote = {"new-remote": state("new-remote", "y"), "deleted-local": state("deleted-local", "gone")}
    plan = plan_sync(local, remote, {"deleted-local": sha256_text("gone")})
    by_path = {x.path: x.action for x in plan}
    assert by_path["new-local"] == "push"
    assert by_path["new-remote"] == "pull"
    assert by_path["deleted-local"] == "delete_remote"


def test_remote_deletion_is_delete_local_when_local_matches_baseline():
    local = {"deleted-remote": state("deleted-remote", "gone")}
    remote = {}
    plan = plan_sync(local, remote, {"deleted-remote": sha256_text("gone")})
    by_path = {x.path: x.action for x in plan}
    assert by_path["deleted-remote"] == "delete_local"


def test_initial_sync_same_file_is_noop_and_dual_new_is_conflict():
    local = {"same": state("same", "x"), "both": state("both", "local")}
    remote = {"same": state("same", "x"), "both": state("both", "remote")}
    plan = plan_sync(local, remote, {})
    by_path = {x.path: x.action for x in plan}
    assert by_path["same"] == "noop"
    assert by_path["both"] == "conflict"
