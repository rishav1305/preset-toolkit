"""Section ownership checking with advisory warnings."""
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

log = get_logger("ownership")


@dataclass
class Section:
    name: str
    owner: Optional[str]
    charts: List[int] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class SharedDataset:
    name: str
    owners: List[str]
    advisory: str = ""


@dataclass
class OwnershipCheck:
    warnings: List[str] = field(default_factory=list)
    shared_dataset_warnings: List[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def has_shared_dataset_warnings(self) -> bool:
        return len(self.shared_dataset_warnings) > 0


class OwnershipMap:
    def __init__(self, sections: Dict[str, Section], shared: List[SharedDataset]):
        self.sections = sections
        self.shared_datasets = shared
        self._chart_index: Dict[int, str] = {}
        for name, sec in sections.items():
            for cid in sec.charts:
                self._chart_index[cid] = name
        self._shared_by_name: Dict[str, SharedDataset] = {sd.name: sd for sd in shared}

    @classmethod
    def load(cls, path: Path) -> "OwnershipMap":
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            log.warning("Could not read ownership file %s: %s", path, e)
            return cls({}, [])
        if not isinstance(data, dict):
            return cls({}, [])

        sections = {}
        for name, sec_data in data.get("sections", {}).items():
            sections[name] = Section(
                name=name,
                owner=sec_data.get("owner"),
                charts=sec_data.get("charts", []),
                datasets=sec_data.get("datasets", []),
                description=sec_data.get("description", ""),
            )

        shared = []
        for sd in data.get("shared_datasets", []):
            name = sd.get("name", "")
            if not name:
                log.debug("Skipping shared_dataset entry without name")
                continue
            shared.append(SharedDataset(
                name=name,
                owners=sd.get("owners", []),
                advisory=sd.get("advisory", ""),
            ))

        return cls(sections, shared)

    def chart_section(self, chart_id: int) -> Optional[str]:
        return self._chart_index.get(chart_id)

    def check(
        self,
        user_email: str,
        changed_charts: Optional[List[int]] = None,
        changed_datasets: Optional[List[str]] = None,
    ) -> OwnershipCheck:
        result = OwnershipCheck()

        for cid in (changed_charts or []):
            section_name = self.chart_section(cid)
            if section_name is None:
                continue
            section = self.sections[section_name]
            if section.owner is None:
                continue
            if section.owner != user_email:
                result.warnings.append(
                    f"Chart {cid} belongs to '{section_name}' "
                    f"(owned by {section.owner}). Notify them before pushing."
                )

        for ds_name in (changed_datasets or []):
            sd = self._shared_by_name.get(ds_name)
            if sd:
                other_owners = [o for o in sd.owners if o != user_email]
                if other_owners:
                    result.shared_dataset_warnings.append(
                        f"Dataset '{ds_name}' is shared. "
                        f"{sd.advisory} Owners: {', '.join(other_owners)}"
                    )

        return result
