"""Dependency checker and auto-installer for preset-toolkit."""
import importlib
import subprocess
import sys


# Map of import name -> pip package name (only where they differ)
_PIP_NAMES = {
    "yaml": "PyYAML",
    "PIL": "Pillow",
}

# Required for core functionality
CORE_DEPS = ["yaml", "PIL", "httpx"]

# Optional extras
OPTIONAL_DEPS = {
    "playwright": "playwright",
}


def _pip_install(package: str) -> bool:
    """Install a package via pip. Returns True on success."""
    print(f"  Installing {package}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        print(f"  Installed {package} successfully.")
        return True
    print(f"  Failed to install {package}: {result.stderr.strip()}")
    return False


def _is_importable(module_name: str) -> bool:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _pip_name(import_name: str) -> str:
    """Get pip package name for an import name."""
    return _PIP_NAMES.get(import_name, import_name)


def ensure_package(import_name: str) -> bool:
    """Check if a package is available; install it if not. Returns True if available after check."""
    if _is_importable(import_name):
        return True
    pip_pkg = _pip_name(import_name)
    print(f"  {pip_pkg} not found.")
    if _pip_install(pip_pkg):
        importlib.invalidate_caches()
        return _is_importable(import_name)
    return False


def ensure_core() -> list:
    """Ensure all core dependencies are installed. Returns list of failures."""
    failures = []
    for dep in CORE_DEPS:
        if not ensure_package(dep):
            failures.append(_pip_name(dep))
    return failures


def ensure_sup_cli() -> bool:
    """Check if preset-cli (sup) is installed; install if not."""
    result = subprocess.run(
        ["sup", "version"], capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return True
    print("  preset-cli (sup) not found.")
    if _pip_install("preset-cli"):
        # Verify it works after install
        verify = subprocess.run(
            ["sup", "version"], capture_output=True, text=True, timeout=30,
        )
        return verify.returncode == 0
    return False


def ensure_playwright() -> bool:
    """Ensure playwright + chromium browser are available."""
    if not ensure_package("playwright"):
        return False
    # Check if chromium is installed
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
        capture_output=True, text=True, timeout=30,
    )
    # If dry-run shows nothing to install, we're good. Otherwise install.
    if "chromium" in result.stdout or result.returncode != 0:
        print("  Installing Playwright Chromium browser...")
        install = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=300,
        )
        if install.returncode != 0:
            print(f"  Failed to install Chromium: {install.stderr.strip()}")
            return False
        print("  Chromium installed successfully.")
    return True


def check_all(include_optional: bool = False) -> dict:
    """Run a full dependency check. Returns status dict."""
    status = {"core": {}, "tools": {}, "optional": {}}

    for dep in CORE_DEPS:
        status["core"][_pip_name(dep)] = _is_importable(dep)

    sup_ok = subprocess.run(
        ["sup", "version"], capture_output=True, text=True, timeout=10,
    ).returncode == 0
    status["tools"]["preset-cli"] = sup_ok

    if include_optional:
        status["optional"]["playwright"] = _is_importable("playwright")

    return status
