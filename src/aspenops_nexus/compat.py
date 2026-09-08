from __future__ import annotations

import importlib
import os
import platform
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ComCandidate:
    product: str
    progid: str
    numeric_version: tuple[int, ...]
    registry_view: str
    pinned: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["numeric_version"] = list(self.numeric_version)
        return data


def parse_numeric_version(progid: str) -> tuple[int, ...]:
    """Extract a sortable numeric suffix without assuming a marketing-version mapping."""
    matches = re.findall(r"\d+", progid)
    return tuple(int(item) for item in matches) if matches else ()


def _candidate_sort_key(item: ComCandidate) -> tuple[int, tuple[int, ...], str]:
    return (1 if item.numeric_version else 0, item.numeric_version, item.progid)


def _enumerate_hkcr(prefixes: Iterable[str]) -> list[tuple[str, str]]:
    if platform.system() != "Windows":
        return []
    winreg: Any = importlib.import_module("winreg")
    prefixes_lower = tuple(prefix.lower() for prefix in prefixes)
    found: set[tuple[str, str]] = set()
    views = (
        ("64-bit", winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
        ("32-bit", winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
    )
    for view_name, flags in views:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "", 0, flags) as root:
                count = int(winreg.QueryInfoKey(root)[0])
                for index in range(count):
                    name = str(winreg.EnumKey(root, index))
                    lowered = name.lower()
                    if any(lowered == p or lowered.startswith(p + ".") for p in prefixes_lower):
                        found.add((name, view_name))
        except OSError:
            continue
    return sorted(found)


def discover_aspen_plus_candidates() -> list[ComCandidate]:
    pinned = os.getenv("ASPENOPS_PROGID", "").strip()
    if pinned:
        return [ComCandidate("aspen_plus", pinned, parse_numeric_version(pinned), "pinned", True)]
    candidates = [
        ComCandidate("aspen_plus", name, parse_numeric_version(name), view)
        for name, view in _enumerate_hkcr(("Apwn.Document",))
        if re.fullmatch(r"Apwn\.Document(?:\.\d+(?:\.\d+)*)?", name, re.IGNORECASE)
    ]
    if not any(item.progid.lower() == "apwn.document" for item in candidates):
        candidates.append(ComCandidate("aspen_plus", "Apwn.Document", (), "fallback"))
    dedup: dict[str, ComCandidate] = {}
    for item in candidates:
        current = dedup.get(item.progid.lower())
        if current is None or current.registry_view == "32-bit":
            dedup[item.progid.lower()] = item
    return sorted(dedup.values(), key=_candidate_sort_key, reverse=True)


def discover_hysys_candidates() -> list[ComCandidate]:
    pinned = os.getenv("ASPENOPS_HYSYS_PROGID", "").strip()
    if pinned:
        return [ComCandidate("hysys", pinned, parse_numeric_version(pinned), "pinned", True)]
    names = _enumerate_hkcr(("HYSYS.Application",))
    candidates = [
        ComCandidate("hysys", name, parse_numeric_version(name), view)
        for name, view in names
        if re.fullmatch(r"HYSYS\.Application(?:\.\d+(?:\.\d+)*)?", name, re.IGNORECASE)
    ]
    if not any(item.progid.lower() == "hysys.application" for item in candidates):
        candidates.append(ComCandidate("hysys", "HYSYS.Application", (), "fallback"))
    dedup = {item.progid.lower(): item for item in candidates}
    return sorted(dedup.values(), key=_candidate_sort_key, reverse=True)


def compatibility_report() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "strategy": (
            "Discover registered COM Automation Servers at runtime; try numeric registrations "
            "newest-first; retain the unversioned ProgID as fallback; never infer support from a "
            "marketing-version table."
        ),
        "aspen_plus": [item.to_dict() for item in discover_aspen_plus_candidates()],
        "hysys": [item.to_dict() for item in discover_hysys_candidates()],
    }
