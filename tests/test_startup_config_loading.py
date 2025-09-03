import os
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.services.state import get_state


def test_load_yaml_on_startup(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("api:\n  paper: false\n")
    os.environ["APP_CONFIG_FILE"] = str(cfg_path)

    # Before startup, defaults should be in place
    assert settings.runtime_cfg["api"]["paper"] is True

    with TestClient(app):
        pass  # triggers startup and shutdown

    # After startup, config from file should be loaded
    assert settings.runtime_cfg["api"]["paper"] is False
    state = get_state()
    assert state.cfg["api"]["paper"] is False

    # Cleanup
    os.environ.pop("APP_CONFIG_FILE", None)
    settings.runtime_cfg = settings.default_cfg.copy()
    state.cfg = settings.runtime_cfg
