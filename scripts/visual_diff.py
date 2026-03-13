"""Pixel-level image comparison using Pillow."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    from scripts.deps import ensure_package
    ensure_package("PIL")
    from PIL import Image

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


@dataclass
class DiffResult:
    diff_ratio: float          # 0.0 = identical, 1.0 = completely different
    diff_pixels: int
    total_pixels: int
    passed: bool
    diff_image: Optional[Path] = None
    error: str = ""


def _compare_numpy(img_a, img_b, color_tolerance):
    """Fast numpy-based pixel comparison."""
    arr_a = np.array(img_a, dtype=np.float32)
    arr_b = np.array(img_b, dtype=np.float32)
    diff = np.sqrt(np.sum((arr_a - arr_b) ** 2, axis=2))
    diff_mask = diff > color_tolerance
    return int(np.count_nonzero(diff_mask)), diff_mask


def _compare_pillow(img_a, img_b, color_tolerance):
    """Fallback pure-Python pixel comparison."""
    width, height = img_a.size
    pixels_a = img_a.load()
    pixels_b = img_b.load()
    diff_count = 0
    for y in range(height):
        for x in range(width):
            pa = pixels_a[x, y]
            pb = pixels_b[x, y]
            dist = sum((a - b) ** 2 for a, b in zip(pa, pb)) ** 0.5
            if dist > color_tolerance:
                diff_count += 1
    return diff_count, None


def compare_images(
    baseline: Path,
    current: Path,
    threshold: float = 0.01,
    diff_output: Optional[Path] = None,
    color_tolerance: int = 35,
) -> DiffResult:
    """Compare two images pixel-by-pixel.

    Args:
        baseline: Path to baseline screenshot
        current: Path to current screenshot
        threshold: Maximum allowed diff ratio (0.01 = 1%)
        diff_output: If set, write diff image highlighting changed pixels
        color_tolerance: Euclidean RGB distance below which pixels are
            considered identical (handles anti-aliasing). Default 35.

    Returns:
        DiffResult with diff stats and pass/fail
    """
    img_a = Image.open(baseline).convert("RGB")
    img_b = Image.open(current).convert("RGB")

    if img_a.size != img_b.size:
        return DiffResult(
            diff_ratio=1.0,
            diff_pixels=0,
            total_pixels=0,
            passed=False,
            error=f"Size mismatch: {img_a.size} vs {img_b.size}",
        )

    width, height = img_a.size
    total = width * height

    if _HAS_NUMPY:
        diff_count, diff_mask = _compare_numpy(img_a, img_b, color_tolerance)
    else:
        diff_count, diff_mask = _compare_pillow(img_a, img_b, color_tolerance)

    ratio = diff_count / total if total > 0 else 0.0

    diff_path = None
    if diff_output:
        if _HAS_NUMPY and diff_mask is not None:
            # Build diff image from numpy mask
            arr_a = np.array(img_a)
            diff_img_arr = arr_a // 4  # Dim unchanged pixels
            diff_img_arr[diff_mask] = [255, 0, 0]  # Red for changed pixels
            diff_img = Image.fromarray(diff_img_arr.astype(np.uint8))
        else:
            # Fallback: rebuild diff image with pillow
            diff_img = Image.new("RGB", (width, height), (0, 0, 0))
            pixels_a_raw = img_a.load()
            pixels_b_raw = img_b.load()
            diff_px = diff_img.load()
            for y in range(height):
                for x in range(width):
                    pa = pixels_a_raw[x, y]
                    pb = pixels_b_raw[x, y]
                    dist = sum((a - b) ** 2 for a, b in zip(pa, pb)) ** 0.5
                    if dist > color_tolerance:
                        diff_px[x, y] = (255, 0, 0)
                    else:
                        r, g, b = pa
                        diff_px[x, y] = (r // 4, g // 4, b // 4)
        diff_img.save(diff_output)
        diff_path = diff_output

    return DiffResult(
        diff_ratio=ratio,
        diff_pixels=diff_count,
        total_pixels=total,
        passed=ratio <= threshold,
        diff_image=diff_path,
    )
