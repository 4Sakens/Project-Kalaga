"""Layered configuration for the Project Kalaga launcher.

Resolution order (first hit wins):

1. ``--config PATH`` on the command line
2. ``KALAGA_CONFIG`` environment variable (``PROJECTZ_CONFIG`` still works)
3. ``kalaga.toml`` at the repository root (git-ignored, machine-local), or
   the old ``projectz.toml`` if only that exists
4. built-in defaults

Nothing in this module imports the game or the runtimes; it only describes
where they are expected to live.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_GAME_ROOT = r"D:\GTA 6"
DEFAULT_VICTORY_DIR = r"D:\VIctory"
DEFAULT_XCL_DIR = r"D:\xcl"


@dataclass
class GameConfig:
    directory: str = ""
    root: str = DEFAULT_GAME_ROOT
    expected_title_id: str = "7952987A"
    expected_version: str = "1.0.2.1"
    manifest: str = ""  # optional .torrent used as an integrity manifest
    min_free_gib: float = 8.0


@dataclass
class RuntimeConfig:
    preferred: str = "victory"
    victory_dir: str = DEFAULT_VICTORY_DIR
    xcl_dir: str = DEFAULT_XCL_DIR
    fivestar_dir: str = "fivestar"
    # Rust target triple; empty = host default (x86_64-pc-windows-msvc).
    # A gnullvm triple builds without Visual Studio (bundled lld).
    target: str = ""
    # Folder holding dxcompiler.dll / dxil.dll; empty = auto-detect.
    dxc_dir: str = ""
    # Optional rustup toolchain, e.g. "1.98.1-x86_64-pc-windows-gnu".
    # Empty = the default toolchain (msvc unless rustup was told otherwise).
    toolchain: str = ""
    # Folder prepended to PATH for builds, e.g. a mingw-w64 bin directory.
    toolchain_bin: str = ""
    # Which build to prefer: "release" or "diag" (diagnostics aids).
    profile: str = "release"


@dataclass
class LaunchConfig:
    # Empty = the preset's console, else "series-x".
    console: str = ""
    # A named preset from kalaga/presets.py; empty = none.
    preset: str = ""
    warp: bool = False
    log: str = "info"
    extra_env: dict[str, str] = field(default_factory=dict)
    extra_args: list[str] = field(default_factory=list)
    timeout: int = 0  # 0 = wait for the title to exit


@dataclass
class Config:
    game: GameConfig = field(default_factory=GameConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    launch: LaunchConfig = field(default_factory=LaunchConfig)
    path: Path | None = None
    logs_dir: Path = REPO_ROOT / "logs"

    @property
    def game_dir(self) -> Path | None:
        if self.game.directory:
            return Path(self.game.directory)
        return None

    def manifest_path(self) -> Path | None:
        if self.game.manifest:
            return Path(self.game.manifest)
        if self.game_dir is None:
            return None
        # A release folder usually ships one manifest next to the game folder.
        for candidate in sorted(self.game_dir.parent.glob("*.torrent")):
            return candidate
        return None


def _as_str(value, default: str = "") -> str:
    return str(value) if value is not None else default


def load(path: str | os.PathLike | None = None) -> Config:
    explicit = Path(path) if path else None
    for variable in ("KALAGA_CONFIG", "PROJECTZ_CONFIG"):
        if explicit is None and os.environ.get(variable):
            explicit = Path(os.environ[variable])
    if explicit is None:
        # The project was called Project-Z; an old local config still loads.
        for name in ("kalaga.toml", "projectz.toml"):
            candidate = REPO_ROOT / name
            if candidate.is_file():
                explicit = candidate
                break

    cfg = Config()
    if explicit is None or not explicit.is_file():
        return cfg

    data = tomllib.loads(explicit.read_text(encoding="utf-8"))
    game = data.get("game", {})
    cfg.game = GameConfig(
        directory=_as_str(game.get("dir") or game.get("directory")),
        root=_as_str(game.get("root"), DEFAULT_GAME_ROOT),
        expected_title_id=_as_str(game.get("expected_title_id"), "7952987A"),
        expected_version=_as_str(game.get("expected_version"), "1.0.2.1"),
        manifest=_as_str(game.get("manifest")),
        min_free_gib=float(game.get("min_free_gib", 8.0)),
    )
    runtime = data.get("runtime", {})
    cfg.runtime = RuntimeConfig(
        preferred=_as_str(runtime.get("preferred"), "victory").lower(),
        victory_dir=_as_str(runtime.get("victory_dir"), DEFAULT_VICTORY_DIR),
        xcl_dir=_as_str(runtime.get("xcl_dir"), DEFAULT_XCL_DIR),
        fivestar_dir=_as_str(runtime.get("fivestar_dir"), "fivestar"),
        target=_as_str(runtime.get("target")),
        dxc_dir=_as_str(runtime.get("dxc_dir")),
        toolchain=_as_str(runtime.get("toolchain")),
        toolchain_bin=_as_str(runtime.get("toolchain_bin")),
        profile=_as_str(runtime.get("profile"), "release").lower(),
    )
    launch = data.get("launch", {})
    cfg.launch = LaunchConfig(
        console=_as_str(launch.get("console")).lower(),
        preset=_as_str(launch.get("preset")),
        warp=bool(launch.get("warp", False)),
        log=_as_str(launch.get("log"), "info"),
        extra_env={str(k): str(v) for k, v in (launch.get("extra_env") or {}).items()},
        extra_args=[str(a) for a in (launch.get("extra_args") or [])],
        timeout=int(launch.get("timeout", 0)),
    )
    cfg.path = explicit
    cfg.logs_dir = Path(_as_str(data.get("logs_dir"), str(REPO_ROOT / "logs")))
    return cfg
