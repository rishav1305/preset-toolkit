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


def test_compute_fingerprint_empty_yaml(tmp_path):
    """Empty YAML file should not crash."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    from scripts.fingerprint import compute_fingerprint
    fp = compute_fingerprint(empty)
    assert fp.hash != ""
    assert fp.sql_length == 0


def test_check_markers_empty_yaml(tmp_path):
    """Empty dataset YAML should report all markers missing."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    markers = tmp_path / "markers.txt"
    markers.write_text("some_marker\n")
    from scripts.fingerprint import check_markers
    result = check_markers(empty, markers)
    assert result.all_present is False


def test_load_fingerprint_malformed(tmp_path):
    """Malformed fingerprint file should return None, not crash."""
    from scripts.fingerprint import load_fingerprint
    fp_file = tmp_path / "fp"
    fp_file.write_text("only_one_field")
    assert load_fingerprint(fp_file) is None


def test_compute_fingerprint_corrupt_yaml(tmp_path):
    """Corrupt YAML in dataset should return empty fingerprint, not crash."""
    corrupt = tmp_path / "dataset.yaml"
    corrupt.write_text(": : invalid yaml [[[")
    fp = compute_fingerprint(corrupt)
    assert fp.hash != ""
    assert fp.sql_length == 0


def test_save_fingerprint_creates_parent_dir(tmp_path):
    """save_fingerprint should create parent directory if missing."""
    fp = Fingerprint(hash="abc123", sql_length=100)
    fp_path = tmp_path / "deep" / "nested" / "fingerprint"
    save_fingerprint(fp, fp_path)
    assert fp_path.exists()
    assert "abc123" in fp_path.read_text()


def test_load_fingerprint_non_numeric_length(tmp_path):
    """Non-numeric SQL length should return None."""
    from scripts.fingerprint import load_fingerprint
    fp_file = tmp_path / "fp"
    fp_file.write_text("abc123 not_a_number")
    assert load_fingerprint(fp_file) is None
