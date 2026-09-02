import pytest
from server.secret_scanner import scan_text


def test_secret_filename_blocked():
    assert scan_text("secrets.yaml", "token: harmless")


def test_token_pattern_blocked():
    findings = scan_text("configuration.yaml", "api_key: abcdefghijklmnop")
    assert findings and findings[0].line == 1


def test_normal_config_allowed():
    assert scan_text("configuration.yaml", "homeassistant:\n  name: Home\n") == []
