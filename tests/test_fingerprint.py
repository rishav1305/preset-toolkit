import pytest
from pathlib import Path
from scripts.fingerprint import (
    compute_fingerprint, compute_fingerprint_map, check_markers,
    save_fingerprint, load_fingerprint, Fingerprint,
    save_fingerprint_map, load_fingerprint_map, FingerprintMap,
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


# ── v2 Fingerprint Map tests ──


def test_compute_fingerprint_map(tmp_path):
    """compute_fingerprint_map returns per-file hashes."""
    assets = tmp_path / "assets"
    (assets / "datasets" / "db").mkdir(parents=True)
    (assets / "datasets" / "db" / "ds1.yaml").write_text("sql: SELECT 1")
    (assets / "datasets" / "db" / "ds2.yaml").write_text("sql: SELECT 2")
    fm = compute_fingerprint_map(assets)
    assert len(fm.files) == 2
    assert "ds1.yaml" in fm.files
    assert "ds2.yaml" in fm.files


def test_fingerprint_map_diff():
    """Diff detects added, removed, changed files."""
    old = FingerprintMap(files={"a.yaml": "aaa", "b.yaml": "bbb", "c.yaml": "ccc"})
    new = FingerprintMap(files={"a.yaml": "aaa", "b.yaml": "XXX", "d.yaml": "ddd"})
    changes = new.diff(old)
    assert changes == {"b.yaml": "changed", "c.yaml": "removed", "d.yaml": "added"}


def test_fingerprint_map_summary():
    """Summary produces human-readable change description."""
    old = FingerprintMap(files={"a.yaml": "aaa"})
    new = FingerprintMap(files={"a.yaml": "XXX", "b.yaml": "bbb"})
    assert "1 changed" in new.summary(old)
    assert "1 added" in new.summary(old)


def test_save_and_load_fingerprint_map(tmp_path):
    """v2 fingerprint map round-trips through JSON."""
    fm = FingerprintMap(files={"ds.yaml": "abc123", "chart.yaml": "def456"})
    path = tmp_path / ".last-push-fingerprint"
    save_fingerprint_map(fm, path)
    loaded = load_fingerprint_map(path)
    assert loaded is not None
    assert loaded.files == fm.files


def test_load_fingerprint_map_v1_returns_none(tmp_path):
    """v1 format (plain text) returns None from load_fingerprint_map."""
    path = tmp_path / "fp"
    path.write_text("abc123 12345")
    assert load_fingerprint_map(path) is None


def test_load_fingerprint_map_missing():
    """Missing file returns None."""
    assert load_fingerprint_map(Path("/nonexistent")) is None


def test_fingerprint_map_no_changes():
    """Identical maps produce empty diff."""
    fm = FingerprintMap(files={"a.yaml": "aaa"})
    assert fm.diff(fm) == {}
    assert fm.summary(fm) == "no changes"


def test_compute_fingerprint_map_empty_dir(tmp_path):
    """Empty directory returns empty map."""
    assets = tmp_path / "empty"
    assets.mkdir()
    fm = compute_fingerprint_map(assets)
    assert len(fm.files) == 0


def test_compute_fingerprint_map_nonexistent(tmp_path):
    """Nonexistent directory returns empty map."""
    fm = compute_fingerprint_map(tmp_path / "nope")
    assert len(fm.files) == 0
