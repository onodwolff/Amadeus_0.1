import yaml
import pytest
from backend.app.core.config import AppSettings


def test_load_yaml_defaults(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_data = {
        "api": {"paper": False, "autostart": True, "shadow": True},
        "strategy": {
            "name": "market_maker",
            "market_maker": {
                "symbol": "ETHUSDT",
                "post_only": False,
                "aggressive_take": True,
            },
        },
        "ui": {"theme": "light"},
        "features": {"risk_protections": False},
        "risk": {"max_drawdown_pct": 5},
        "history": {"db_path": "test.db"},
    }
    cfg_file.write_text(yaml.safe_dump(cfg_data))

    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()

    # api section
    assert s.runtime_cfg["api"]["paper"] is False
    assert s.runtime_cfg["api"]["autostart"] is True
    assert s.runtime_cfg["api"]["shadow"] is True

    # strategy section
    strat = s.runtime_cfg["strategy"]["market_maker"]
    assert strat["symbol"] == "ETHUSDT"
    assert strat["post_only"] is False
    assert strat["aggressive_take"] is True
    assert strat["loop_sleep"] == 0.2

    # ui section
    assert s.runtime_cfg["ui"]["theme"] == "light"
    assert s.runtime_cfg["ui"]["chart"] == "tv"

    # features section
    assert s.runtime_cfg["features"]["risk_protections"] is False
    assert s.runtime_cfg["features"]["market_widget_feed"] is True

    # risk section
    assert s.runtime_cfg["risk"]["max_drawdown_pct"] == 5
    assert s.runtime_cfg["risk"]["cooldown_sec"] == 1800

    # history section
    assert s.runtime_cfg["history"]["db_path"] == "test.db"
    assert s.runtime_cfg["history"]["retention_days"] == 365

    # shadow defaults should still be applied
    assert s.runtime_cfg["shadow"]["enabled"] is True


def test_loop_sleep_override(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        yaml.safe_dump({"strategy": {"name": "market_maker", "market_maker": {"loop_sleep": 0.5}}})
    )
    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()
    assert s.runtime_cfg["strategy"]["market_maker"]["loop_sleep"] == 0.5


def test_defaults_when_sections_missing(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({}))

    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()

    assert s.runtime_cfg["features"]["risk_protections"] is True
    assert s.runtime_cfg["ui"]["theme"] == "dark"
    assert s.runtime_cfg["risk"]["max_drawdown_pct"] == 10.0
    assert s.runtime_cfg["history"]["db_path"] == "data/history.db"
    assert s.runtime_cfg["api"]["paper"] is True
    assert s.runtime_cfg["strategy"]["market_maker"]["post_only"] is True


def test_dump_and_load_round_trip(tmp_path):
    cfg_data = {
        "api": {"paper": False, "autostart": True, "shadow": True},
        "strategy": {
            "name": "market_maker",
            "market_maker": {
                "symbol": "BTCUSDT",
                "allow_short": True,
                "post_only": False,
            },
        },
        "ui": {"chart": "tv", "theme": "light"},
        "features": {"risk_protections": False},
        "risk": {"max_drawdown_pct": 2.5},
        "history": {"db_path": "my.db", "retention_days": 10},
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump(cfg_data))

    s = AppSettings(app_config_file=str(cfg_file))
    s.load_yaml()

    out_file = tmp_path / "round.yaml"
    s.dump_yaml(str(out_file))

    s2 = AppSettings(app_config_file=str(out_file))
    s2.load_yaml()

    assert s.runtime_cfg == s2.runtime_cfg


@pytest.mark.parametrize(
    "bad_section",
    [
        {"strategy": {"unknown": 1}},
        {"strategy": {"market_maker": {"unknown": 1}}},
        {"strategy": {"market_maker": {"econ": {"unknown": 1}}}},
        {"ui": {"unknown": 1}},
        {"features": {"unknown": 1}},
        {"risk": {"unknown": 1}},
        {"history": {"unknown": 1}},
        {"api": {"unknown": 1}},
    ],
)
def test_load_yaml_invalid_field(tmp_path, bad_section):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.safe_dump(bad_section))
    s = AppSettings(app_config_file=str(cfg_file))
    with pytest.raises(ValueError):
        s.load_yaml()
