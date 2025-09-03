from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

import yaml

logger = logging.getLogger(__name__)


class ConfigService:
    """Utility class for application runtime configuration."""

    def __init__(self, raw: Any | None = None) -> None:
        self.cfg: Dict[str, Any] = self.coerce_cfg(raw)

    @staticmethod
    def coerce_cfg(raw: Any) -> Dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, Mapping):
            return dict(raw)
        if isinstance(raw, str):
            try:
                data = yaml.safe_load(raw) or {}
                if isinstance(data, dict):
                    return data
                return {"_raw": raw, "_parsed": data}
            except Exception as e:  # pragma: no cover - safe load errors
                logger.warning("cfg safe_load failed: %s", e)
                return {"_raw": raw}
        return {}

    def set_cfg(self, new_cfg: Any) -> Dict[str, Any]:
        self.cfg = self.coerce_cfg(new_cfg)
        logger.info("Config updated. keys=%s", list(self.cfg.keys())[:8])
        return self.cfg
