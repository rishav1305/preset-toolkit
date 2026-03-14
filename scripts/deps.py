"""Dependency checker and auto-installer for preset-toolkit."""
import importlib
import subprocess
import sys

from scripts.logger import get_logger
log = get_logger("deps")


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
    log.info("Installing %s...", package)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        log.warning("Timed out installing %s", package)
        return False
    if result.returncode == 0:
        log.info("Installed %s successfully.", package)
        return True
    log.warning("Failed to install %s: %s", package, result.stderr.strip())
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
    log.info("%s not found.", pip_pkg)
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


def _find_sup_binary() -> str:
    """Find sup binary (from superset-sup package), checking .venv/bin/ first, then system PATH."""
    from pathlib import Path
    import shutil
    venv_sup = Path(".venv/bin/sup")
    if venv_sup.exists():
        return str(venv_sup.resolve())
    system_sup = shutil.which("sup")
    if system_sup:
        return system_sup
    return "sup"  # fallback to bare name


def ensure_sup_cli() -> bool:
    """Check if sup CLI (from superset-sup package) is installed; install if not."""
    sup = _find_sup_binary()
    try:
        result = subprocess.run(
            [sup, "--version"], capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    log.info("sup CLI not found.")
    if _pip_install("superset-sup"):
        sup = _find_sup_binary()
        try:
            verify = subprocess.run(
                [sup, "--version"], capture_output=True, text=True, timeout=30,
            )
            return verify.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    return False


# Backward compatibility aliases
_find_preset_cli = _find_sup_binary
ensure_preset_cli = ensure_sup_cli


def ensure_playwright() -> bool:
    """Ensure playwright + chromium browser are available."""
    if not ensure_package("playwright"):
        return False
    # Check if chromium is installed
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        log.warning("Timed out checking Playwright status")
        return False
    # If dry-run shows nothing to install, we're good. Otherwise install.
    if "chromium" in result.stdout or result.returncode != 0:
        log.info("Installing Playwright Chromium browser...")
        try:
            install = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            log.warning("Timed out installing Chromium")
            return False
        if install.returncode != 0:
            log.warning("Failed to install Chromium: %s", install.stderr.strip())
            return False
        log.info("Chromium installed successfully.")
    return True


def check_all(include_optional: bool = False) -> dict:
    """Run a full dependency check. Returns status dict."""
    status = {"core": {}, "tools": {}, "optional": {}}

    for dep in CORE_DEPS:
        status["core"][_pip_name(dep)] = _is_importable(dep)

    sup = _find_sup_binary()
    try:
        sup_ok = subprocess.run(
            [sup, "--version"], capture_output=True, text=True, timeout=10,
        ).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        sup_ok = False
    status["tools"]["sup"] = sup_ok

    if include_optional:
        status["optional"]["playwright"] = _is_importable("playwright")

    return status
