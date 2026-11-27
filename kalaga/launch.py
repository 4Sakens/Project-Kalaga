"""Compose and run the chosen runtime, with logs that make failures diagnosable."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import doctor, gamefs, presets, util
from .config import Config
from .plan import Assessment


@dataclass
class LaunchPlan:
    runtime: str
    argv: list[str]
    cwd: str
    env: dict[str, str]
    log_path: Path
    title_exe: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "runtime": self.runtime,
            "argv": self.argv,
            "cwd": self.cwd,
            "log_path": str(self.log_path),
            "title_exe": self.title_exe,
            "env": {k: v for k, v in sorted(self.env.items()) if k.startswith(("VICTORY_", "XCL_"))},
        }

    def display(self) -> str:
        return " ".join(f'"{a}"' if " " in a else a for a in self.argv)


def _title_exe(scan: gamefs.GameScan) -> str | None:
    if not scan.entry_points:
        return None
    return str(scan.entry_points[0])


def stage_dependencies(assessment: Assessment, cfg: Config) -> list[Path]:
    """Copy the shader compiler next to the runtime executable when needed.

    Both runtimes load ``dxcompiler.dll`` at run time; the Windows SDK normally
    provides it, but a standalone DXC release works just as well. Copying it
    beside the .exe makes the launch self-contained and independent of PATH.
    """

    if assessment.executable is None:
        return []
    source = Path(cfg.runtime.dxc_dir) if cfg.runtime.dxc_dir else None
    if source is None or not source.is_dir():
        return []
    staged: list[Path] = []
    for name in ("dxcompiler.dll", "dxil.dll"):
        candidate = source / name
        if not candidate.is_file():
            continue
        destination = assessment.executable.parent / name
        if destination.is_file() and destination.stat().st_size == candidate.stat().st_size:
            continue
        shutil.copy2(candidate, destination)
        staged.append(destination)
    return staged


def victory_env(cfg: Config, preset: presets.Preset | None) -> tuple[dict[str, str], list[str]]:
    """The environment a victory process gets: inherited, preset, extra_env.

    With a preset, inherited VICTORY_* switches are dropped (paths kept), as
    Belobug's play.ps1 does: a shell that still has, say, the old fork's
    VICTORY_SKIP_PIPELINES from the README's AMD instructions would otherwise
    leave 43 pipelines out of the Belobug runtime (missing effects).
    ``launch`` and ``prepare`` both use this, so the shader cache they fill
    matches (Belobug keys translations on switches such as VICTORY_PORT_CBV).
    """

    env = dict(os.environ)
    notes: list[str] = []
    if preset:
        dropped = sorted(
            k for k in env
            if k.upper().startswith("VICTORY_") and k.upper() not in presets.PATH_VARIABLES
        )
        for key in dropped:
            del env[key]
        if dropped:
            notes.append("preset: ignored inherited " + ", ".join(dropped)
                         + " (put them in [launch.extra_env] to keep them)")
        env.update(presets.environment(preset))
        notes.append(f"preset {preset.name}: {preset.summary}")
    if cfg.runtime.dxc_dir:
        env["VICTORY_DXC_DIR"] = cfg.runtime.dxc_dir
    env.update(cfg.launch.extra_env)
    return env, notes


def compose(assessment: Assessment, scan: gamefs.GameScan, cfg: Config) -> LaunchPlan:
    if assessment.executable is None:
        raise RuntimeError(
            f"{assessment.runtime} is not built; run `kalaga build` first"
        )
    title = _title_exe(scan)
    if not title:
        raise RuntimeError("no title executable found; run `kalaga validate`")

    logs = cfg.logs_dir
    logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = logs / f"{assessment.runtime}-{stamp}.log"

    cwd = str(Path(assessment.executable).parent)

    preset = presets.get(cfg.launch.preset) if cfg.launch.preset else None

    if assessment.runtime == "victory":
        env, notes = victory_env(cfg, preset)
        console = cfg.launch.console or (preset.console if preset else "") or "series-x"
        argv = [str(assessment.executable), "run", title, "--execute"]
        argv += ["--console", console]
        if cfg.launch.log:
            env["VICTORY_LOG"] = cfg.launch.log
        if cfg.launch.warp:
            env["VICTORY_D3D12_WARP"] = "1"
            notes.append("software adapter (WARP): slow, but cannot reset the display driver")
        if cfg.runtime.dxc_dir:
            env["XCL_DXC_DIR"] = cfg.runtime.dxc_dir
        # The runtime reads VICTORY_CONFIG, else ./victory.toml, so run from the
        # source checkout and point at its config explicitly.
        runtime_toml = Path(cfg.runtime.victory_dir) / "victory.toml"
        if runtime_toml.is_file():
            env.setdefault("VICTORY_CONFIG", str(runtime_toml))
            cwd = str(Path(cfg.runtime.victory_dir))
        argv += cfg.launch.extra_args
        env.update(cfg.launch.extra_env)  # still the last word, over VICTORY_LOG too
    else:
        env = dict(os.environ)
        notes = []
        if preset:
            notes.append(f"preset {preset.name} ignored: it is for the victory runtime")
        argv = [str(assessment.executable), "run", str(scan.directory)]
        if cfg.launch.log:
            env["XCL_LOG"] = cfg.launch.log
        if cfg.launch.warp:
            env["XCL_D3D12_WARP"] = "1"
            notes.append("software adapter requested (WARP)")
        argv += cfg.launch.extra_args
        env.update(cfg.launch.extra_env)

    return LaunchPlan(
        runtime=assessment.runtime,
        argv=argv,
        cwd=cwd,
        env=env,
        log_path=log_path,
        title_exe=title,
        notes=notes,
    )


def execute(plan: LaunchPlan, timeout: int = 0, on_spawn=None, echo: bool = True) -> int:
    """Run the plan, teeing output to stdout and the log file.

    ``on_spawn(pid)`` is called once the process exists (kalaga session uses
    it to sample memory); ``echo=False`` writes only to the log.
    """

    with open(plan.log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write(f"# {time.strftime('%Y-%m-%d %H:%M:%S')} {plan.runtime}\n")
        log.write(f"# argv: {plan.display()}\n")
        for key in ("VICTORY_LOG", "VICTORY_D3D12_WARP", "XCL_LOG", "XCL_DXC_DIR"):
            if key in plan.env and plan.env[key]:
                log.write(f"# env {key}={plan.env[key]}\n")
        log.flush()

        proc = subprocess.Popen(
            plan.argv,
            cwd=plan.cwd,
            env=plan.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        if on_spawn is not None:
            on_spawn(proc.pid)
        deadline = time.time() + timeout if timeout else None
        try:
            for line in proc.stdout:
                if echo:
                    print(line, end="")
                log.write(line)
                log.flush()
                if deadline and time.time() > deadline:
                    proc.terminate()
                    notes = f"# timed out after {timeout}s\n"
                    print(notes, end="")
                    log.write(notes)
                    break
        except KeyboardInterrupt:  # pragma: no cover - interactive
            proc.terminate()
        finally:
            try:
                code = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                proc.kill()
                code = proc.wait()
    return code


def crash_log(env: doctor.Environment, cfg: Config) -> Path:
    """The runtime keeps crashes next to the title's data folder."""

    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData/Local")
    return Path(local) / "victory" / "data" / "crashes.log"


def tail(path: Path, lines: int = 20) -> str:
    if not path.is_file():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(content[-lines:])


def summary(plan: LaunchPlan, exit_code: int, cfg: Config) -> str:
    parts = [f"{plan.runtime} exited with code {exit_code} (0x{exit_code & 0xFFFFFFFF:08X})"]
    if plan.log_path.is_file():
        parts.append(f"log: {plan.log_path}")
    crashes = crash_log(doctor.Environment(), cfg)
    if crashes.is_file():
        last = tail(crashes, 12)
        if last:
            parts.append(f"crashes.log (last lines):\n{last}")
    code = exit_code & 0xFFFFFFFF
    hints = {
        0xC0000005: "access violation inside the title; capture a crash dump with "
        "VICTORY_CRASH_SAVE / VICTORY_D3D12_DRED=1",
        0x887A0005: "D3D12 device removed (GPU hang or driver reset); retry with --warp",
        0x1455 & 0xFFFFFFFF: "Windows error 1455: not enough commit; close applications "
        "or grow the paging file",
    }
    if code in hints:
        parts.append("hint: " + hints[code])
    return "\n".join(parts)
