"""UUID-based deduplication for chart/dataset YAMLs."""
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import yaml
except ImportError:
    from scripts.deps import ensure_package
    ensure_package("yaml")
    import yaml

from scripts.logger import get_logger

log = get_logger("dedup")

_ID_SUFFIX_RE = re.compile(r"_\d+\.yaml$")


def find_duplicates(directory: Path) -> Dict[str, List[Tuple[float, Path]]]:
    """Scan directory for YAML files with duplicate UUIDs.

    Returns: {uuid: [(mtime, path), ...]} for UUIDs with >1 file.
    """
    uuid_map: Dict[str, List[Tuple[float, Path]]] = defaultdict(list)
    for f in sorted(directory.glob("*.yaml")):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                continue
            uuid = data.get("uuid", "")
            if not uuid:
                continue
            uuid_map[uuid].append((os.path.getmtime(f), f))
        except (yaml.YAMLError, OSError) as e:
            log.warning("Skipping %s: %s", f.name, e)
            continue
    return {k: v for k, v in uuid_map.items() if len(v) > 1}


def pick_keeper(files: List[Tuple[float, Path]]) -> Path:
    """Pick which file to keep from duplicates.

    Preference: file without numeric ID suffix (preserves script references),
    then newest by mtime.
    """
    no_id = [(m, f) for m, f in files if not _ID_SUFFIX_RE.search(f.name)]
    if len(no_id) == 1:
        return no_id[0][1]
    sorted_files = sorted(files, key=lambda x: x[0], reverse=True)
    return sorted_files[0][1]


def apply_dedup(directory: Path, dry_run: bool = False) -> int:
    """Remove duplicate YAML files. Returns count of files removed."""
    dupes = find_duplicates(directory)
    removed = 0
    for uuid, files in sorted(dupes.items()):
        keeper = pick_keeper(files)
        for _, f in files:
            if f == keeper:
                continue
            if dry_run:
                log.info("Would remove: %s", f.name)
            else:
                f.unlink()
                log.info("Removed duplicate: %s", f.name)
            removed += 1
    return removed
