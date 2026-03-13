import pytest
from pathlib import Path
from PIL import Image
from scripts.visual_diff import compare_images, DiffResult


def _make_image(tmp_path: Path, name: str, color: tuple) -> Path:
    img = Image.new("RGB", (100, 100), color)
    path = tmp_path / name
    img.save(path)
    return path


def test_identical_images(tmp_path):
    a = _make_image(tmp_path, "a.png", (255, 0, 0))
    b = _make_image(tmp_path, "b.png", (255, 0, 0))
    result = compare_images(a, b)
    assert result.diff_ratio == 0.0
    assert result.passed is True


def test_completely_different_images(tmp_path):
    a = _make_image(tmp_path, "a.png", (255, 0, 0))
    b = _make_image(tmp_path, "b.png", (0, 0, 255))
    result = compare_images(a, b, threshold=0.01)
    assert result.diff_ratio > 0.5
    assert result.passed is False


def test_threshold_boundary(tmp_path):
    a = _make_image(tmp_path, "a.png", (255, 0, 0))
    b = _make_image(tmp_path, "b.png", (254, 0, 0))
    result = compare_images(a, b, threshold=0.01)
    # Sub-pixel difference within color_tolerance=35 should pass
    assert result.passed is True
    assert result.diff_ratio == 0.0


def test_diff_image_generated(tmp_path):
    a = _make_image(tmp_path, "a.png", (255, 0, 0))
    b = _make_image(tmp_path, "b.png", (0, 0, 255))
    diff_path = tmp_path / "diff.png"
    result = compare_images(a, b, diff_output=diff_path)
    assert diff_path.exists()
    assert result.diff_image == diff_path


def test_size_mismatch(tmp_path):
    a_img = Image.new("RGB", (100, 100), (255, 0, 0))
    b_img = Image.new("RGB", (200, 200), (255, 0, 0))
    a = tmp_path / "a.png"; a_img.save(a)
    b = tmp_path / "b.png"; b_img.save(b)
    result = compare_images(a, b)
    assert result.passed is False
    assert "size mismatch" in result.error.lower()


def test_custom_color_tolerance(tmp_path):
    a = _make_image(tmp_path, "a.png", (200, 0, 0))
    b = _make_image(tmp_path, "b.png", (150, 0, 0))
    # Distance is 50. Default tolerance=35 should flag it.
    result_strict = compare_images(a, b, color_tolerance=35)
    assert result_strict.diff_ratio > 0
    # Tolerance=60 should pass it.
    result_loose = compare_images(a, b, color_tolerance=60)
    assert result_loose.diff_ratio == 0.0


def test_large_image_comparison_completes_in_time(tmp_path):
    """Visual diff of 1920x1080 images should complete in <5 seconds."""
    import time
    img_a = Image.new("RGB", (1920, 1080), (200, 200, 200))
    img_b = Image.new("RGB", (1920, 1080), (200, 200, 201))
    a_path = tmp_path / "a.png"
    b_path = tmp_path / "b.png"
    img_a.save(a_path)
    img_b.save(b_path)
    start = time.monotonic()
    result = compare_images(a_path, b_path)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"Took {elapsed:.1f}s — too slow"
    assert result.passed is True
