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


@dataclass
class DiffResult:
    diff_ratio: float          # 0.0 = identical, 1.0 = completely different
    diff_pixels: int
    total_pixels: int
    passed: bool
    diff_image: Optional[Path] = None
    error: str = ""


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
    pixels_a = img_a.load()
    pixels_b = img_b.load()

    diff_count = 0
    diff_img = Image.new("RGB", (width, height), (0, 0, 0)) if diff_output else None
    diff_pixels_img = diff_img.load() if diff_img else None

    for y in range(height):
        for x in range(width):
            pa = pixels_a[x, y]
            pb = pixels_b[x, y]
            dist = sum((a - b) ** 2 for a, b in zip(pa, pb)) ** 0.5
            if dist > color_tolerance:
                diff_count += 1
                if diff_pixels_img:
                    diff_pixels_img[x, y] = (255, 0, 0)
            elif diff_pixels_img:
                r, g, b = pa
                diff_pixels_img[x, y] = (r // 4, g // 4, b // 4)

    ratio = diff_count / total if total > 0 else 0.0

    diff_path = None
    if diff_img and diff_output:
        diff_img.save(diff_output)
        diff_path = diff_output

    return DiffResult(
        diff_ratio=ratio,
        diff_pixels=diff_count,
        total_pixels=total,
        passed=ratio <= threshold,
        diff_image=diff_path,
    )
