import yaml
import pytest
from backend.app.core.config import AppSettings, RuntimeConfig


def test_load_yaml_defaults(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    # Write minimal config with only some overrides
    cfg_data = {"api": {"paper": False}, "strategy": {"symbol": "ETHUSDT"}}
    cfg_file.write_text(yaml.safe_dump(cfg_data))

    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()

    assert s.runtime_cfg["api"]["paper"] is False
    assert s.runtime_cfg["strategy"]["symbol"] == "ETHUSDT"
    # default from model
    assert s.runtime_cfg["shadow"]["enabled"] is True


def test_load_yaml_invalid_field(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"strategy": {"unknown": 1}}))
    s = AppSettings(app_config_file=str(cfg_file))
    with pytest.raises(ValueError):
        s.load_yaml()
