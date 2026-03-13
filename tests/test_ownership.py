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
