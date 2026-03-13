import shutil
import pytest
from pathlib import Path
from scripts.dedup import find_duplicates, pick_keeper, apply_dedup

FIXTURES = Path(__file__).parent / "fixtures"


def test_find_duplicates(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    shutil.copy(FIXTURES / "sample_chart_a.yaml", charts / "My_Chart.yaml")
    shutil.copy(FIXTURES / "sample_chart_b_dup.yaml", charts / "My_Chart_Renamed_123.yaml")
    dupes = find_duplicates(charts)
    assert len(dupes) == 1
    uuid_key = list(dupes.keys())[0]
    assert len(dupes[uuid_key]) == 2


def test_pick_keeper_prefers_no_id_suffix():
    files = [
        (1000.0, Path("My_Chart.yaml")),
        (2000.0, Path("My_Chart_123.yaml")),
    ]
    keeper = pick_keeper(files)
    assert keeper.name == "My_Chart.yaml"


def test_pick_keeper_falls_back_to_newest():
    files = [
        (1000.0, Path("Old_Name_100.yaml")),
        (2000.0, Path("New_Name_200.yaml")),
    ]
    keeper = pick_keeper(files)
    assert keeper.name == "New_Name_200.yaml"


def test_apply_dedup(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    shutil.copy(FIXTURES / "sample_chart_a.yaml", charts / "My_Chart.yaml")
    shutil.copy(FIXTURES / "sample_chart_b_dup.yaml", charts / "My_Chart_Renamed_123.yaml")
    removed = apply_dedup(charts)
    assert removed == 1
    assert (charts / "My_Chart.yaml").exists()
    assert not (charts / "My_Chart_Renamed_123.yaml").exists()


def test_no_duplicates(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    shutil.copy(FIXTURES / "sample_chart_a.yaml", charts / "Only_One.yaml")
    dupes = find_duplicates(charts)
    assert len(dupes) == 0


def test_file_without_uuid_skipped(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    no_uuid = charts / "no_uuid.yaml"
    no_uuid.write_text("slice_name: test\nviz_type: table\n")
    dupes = find_duplicates(charts)
    assert len(dupes) == 0


def test_empty_directory(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    dupes = find_duplicates(charts)
    assert len(dupes) == 0


def test_empty_yaml_file_skipped(tmp_path):
    """Empty YAML files should be skipped without crashing."""
    import yaml
    d = tmp_path / "charts"
    d.mkdir()
    (d / "empty.yaml").write_text("")
    (d / "valid.yaml").write_text(yaml.safe_dump({"uuid": "abc", "name": "chart"}))
    from scripts.dedup import find_duplicates
    dupes = find_duplicates(d)
    assert len(dupes) == 0
