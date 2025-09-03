import yaml
import pytest
from backend.app.core.config import AppSettings, RuntimeConfig


def test_load_yaml_defaults(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_data = {
        "api": {"paper": False},
        "strategy": {"symbol": "ETHUSDT"},
        "ui": {"theme": "light"},
        "features": {"risk_protections": False},
        "risk": {"max_drawdown_pct": 5},
        "history": {"db_path": "test.db"},
    }
    cfg_file.write_text(yaml.safe_dump(cfg_data))

    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()

    assert s.runtime_cfg["api"]["paper"] is False
    assert s.runtime_cfg["api"]["autostart"] is False
    assert s.runtime_cfg["api"]["shadow"] is False
    assert s.runtime_cfg["strategy"]["symbol"] == "ETHUSDT"
    assert s.runtime_cfg["strategy"]["loop_sleep"] == 0.2
    assert s.runtime_cfg["ui"]["theme"] == "light"
    assert s.runtime_cfg["ui"]["chart"] == "tv"
    assert s.runtime_cfg["features"]["risk_protections"] is False
    assert s.runtime_cfg["features"]["market_widget_feed"] is True
    assert s.runtime_cfg["risk"]["max_drawdown_pct"] == 5
    assert s.runtime_cfg["risk"]["cooldown_sec"] == 1800
    assert s.runtime_cfg["history"]["db_path"] == "test.db"
    assert s.runtime_cfg["history"]["retention_days"] == 365
    assert s.runtime_cfg["shadow"]["enabled"] is True


def test_loop_sleep_override(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({"strategy": {"loop_sleep": 0.5}}))
    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()
    assert s.runtime_cfg["strategy"]["loop_sleep"] == 0.5


@pytest.mark.parametrize("bad_section", [
    {"strategy": {"unknown": 1}},
    {"ui": {"unknown": 1}},
    {"features": {"unknown": 1}},
    {"risk": {"unknown": 1}},
    {"history": {"unknown": 1}},
])
def test_load_yaml_invalid_field(tmp_path, bad_section):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump(bad_section))
    s = AppSettings(app_config_file=str(cfg_file))
    with pytest.raises(ValueError):
        s.load_yaml()
