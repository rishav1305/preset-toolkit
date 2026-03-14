"""End-to-end integration test: config → dedup → fingerprint → ownership → visual diff."""
import shutil
from pathlib import Path

import yaml
from PIL import Image

from scripts.config import ToolkitConfig
from scripts.dedup import find_duplicates, apply_dedup
from scripts.fingerprint import (
    compute_fingerprint, compute_fingerprint_map, check_markers,
    save_fingerprint, load_fingerprint,
    save_fingerprint_map, load_fingerprint_map, FingerprintMap,
)
from scripts.ownership import OwnershipMap
from scripts.visual_diff import compare_images
from scripts.push_dashboard import compare_css


FIXTURES = Path(__file__).parent / "fixtures"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f)


def _make_image(path: Path, color: tuple) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (200, 100), color)
    img.save(path)
    return path


def test_full_setup_flow(tmp_path):
    """Full pipeline: config → dedup → fingerprint → markers → ownership → visual diff → CSS compare."""

    # --- 1. Config ---
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        "version: 1\n"
        "workspace:\n"
        '  url: "https://test.us2a.app.preset.io"\n'
        '  id: "12345"\n'
        "dashboard:\n"
        "  id: 99\n"
        '  name: "Integration Test Dashboard"\n'
        '  sync_folder: "sync"\n'
        "auth:\n"
        '  method: "env"\n'
        "validation:\n"
        '  markers_file: ".preset-toolkit/markers.txt"\n'
        '  fingerprint_file: ".preset-toolkit/.last-push-fingerprint"\n'
        "user:\n"
        '  email: "dev@company.com"\n'
    )
    cfg = ToolkitConfig.load(config_path)
    assert cfg.dashboard_name == "Integration Test Dashboard"
    assert cfg.dashboard_id == 99
    assert cfg.user_email == "dev@company.com"

    # --- 2. Dedup ---
    charts_dir = tmp_path / "sync" / "assets" / "charts"
    charts_dir.mkdir(parents=True)

    _write_yaml(charts_dir / "Revenue.yaml", {
        "uuid": "rev-uuid-1111",
        "slice_name": "Revenue",
        "viz_type": "table",
    })
    _write_yaml(charts_dir / "Revenue_Renamed_555.yaml", {
        "uuid": "rev-uuid-1111",
        "slice_name": "Revenue Renamed",
        "viz_type": "table",
    })
    _write_yaml(charts_dir / "Audience.yaml", {
        "uuid": "aud-uuid-2222",
        "slice_name": "Audience",
        "viz_type": "table",
    })

    dupes = find_duplicates(charts_dir)
    assert len(dupes) == 1  # One UUID has 2 files
    removed = apply_dedup(charts_dir)
    assert removed == 1
    assert (charts_dir / "Revenue.yaml").exists()  # Kept (no ID suffix)
    assert not (charts_dir / "Revenue_Renamed_555.yaml").exists()  # Removed
    assert (charts_dir / "Audience.yaml").exists()  # Untouched (unique)

    # --- 3. Fingerprint ---
    datasets_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    datasets_dir.mkdir(parents=True)
    dataset_path = datasets_dir / "Main_Dataset.yaml"
    _write_yaml(dataset_path, {
        "uuid": "ds-uuid-3333",
        "table_name": "test_table",
        "sql": "SELECT 'Revenue - Ads | Subs Sales' AS title, weekly_total_revenue_curr FROM kpis",
    })

    fp = compute_fingerprint(dataset_path)
    assert len(fp.hash) == 16
    assert fp.sql_length > 0

    # Deterministic
    fp2 = compute_fingerprint(dataset_path)
    assert fp.hash == fp2.hash

    # Save and load (v1 legacy)
    fp_file = config_dir / ".last-push-fingerprint"
    save_fingerprint(fp, fp_file)
    loaded = load_fingerprint(fp_file)
    assert loaded.hash == fp.hash
    assert loaded.sql_length == fp.sql_length

    # v2 per-file fingerprint map
    assets_dir = tmp_path / "sync" / "assets"
    fp_map = compute_fingerprint_map(assets_dir)
    assert len(fp_map.files) > 0

    fp_map_file = config_dir / ".fp-map-test"
    save_fingerprint_map(fp_map, fp_map_file)
    loaded_map = load_fingerprint_map(fp_map_file)
    assert loaded_map is not None
    assert loaded_map.files == fp_map.files

    # Diff detection
    fp_map2 = FingerprintMap(files={**fp_map.files, "new_file.yaml": "deadbeef"})
    changes = fp_map2.diff(fp_map)
    assert changes.get("new_file.yaml") == "added"

    # --- 4. Markers ---
    markers_file = config_dir / "markers.txt"
    markers_file.write_text(
        "# Required markers\n"
        "Revenue - Ads | Subs Sales\n"
        "weekly_total_revenue_curr\n"
    )
    mr = check_markers(dataset_path, markers_file)
    assert mr.all_present is True
    assert len(mr.present) == 2
    assert len(mr.missing) == 0

    # Missing marker
    markers_file.write_text("NONEXISTENT_MARKER\n")
    mr2 = check_markers(dataset_path, markers_file)
    assert mr2.all_present is False
    assert "NONEXISTENT_MARKER" in mr2.missing

    # --- 5. Ownership ---
    ownership_path = config_dir / "ownership.yaml"
    _write_yaml(ownership_path, {
        "sections": {
            "revenue": {
                "owner": "alice@company.com",
                "charts": [2085, 2088],
                "datasets": ["Main_Dataset"],
                "description": "Revenue tiles",
            },
            "audience": {
                "owner": "bob@company.com",
                "charts": [2084],
                "datasets": ["Main_Dataset"],
                "description": "Audience tiles",
            },
        },
        "shared_datasets": [{
            "name": "Main_Dataset",
            "owners": ["alice@company.com", "bob@company.com"],
            "advisory": "Shared dataset — notify all owners.",
        }],
    })

    om = OwnershipMap.load(ownership_path)
    assert om.chart_section(2085) == "revenue"
    assert om.chart_section(2084) == "audience"

    # Own section — no warning
    own = om.check("alice@company.com", changed_charts=[2085])
    assert own.has_warnings is False

    # Foreign section — warning
    foreign = om.check("alice@company.com", changed_charts=[2084])
    assert foreign.has_warnings is True
    assert "bob@company.com" in foreign.warnings[0]

    # Shared dataset warning
    shared = om.check("alice@company.com", changed_datasets=["Main_Dataset"])
    assert shared.has_shared_dataset_warnings is True

    # --- 6. Visual Diff ---
    baselines = config_dir / "baselines"
    current = tmp_path / "screenshots"

    baseline_img = _make_image(baselines / "full-page.png", (200, 200, 200))
    current_same = _make_image(current / "full-page.png", (200, 200, 200))

    # Identical — should pass
    result = compare_images(baseline_img, current_same)
    assert result.passed is True
    assert result.diff_ratio == 0.0

    # Different — should fail
    current_diff = _make_image(current / "full-page-changed.png", (100, 50, 50))
    result2 = compare_images(baseline_img, current_diff, threshold=0.01)
    assert result2.passed is False
    assert result2.diff_ratio > 0.5

    # Diff image generation
    diff_path = tmp_path / "diff.png"
    result3 = compare_images(baseline_img, current_diff, diff_output=diff_path)
    assert diff_path.exists()
    assert result3.diff_image == diff_path

    # --- 7. CSS Compare ---
    css_cmp = compare_css("body { color: red; }", "body { color: red; }")
    assert css_cmp.changed is False

    css_cmp2 = compare_css("body { color: red; }", "body { color: blue; }")
    assert css_cmp2.changed is True

    long_css = "x" * 31000
    css_cmp3 = compare_css(long_css, "short")
    assert css_cmp3.length_warning is True


def test_config_discover_from_subdirectory(tmp_path):
    """Config.discover() finds config.yaml by walking up directories."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "version: 1\n"
        "workspace:\n"
        '  url: "https://found.preset.io"\n'
        "dashboard:\n"
        "  id: 42\n"
        '  name: "Found Dashboard"\n'
    )

    # Create a nested subdirectory
    deep = tmp_path / "sync" / "assets" / "charts"
    deep.mkdir(parents=True)

    cfg = ToolkitConfig.discover(start_dir=deep)
    assert cfg.dashboard_name == "Found Dashboard"
    assert cfg.dashboard_id == 42
