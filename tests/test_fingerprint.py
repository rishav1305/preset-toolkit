import pytest
from pathlib import Path
from scripts.fingerprint import (
    compute_fingerprint, check_markers, save_fingerprint, load_fingerprint, Fingerprint
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_fingerprint():
    fp = compute_fingerprint(FIXTURES / "sample_dataset.yaml")
    assert len(fp.hash) == 16
    assert fp.sql_length > 0


def test_fingerprint_deterministic():
    fp1 = compute_fingerprint(FIXTURES / "sample_dataset.yaml")
    fp2 = compute_fingerprint(FIXTURES / "sample_dataset.yaml")
    assert fp1.hash == fp2.hash
    assert fp1.sql_length == fp2.sql_length


def test_check_markers_all_present(tmp_path):
    markers_file = tmp_path / "markers.txt"
    markers_file.write_text("Revenue - Ads | Subs Sales\nweekly_total_revenue_curr\n")
    result = check_markers(FIXTURES / "sample_dataset.yaml", markers_file)
    assert result.all_present is True
    assert len(result.missing) == 0


def test_check_markers_some_missing(tmp_path):
    markers_file = tmp_path / "markers.txt"
    markers_file.write_text("Revenue - Ads | Subs Sales\nNONEXISTENT_MARKER\n")
    result = check_markers(FIXTURES / "sample_dataset.yaml", markers_file)
    assert result.all_present is False
    assert "NONEXISTENT_MARKER" in result.missing


def test_check_markers_ignores_comments_and_blanks(tmp_path):
    markers_file = tmp_path / "markers.txt"
    markers_file.write_text("# comment\n\nRevenue - Ads | Subs Sales\n  \n")
    result = check_markers(FIXTURES / "sample_dataset.yaml", markers_file)
    assert result.all_present is True
    assert len(result.present) == 1


def test_save_and_load_fingerprint(tmp_path):
    fp = Fingerprint(hash="abcdef1234567890", sql_length=12345)
    path = tmp_path / ".fingerprint"
    save_fingerprint(fp, path)
    loaded = load_fingerprint(path)
    assert loaded is not None
    assert loaded.hash == fp.hash
    assert loaded.sql_length == fp.sql_length


def test_load_fingerprint_missing():
    result = load_fingerprint(Path("/nonexistent/file"))
    assert result is None
