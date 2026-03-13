"""Content fingerprinting and marker checking for dataset YAMLs."""
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class Fingerprint:
    hash: str
    sql_length: int

    def __str__(self) -> str:
        return f"{self.hash}  {self.sql_length}"


@dataclass
class MarkerResult:
    present: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    @property
    def all_present(self) -> bool:
        return len(self.missing) == 0


def compute_fingerprint(dataset_yaml: Path) -> Fingerprint:
    """Compute SHA-256 fingerprint of the SQL field in a dataset YAML."""
    with open(dataset_yaml) as f:
        data = yaml.safe_load(f)
    sql = data.get("sql", "")
    h = hashlib.sha256(sql.encode()).hexdigest()[:16]
    return Fingerprint(hash=h, sql_length=len(sql))


def check_markers(dataset_yaml: Path, markers_file: Path) -> MarkerResult:
    """Check that all markers in markers_file exist in the dataset SQL."""
    with open(dataset_yaml) as f:
        data = yaml.safe_load(f)
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
    path.write_text(str(fingerprint) + "\n")


def load_fingerprint(path: Path) -> Optional[Fingerprint]:
    if not path.exists():
        return None
    text = path.read_text().strip()
    parts = text.split()
    if len(parts) != 2:
        return None
    return Fingerprint(hash=parts[0], sql_length=int(parts[1]))
