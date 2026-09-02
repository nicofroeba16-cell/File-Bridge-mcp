from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.config import BridgeConfig, PROTECTED_EXCLUSIONS


def test_default_config_is_valid_and_protected():
    cfg = BridgeConfig().validate()
    assert cfg.repository == "nicofroeba16-cell/ha-grok-bridge"
    assert set(PROTECTED_EXCLUSIONS) <= set(cfg.exclusions)


def test_custom_config_is_normalized():
    cfg = BridgeConfig.from_mapping({"branch": "develop", "backup_retention": 25, "exclusions": list(PROTECTED_EXCLUSIONS) + ["custom/"]})
    assert cfg.branch == "develop"
    assert cfg.backup_retention == 25
    assert "custom/" in cfg.exclusions


def test_mandatory_exclusions_cannot_be_removed():
    with pytest.raises(ValueError, match="mandatory protected exclusions"):
        BridgeConfig.from_mapping({"exclusions": ["custom/"]})


def test_unknown_keys_are_rejected():
    with pytest.raises(ValueError, match="unknown configuration keys"):
        BridgeConfig.from_mapping({"not_a_real_setting": True})


def test_ranges_are_validated():
    with pytest.raises(ValueError, match="github_retries"):
        BridgeConfig.from_mapping({"github_retries": 0})
    with pytest.raises(ValueError, match="backup_retention"):
        BridgeConfig.from_mapping({"backup_retention": 0})


def test_json_config_load(tmp_path: Path):
    path = tmp_path / "bridge.json"
    path.write_text(json.dumps({"repository": "example/project", "branch": "main"}))
    cfg = BridgeConfig.load_json(path)
    assert cfg.repository == "example/project"
