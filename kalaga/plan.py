"""Decide which runtime can actually run the title, and why not.

The planner turns "is my machine ready?" into an explicit list of blockers with
the exact fix for each, instead of a single opaque failure when something is
missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import doctor, gamefs
from .config import Config

RUNTIMES = ("victory", "xcl")


@dataclass
class Blocker:
    code: str
    message: str
    fix: str = ""
    severity: str = "error"  # "error" blocks, "warn" only degrades

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass
class Assessment:
    runtime: str
    game_ok: bool = False
    can_build: bool = False
    can_run: bool = False
    blockers: list[Blocker] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    executable: Path | None = None
    source_dir: Path | None = None
    build_command: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Blocker]:
        return [b for b in self.blockers if b.severity == "error"]

    @property
    def warnings(self) -> list[Blocker]:
        return [b for b in self.blockers if b.severity == "warn"]

    def to_dict(self) -> dict:
        return {
            "runtime": self.runtime,
            "game_ok": self.game_ok,
            "can_build": self.can_build,
            "can_run": self.can_run,
            "executable": str(self.executable) if self.executable else None,
            "source_dir": str(self.source_dir) if self.source_dir else None,
            "build_command": self.build_command,
            "blockers": [b.to_dict() for b in self.blockers],
            "notes": self.notes,
        }


def _gnu_target(cfg: Config) -> bool:
    return "gnu" in cfg.runtime.target.lower()


def _buildable_source(
    source_dir: Path,
    env: doctor.Environment,
    assessment: Assessment,
    cfg: Config,
) -> bool:
    if not (source_dir / "Cargo.toml").is_file():
        assessment.blockers.append(
            Blocker(
                "source-missing",
                f"no Rust crate found at {source_dir}",
                "clone the runtime next to this repository and set runtime."
                f"{'victory_dir' if 'V' in str(source_dir) else 'xcl_dir'} in kalaga.toml",
            )
        )
        return False
    cargo = env.tool("cargo")
    if not cargo.present:
        assessment.blockers.append(
            Blocker(
                "no-cargo",
                "cargo is not installed",
                "install Rust (https://rustup.rs), then rerun `kalaga doctor`",
            )
        )
        return False
    if _gnu_target(cfg):
        if not (env.tool("gcc").present or env.tool("link").present):
            assessment.blockers.append(
                Blocker(
                    "no-linker",
                    "no linker for the GNU target: gcc was not found",
                    "install mingw-w64 (or set runtime.toolchain_bin to its bin folder) "
                    "and rerun `kalaga doctor`",
                )
            )
            return False
        return True

    if not env.tool("link").present:
        assessment.blockers.append(
            Blocker(
                "no-linker",
                "the MSVC linker (link.exe) is missing: Rust cannot produce an .exe",
                "install Visual Studio 2022 Build Tools with the 'Desktop development with "
                "C++' workload, or set runtime.target to a *-windows-gnu triple and "
                "runtime.toolchain_bin to a mingw-w64 bin folder",
            )
        )
        return False
    return True


def _runtime_dir(runtime: str, cfg: Config) -> Path:
    return Path(cfg.runtime.victory_dir if runtime == "victory" else cfg.runtime.xcl_dir)


def _exe_candidates(source_dir: Path, target: str, profile: str, name: str) -> list[Path]:
    """Output paths, target-triple first when a cross/target build is configured."""

    candidates: list[Path] = []
    if target:
        candidates.append(source_dir / "target" / target / profile / name)
    candidates.append(source_dir / "target" / profile / name)
    return candidates


def _build_argv(
    env: doctor.Environment,
    package: str,
    target: str,
    toolchain: str = "",
    profile: str = "release",
) -> list[str]:
    argv = [env.tool("cargo").path or "cargo"]
    if toolchain:
        argv.append(f"+{toolchain}")
    if profile == "diag":
        argv += ["build", "--profile", "diag", "-p", package, "--features", "diagnostics"]
    else:
        argv += ["build", "--release", "-p", package]
    if target:
        argv += ["--target", target]
    return argv


def assess(
    runtime: str,
    env: doctor.Environment,
    scan: gamefs.GameScan,
    cfg: Config,
) -> Assessment:
    if runtime not in RUNTIMES:
        raise ValueError(f"unknown runtime {runtime!r}; expected one of {RUNTIMES}")

    result = Assessment(runtime=runtime, source_dir=_runtime_dir(runtime, cfg))
    result.game_ok = scan.ok

    if not scan.ok:
        details = "; ".join(i.detail for i in scan.errors[:3]) or "game files not validated"
        result.blockers.append(
            Blocker("game", f"game files are not usable: {details}", "run `kalaga validate`")
        )

    if not result.source_dir.is_dir():
        result.blockers.append(
            Blocker(
                "source-missing",
                f"runtime source directory not found: {result.source_dir}",
                "clone the runtime or point the config at it",
            )
        )
        return result

    result.can_build = _buildable_source(result.source_dir, env, result, cfg)

    target = cfg.runtime.target
    profiles = (
        ("release", "diag") if cfg.runtime.profile == "release" else ("diag", "release")
    )

    if runtime == "victory":
        for profile in profiles:
            for candidate in _exe_candidates(result.source_dir, target, profile, "victory.exe"):
                if candidate.is_file():
                    result.executable = candidate
                    break
            if result.executable:
                break
        result.build_command = _build_argv(
            env, "victory", target, cfg.runtime.toolchain, cfg.runtime.profile
        )
        if not env.dxcompiler:
            result.blockers.append(
                Blocker(
                    "no-dxcompiler",
                    "dxcompiler.dll was not found: console shaders cannot be translated",
                    "install the Windows SDK (DXC) or set XCL_DXC_DIR to a folder "
                    "containing dxcompiler.dll",
                )
            )
    else:
        for candidate in _exe_candidates(result.source_dir, target, profiles[0], "xcl.exe"):
            if candidate.is_file():
                result.executable = candidate
                break
        result.build_command = _build_argv(
        env, "xcl", target, cfg.runtime.toolchain, cfg.runtime.profile
    )
        if not env.dxcompiler:
            result.blockers.append(
                Blocker(
                    "no-dxcompiler",
                    "dxcompiler.dll was not found: console shaders cannot be translated",
                    "install the Windows SDK (DXC) or set XCL_DXC_DIR",
                )
            )

    if result.executable is None:
        result.blockers.append(
            Blocker(
                "not-built",
                f"{runtime} is not built yet",
                "run `kalaga build`",
                severity="warn",
            )
        )
    elif runtime == "victory":
        result.notes.append(
            "VIctory boots the title and runs its menus at the title's own 30 fps; "
            "the world loads but renders incompletely. Expect 0.5-1.8 s frames there."
        )
        result.notes.append(
            "On a real GPU the world can hang the display driver; use `kalaga launch --warp` "
            "for a software-adapter diagnostics run."
        )

    result.can_run = result.game_ok and result.executable is not None and not result.errors
    return result


def assess_all(env: doctor.Environment, scan: gamefs.GameScan, cfg: Config) -> list[Assessment]:
    return [assess(name, env, scan, cfg) for name in RUNTIMES]


def pick(assessments: list[Assessment], preferred: str) -> Assessment:
    """Prefer the configured runtime when it can run; otherwise the best other."""

    ready = [a for a in assessments if a.can_run]
    if not ready:
        return next((a for a in assessments if a.runtime == preferred), assessments[0])
    for a in ready:
        if a.runtime == preferred:
            return a
    return ready[0]
