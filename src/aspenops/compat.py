"""Windows COM discovery for Aspen Plus Automation Server."""

from __future__ import annotations

import importlib
import os
import platform
import re
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from aspenops.errors import CompatibilityError

_PROGID_RE = re.compile(r"^Apwn\.Document(?:\.(\d+)(?:\.(\d+))?)?$")


@dataclass(frozen=True)
class ProgIdInfo:
    progid: str
    major: int | None
    minor: int | None
    registry_view: str
    clsid: str | None = None

    @property
    def sort_key(self) -> tuple[int, int, int]:
        if self.major is None:
            return (-1, -1, 0)
        return (self.major, self.minor or 0, 1)


def parse_progid(
    progid: str, registry_view: str = "unknown", clsid: str | None = None
) -> ProgIdInfo:
    match = _PROGID_RE.fullmatch(progid)
    if not match:
        raise CompatibilityError(f"Unsupported Aspen ProgID: {progid}")
    major = int(match.group(1)) if match.group(1) else None
    minor = int(match.group(2)) if match.group(2) else None
    return ProgIdInfo(
        progid=progid, major=major, minor=minor, registry_view=registry_view, clsid=clsid
    )


def order_progids(items: Iterable[ProgIdInfo]) -> list[ProgIdInfo]:
    deduped: dict[str, ProgIdInfo] = {}
    for item in items:
        current = deduped.get(item.progid)
        if current is None or current.registry_view == "32-bit":
            deduped[item.progid] = item
    return sorted(deduped.values(), key=lambda item: item.sort_key, reverse=True)


def discover_aspen_progids() -> list[ProgIdInfo]:
    override = os.getenv("ASPENOPS_PROGID")
    if override:
        return [parse_progid(override, registry_view="environment")]
    if platform.system() != "Windows":
        return []

    winreg: Any = importlib.import_module("winreg")

    discovered: list[ProgIdInfo] = []
    views = (("64-bit", winreg.KEY_WOW64_64KEY), ("32-bit", winreg.KEY_WOW64_32KEY))
    for view_name, view_flag in views:
        try:
            root = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "", 0, winreg.KEY_READ | view_flag)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if not _PROGID_RE.fullmatch(name):
                    continue
                clsid = _read_clsid(winreg, name, view_flag)
                discovered.append(parse_progid(name, view_name, clsid))
    return order_progids(discovered)


def candidate_progids() -> list[str]:
    ordered = [item.progid for item in discover_aspen_progids()]
    if "Apwn.Document" not in ordered:
        ordered.append("Apwn.Document")
    return ordered


def _read_clsid(winreg: Any, progid: str, view_flag: int) -> str | None:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            f"{progid}\\CLSID",
            0,
            winreg.KEY_READ | view_flag,
        )
    except OSError:
        return None
    with key:
        try:
            value, _ = winreg.QueryValueEx(key, None)
        except OSError:
            return None
    return str(value)


def probe_aspen_automation() -> dict[str, str | None]:
    """Create and immediately close one Automation document to verify COM registration."""
    if platform.system() != "Windows":
        raise CompatibilityError("Aspen Automation probing requires Windows")
    try:
        pythoncom: Any = importlib.import_module("pythoncom")
        win32com_client: Any = importlib.import_module("win32com.client")
    except ImportError as exc:
        raise CompatibilityError("Install the 'windows' extra to probe Aspen") from exc
    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    errors: list[str] = []
    try:
        for progid in candidate_progids():
            document = None
            try:
                document = win32com_client.DispatchEx(progid)
                version = None
                for name in ("Version", "ProductVersion", "ApplicationVersion"):
                    try:
                        value = getattr(document, name)
                    except Exception:
                        continue
                    if value is not None:
                        version = str(value)
                        break
                return {"progid": progid, "version": version}
            except Exception as exc:
                errors.append(f"{progid}: {exc}")
            finally:
                if document is not None:
                    for name in ("Close", "Quit"):
                        method = getattr(document, name, None)
                        if callable(method):
                            with suppress(Exception):
                                method()
        raise CompatibilityError("No Aspen ProgID could be created: " + "; ".join(errors))
    finally:
        pythoncom.CoUninitialize()
