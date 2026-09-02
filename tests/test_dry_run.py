from server.dry_run import build_dry_run, format_dry_run
from server.sync_engine import FileState, sha256_text


def state(path, content):
    return FileState(path, sha256_text(content), content)


def test_dry_run_reports_plan_without_mutation():
    local = {"a.yaml": state("a.yaml", "local\n")}
    remote = {"a.yaml": state("a.yaml", "remote\n")}
    baseline = {"a.yaml": sha256_text("base\n")}
    before = (local["a.yaml"].content, remote["a.yaml"].content)
    report = build_dry_run(local, remote, baseline)
    assert report.mutations is False
    assert report.actions[0].action == "conflict"
    assert (local["a.yaml"].content, remote["a.yaml"].content) == before


def test_dry_run_output_is_explicit():
    report = build_dry_run({"a": state("a", "x")}, {}, {})
    text = format_dry_run(report)
    assert "mutations=false" in text
    assert "push: a" in text
