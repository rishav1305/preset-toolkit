import pytest
from pathlib import Path
from scripts.config import ToolkitConfig, ConfigNotFoundError, ConfigValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.workspace_url == "https://test.us2a.app.preset.io"
    assert cfg.workspace_id == "12345"
    assert cfg.dashboard_id == 99
    assert cfg.dashboard_name == "Test Dashboard"
    assert cfg.sync_folder == "test-sync"


def test_config_nested_access():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.get("visual_regression.threshold") == 0.01
    assert cfg.get("css.max_length") == 30000
    assert cfg.get("screenshots.mask_selectors") == [".header-with-actions"]


def test_config_not_found():
    with pytest.raises(ConfigNotFoundError):
        ToolkitConfig.load(Path("/nonexistent/config.yaml"))


def test_config_user_email():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.user_email == "test@company.com"


def test_config_defaults():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.get("screenshots.browser") == "chromium"
    assert cfg.get("validation.require_markers_before_push") is True


def test_sync_assets_path():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.sync_assets_path == Path("test-sync/assets")


def test_get_missing_key_returns_default():
    cfg = ToolkitConfig.load(FIXTURES / "sample_config.yaml")
    assert cfg.get("nonexistent.key") is None
    assert cfg.get("nonexistent.key", "fallback") == "fallback"


def test_config_validates_required_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("version: 1\n")
    cfg = ToolkitConfig.load(config_path)
    with pytest.raises(ConfigValidationError, match="workspace.url"):
        cfg.validate()


def test_config_validates_dashboard_id_nonzero(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "version: 1\n"
        "workspace:\n  url: 'https://test.preset.io'\n"
        "dashboard:\n  id: 0\n"
    )
    cfg = ToolkitConfig.load(config_path)
    with pytest.raises(ConfigValidationError, match="dashboard.id"):
        cfg.validate()


def test_discover_walks_up(tmp_path):
    toolkit_dir = tmp_path / ".preset-toolkit"
    toolkit_dir.mkdir()
    config = toolkit_dir / "config.yaml"
    config.write_text("version: 1\nworkspace:\n  url: found\n  id: '1'\ndashboard:\n  id: 1\n  name: test\n  sync_folder: s\n")
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    cfg = ToolkitConfig.discover(subdir)
    assert cfg.workspace_url == "found"
