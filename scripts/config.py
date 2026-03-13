"""Config reader for .preset-toolkit/config.yaml"""
import functools
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigNotFoundError(FileNotFoundError):
    pass


class ToolkitConfig:
    """Reads and provides typed access to .preset-toolkit/config.yaml"""

    def __init__(self, data: dict, config_path: Path):
        self._data = data
        self._path = config_path

    @classmethod
    def load(cls, path: Path) -> "ToolkitConfig":
        path = Path(path)
        if not path.exists():
            raise ConfigNotFoundError(f"Config not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(data, path)

    @classmethod
    def discover(cls, start_dir: Optional[Path] = None) -> "ToolkitConfig":
        """Find .preset-toolkit/config.yaml by walking up from start_dir."""
        d = Path(start_dir or Path.cwd())
        while True:
            candidate = d / ".preset-toolkit" / "config.yaml"
            if candidate.exists():
                return cls.load(candidate)
            parent = d.parent
            if parent == d:
                break
            d = parent
        raise ConfigNotFoundError(
            "No .preset-toolkit/config.yaml found in directory tree"
        )

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Access nested config: cfg.get('visual_regression.threshold')"""
        try:
            return functools.reduce(
                lambda d, k: d[k], dotted_key.split("."), self._data
            )
        except (KeyError, TypeError):
            return default

    @property
    def workspace_url(self) -> str:
        return self.get("workspace.url", "")

    @property
    def workspace_id(self) -> str:
        return str(self.get("workspace.id", ""))

    @property
    def dashboard_id(self) -> int:
        return self.get("dashboard.id", 0)

    @property
    def dashboard_name(self) -> str:
        return self.get("dashboard.name", "")

    @property
    def sync_folder(self) -> str:
        return self.get("dashboard.sync_folder", "sync")

    @property
    def sync_assets_path(self) -> Path:
        return Path(self.sync_folder) / "assets"

    @property
    def user_email(self) -> str:
        return self.get("user.email", "")

    @property
    def project_root(self) -> Path:
        return self._path.parent.parent
