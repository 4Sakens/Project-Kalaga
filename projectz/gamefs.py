"""Locate and validate an Xbox GDK game dump without touching its contents.

Everything here is read-only and cheap: identity comes from
``MicrosoftGame.Config`` and archive sanity from the first four bytes of each
``.rpf``, so validating a 200 GiB install costs a directory walk and two dozen
tiny reads rather than a full hash.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from . import bencode

CONFIG_NAME = "MicrosoftGame.Config"
# A GTA-era RPF starts with the little-endian magic 0x52504639, i.e. "RPF9"
# stored as b"9FPR". Every archive of the 1.0.2.1 Xbox build uses it.
RPF9_MAGIC = b"9FPR"
SUPPORTED_MAGICS = {RPF9_MAGIC: "RPF9"}


@dataclass
class Issue:
    severity: str  # "error" | "warn"
    code: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity}] {self.code}: {self.detail}"


@dataclass
class GameIdentity:
    title_id: str = ""
    version: str = ""
    name: str = ""
    publisher: str = ""
    executable: str = ""
    store_id: str = ""
    package_name: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.title_id and self.version and self.executable)


@dataclass
class GameScan:
    directory: Path | None = None
    identity: GameIdentity = field(default_factory=GameIdentity)
    total_bytes: int = 0
    file_count: int = 0
    entry_points: list[Path] = field(default_factory=list)
    rpf_paths: list[Path] = field(default_factory=list)
    bad_archives: list[tuple[Path, bytes]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.directory) and not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warn"]

    def to_dict(self) -> dict:
        return {
            "directory": str(self.directory) if self.directory else None,
            "ok": self.ok,
            "identity": {
                "title_id": self.identity.title_id,
                "version": self.identity.version,
                "name": self.identity.name,
                "publisher": self.identity.publisher,
                "executable": self.identity.executable,
                "store_id": self.identity.store_id,
                "package_name": self.identity.package_name,
            },
            "total_bytes": self.total_bytes,
            "file_count": self.file_count,
            "entry_points": [str(p) for p in self.entry_points],
            "rpf_count": len(self.rpf_paths),
            "bad_archives": [
                {"path": str(p), "magic": h.hex(" ")} for p, h in self.bad_archives
            ],
            "issues": [
                {"severity": i.severity, "code": i.code, "detail": i.detail}
                for i in self.issues
            ],
        }


def read_identity(game_dir: str | os.PathLike) -> GameIdentity:
    """Parse ``MicrosoftGame.Config``; return an empty identity when absent."""

    ident = GameIdentity()
    cfg = Path(game_dir) / CONFIG_NAME
    if not cfg.is_file():
        return ident
    raw = cfg.read_bytes().lstrip(b"\xef\xbb\xbf")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ident
    ident.title_id = (root.findtext("TitleId") or "").strip()
    ident.store_id = (root.findtext("StoreId") or "").strip()
    identity = root.find("Identity")
    if identity is not None:
        ident.version = (identity.get("Version") or "").strip()
        ident.package_name = (identity.get("Name") or "").strip()
    visuals = root.find("ShellVisuals")
    if visuals is not None:
        ident.name = (visuals.get("DefaultDisplayName") or "").strip()
        ident.publisher = (visuals.get("PublisherDisplayName") or "").strip()
    exe = root.find("ExecutableList/Executable")
    if exe is not None:
        ident.executable = (exe.get("Name") or "").strip()
    return ident


def read_magic(path: str | os.PathLike, size: int = 4) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def find_games(root: str | os.PathLike, max_depth: int = 3) -> list[Path]:
    """Find directories under *root* that contain a ``MicrosoftGame.Config``."""

    base = Path(root)
    if not base.is_dir():
        return []
    found: list[Path] = []
    base_depth = len(base.parts)
    for current, dirs, files in os.walk(base):
        here = Path(current)
        depth = len(here.parts) - base_depth
        if CONFIG_NAME in files:
            found.append(here)
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in {"$RECYCLE.BIN", "System Volume Information"}]
    return sorted(found)


def scan(
    game_dir: str | os.PathLike | None,
    *,
    expected_title_id: str = "",
    expected_version: str = "",
    deep: bool = True,
) -> GameScan:
    """Validate a dump's identity, completeness and archive headers."""

    result = GameScan()
    if not game_dir:
        result.issues.append(Issue("error", "no-game-dir", "no game directory configured"))
        return result

    directory = Path(game_dir)
    result.directory = directory
    if not directory.is_dir():
        result.issues.append(
            Issue("error", "game-dir-missing", f"game directory does not exist: {directory}")
        )
        return result

    result.identity = read_identity(directory)
    ident = result.identity
    if not ident.complete:
        result.issues.append(
            Issue(
                "error",
                "no-game-config",
                f"{CONFIG_NAME} missing or unreadable in {directory}",
            )
        )
    else:
        if expected_title_id and ident.title_id.upper() != expected_title_id.upper():
            result.issues.append(
                Issue(
                    "error",
                    "title-mismatch",
                    f"title id {ident.title_id} != expected {expected_title_id}",
                )
            )
        if expected_version and ident.version != expected_version:
            result.issues.append(
                Issue(
                    "error",
                    "version-mismatch",
                    f"version {ident.version} != expected {expected_version}",
                )
            )

    exe = directory / ident.executable if ident.executable else None
    if exe and exe.is_file():
        result.entry_points.append(exe)
    elif ident.executable:
        result.issues.append(
            Issue("error", "exe-missing", f"title executable not found: {ident.executable}")
        )

    if not deep:
        return result

    for current, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {"$RECYCLE.BIN", "System Volume Information"}]
        for name in files:
            path = Path(current) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            result.total_bytes += size
            result.file_count += 1
            if name.lower().endswith(".rpf"):
                result.rpf_paths.append(path)
                magic = read_magic(path)
                if magic not in SUPPORTED_MAGICS:
                    result.bad_archives.append((path, magic))

    if not result.rpf_paths:
        result.issues.append(Issue("error", "no-archives", "no .rpf archives found"))
    for path, magic in result.bad_archives:
        result.issues.append(
            Issue(
                "error",
                "bad-archive",
                f"{path.relative_to(directory)} starts with {magic.hex(' ') or 'nothing'}, "
                "expected RPF9",
            )
        )

    for expected_dir in ("data", "pack"):
        if not (directory / expected_dir).is_dir():
            result.issues.append(
                Issue("warn", "missing-dir", f"expected subdirectory '{expected_dir}' is absent")
            )

    return result


@dataclass
class ManifestReport:
    manifest: Path | None = None
    release: str = ""
    expected_files: int = 0
    present: int = 0
    missing: list[tuple[str, int]] = field(default_factory=list)
    wrong_size: list[tuple[str, int, int]] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    expected_bytes: int = 0
    actual_bytes: int = 0

    @property
    def exact(self) -> bool:
        return not self.missing and not self.wrong_size

    def to_dict(self) -> dict:
        return {
            "manifest": str(self.manifest) if self.manifest else None,
            "release": self.release,
            "expected_files": self.expected_files,
            "present": self.present,
            "missing": len(self.missing),
            "wrong_size": len(self.wrong_size),
            "extra": self.extra,
            "expected_bytes": self.expected_bytes,
            "actual_bytes": self.actual_bytes,
        }


def verify_manifest(game_dir: str | os.PathLike, manifest: str | os.PathLike) -> ManifestReport:
    """Compare a directory against a torrent's file list (names and sizes).

    Piece hashes are deliberately not checked: that would read the whole
    install.  Exact sizes catch truncation, which is the realistic failure.
    """

    report = ManifestReport(manifest=Path(manifest))
    try:
        name, entries = bencode.file_entries(manifest)
    except (OSError, bencode.BencodeError) as exc:
        report.release = f"unreadable manifest: {exc}"
        return report

    directory = Path(game_dir)
    report.release = name
    report.expected_files = len(entries)
    report.expected_bytes = sum(length for _rel, length in entries)
    listed: set[str] = set()
    for rel, length in entries:
        listed.add(rel.lower())
        path = directory / rel
        if not path.is_file():
            report.missing.append((rel, length))
            continue
        report.present += 1
        size = path.stat().st_size
        report.actual_bytes += size
        if size != length:
            report.wrong_size.append((rel, length, size))

    for current, _dirs, files in os.walk(directory):
        for filename in files:
            rel = os.path.relpath(os.path.join(current, filename), directory)
            if rel.lower() not in listed:
                report.extra.append(rel)
    report.extra.sort()
    return report
