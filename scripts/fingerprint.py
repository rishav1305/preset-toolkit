"""Content fingerprinting and marker checking for dataset YAMLs."""
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    from scripts.deps import ensure_package
    ensure_package("yaml")
    import yaml

from scripts.logger import get_logger

log = get_logger("fingerprint")


@dataclass
class Fingerprint:
    hash: str
    sql_length: int

    def __str__(self) -> str:
        return f"{self.hash}  {self.sql_length}"


@dataclass
class FingerprintMap:
    """Per-file fingerprint map (v2 format)."""
    files: Dict[str, str] = field(default_factory=dict)

    def diff(self, other: "FingerprintMap") -> Dict[str, str]:
        """Compare two maps. Returns dict of {filename: 'added'|'removed'|'changed'}."""
        changes = {}
        for name, h in self.files.items():
            if name not in other.files:
                changes[name] = "added"
            elif other.files[name] != h:
                changes[name] = "changed"
        for name in other.files:
            if name not in self.files:
                changes[name] = "removed"
        return changes

    def summary(self, other: Optional["FingerprintMap"] = None) -> str:
        if other is None:
            return f"{len(self.files)} files tracked"
        d = self.diff(other)
        added = sum(1 for v in d.values() if v == "added")
        removed = sum(1 for v in d.values() if v == "removed")
        changed = sum(1 for v in d.values() if v == "changed")
        if not d:
            return "no changes"
        parts = []
        if changed:
            parts.append(f"{changed} changed")
        if added:
            parts.append(f"{added} added")
        if removed:
            parts.append(f"{removed} removed")
        return ", ".join(parts)


@dataclass
class MarkerResult:
    present: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    @property
    def all_present(self) -> bool:
        return len(self.missing) == 0


def compute_fingerprint(dataset_yaml: Path) -> Fingerprint:
    """Compute SHA-256 fingerprint of the SQL field in a dataset YAML."""
    try:
        with open(dataset_yaml) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        log.warning("Could not read %s: %s", dataset_yaml.name, e)
        data = {}
    if not isinstance(data, dict):
        data = {}
    sql = data.get("sql", "")
    h = hashlib.sha256(sql.encode()).hexdigest()[:16]
    return Fingerprint(hash=h, sql_length=len(sql))


def compute_fingerprint_map(assets_dir: Path) -> FingerprintMap:
    """Compute per-file SHA-256 fingerprint map for all YAMLs under assets_dir."""
    files = {}
    if not assets_dir.exists():
        return FingerprintMap(files=files)
    for yaml_file in sorted(assets_dir.rglob("*.yaml")):
        try:
            content = yaml_file.read_bytes()
            h = hashlib.sha256(content).hexdigest()[:16]
            files[yaml_file.name] = h
        except OSError as e:
            log.warning("Could not read %s: %s", yaml_file.name, e)
    return FingerprintMap(files=files)


def check_markers(dataset_yaml: Path, markers_file: Path) -> MarkerResult:
    """Check that all markers in markers_file exist in the dataset SQL."""
    try:
        with open(dataset_yaml) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        log.warning("Could not read %s: %s", dataset_yaml.name, e)
        data = {}
    if not isinstance(data, dict):
        data = {}
    sql = data.get("sql", "")

    markers = []
    for line in markers_file.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            markers.append(stripped)

    result = MarkerResult()
    for marker in markers:
        if marker in sql:
            result.present.append(marker)
        else:
            result.missing.append(marker)
    return result


def save_fingerprint(fingerprint: Fingerprint, path: Path) -> None:
    """Save single fingerprint (v1 legacy format)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(fingerprint) + "\n")


def save_fingerprint_map(fp_map: FingerprintMap, path: Path) -> None:
    """Save fingerprint map (v2 JSON format) with atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 2, "files": fp_map.files}
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_fingerprint(path: Path) -> Optional[Fingerprint]:
    """Load v1 fingerprint (plain text: hash sql_length)."""
    if not path.exists():
        return None
    text = path.read_text().strip()
    parts = text.split()
    if len(parts) != 2:
        log.debug("Malformed fingerprint file: %s", path)
        return None
    try:
        return Fingerprint(hash=parts[0], sql_length=int(parts[1]))
    except (ValueError, IndexError):
        log.debug("Invalid fingerprint values in: %s", path)
        return None


def load_fingerprint_map(path: Path) -> Optional[FingerprintMap]:
    """Load fingerprint map. Handles v2 JSON and detects v1 (returns None for v1)."""
    if not path.exists():
        return None
    text = path.read_text().strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("version") == 2:
            return FingerprintMap(files=data.get("files", {}))
    except (json.JSONDecodeError, ValueError):
        pass
    log.debug("Fingerprint file is v1 or malformed — will recompute: %s", path)
    return None
