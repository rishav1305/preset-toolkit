import pytest
from pathlib import Path
from scripts.ownership import OwnershipMap, OwnershipCheck

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_ownership():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    assert len(om.sections) == 3
    assert om.sections["audience"].owner == "alice@company.com"


def test_chart_to_section():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    assert om.chart_section(2084) == "audience"
    assert om.chart_section(2085) == "revenue"
    assert om.chart_section(9999) is None


def test_check_ownership_own_section():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    result = om.check("alice@company.com", changed_charts=[2084])
    assert result.has_warnings is False


def test_check_ownership_foreign_section():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    result = om.check("alice@company.com", changed_charts=[2085])
    assert result.has_warnings is True
    assert "bob@company.com" in result.warnings[0]


def test_check_ownership_shared_dataset():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    result = om.check("alice@company.com", changed_datasets=["WCBM_Audience_Tile_Source"])
    assert result.has_shared_dataset_warnings is True


def test_check_unassigned_no_warning():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    result = om.check("anyone@company.com", changed_charts=[2103])
    assert result.has_warnings is False


def test_check_multiple_sections():
    om = OwnershipMap.load(FIXTURES / "sample_ownership.yaml")
    result = om.check("alice@company.com", changed_charts=[2084, 2085, 2088])
    assert result.has_warnings is True
    assert len(result.warnings) == 2  # 2085 and 2088 are both revenue


def test_ownership_load_corrupt_yaml(tmp_path):
    """Corrupt YAML should return empty OwnershipMap, not crash."""
    corrupt = tmp_path / "ownership.yaml"
    corrupt.write_text(": : invalid yaml [[[")
    om = OwnershipMap.load(corrupt)
    assert len(om.sections) == 0
    assert len(om.shared_datasets) == 0


def test_ownership_load_null_yaml(tmp_path):
    """Empty/null YAML should return empty OwnershipMap."""
    empty = tmp_path / "ownership.yaml"
    empty.write_text("")
    om = OwnershipMap.load(empty)
    assert len(om.sections) == 0
    assert len(om.shared_datasets) == 0
