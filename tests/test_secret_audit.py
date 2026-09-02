from server.secret_audit import audit_files, safe_audit_report, assert_repository_clean


def test_audit_detects_already_versioned_secret_without_value_leak():
    result = audit_files({"configuration.yaml": "api_key: abcdefghijklmnop\n"})
    assert not result.clean
    report = safe_audit_report(result)
    assert report["finding_count"] == 1
    assert "abcdefghijklmnop" not in str(report)


def test_audit_detects_protected_secret_filename():
    result = audit_files({"secrets.yaml": "token: value\n"})
    assert not result.clean
    assert result.findings[0].kind == "protected-secret-file"


def test_clean_repository_passes():
    files = {"configuration.yaml": "homeassistant:\n  name: Test\n"}
    assert audit_files(files).clean
    assert_repository_clean(files) is None
