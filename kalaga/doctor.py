"""Environment discovery: hardware, toolchain, shader compiler, VS build tools.

Nothing is assumed about PATH: Rust installed with ``--no-modify-path`` still
appears because the default cargo home is checked directly.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import util

VSWHERE = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
WINDOWS_KITS = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")


@dataclass
class ToolInfo:
    name: str
    path: str | None = None
    version: str | None = None

    @property
    def present(self) -> bool:
        return bool(self.path)

    def to_dict(self) -> dict:
        return {"present": self.present, "path": self.path, "version": self.version}


@dataclass
class Environment:
    os_caption: str = ""
    os_version: str = ""
    os_build: str = ""
    gpu: str = ""
    gpu_driver: str = ""
    gpu_reported_gib: float = 0.0
    ram_gib: float = 0.0
    tools: dict[str, ToolInfo] = field(default_factory=dict)
    vs_install: str = ""
    dxcompiler: str = ""
    cargo_home: str = ""

    def tool(self, name: str) -> ToolInfo:
        return self.tools.get(name, ToolInfo(name))

    def to_dict(self) -> dict:
        return {
            "os": f"{self.os_caption} {self.os_version} (build {self.os_build})".strip(),
            "gpu": {
                "name": self.gpu,
                "driver": self.gpu_driver,
                "reported_gib": self.gpu_reported_gib,
            },
            "ram_gib": self.ram_gib,
            "tools": {name: tool.to_dict() for name, tool in self.tools.items()},
            "vs_install": self.vs_install,
            "dxcompiler": self.dxcompiler,
            "cargo_home": self.cargo_home,
        }


def _find_cargo_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    candidate = Path(home) / ".cargo" / "bin" / f"{name}.exe"
    return str(candidate) if candidate.is_file() else None


def _version_of(path: str | None, args: tuple[str, ...] = ("--version",)) -> str | None:
    if not path:
        return None
    rc, out, err = util.run([path, *args], timeout=30)
    text = (out or err).strip().splitlines()
    return text[0].strip() if rc == 0 and text else None


def _detect_vs() -> tuple[str, str | None]:
    """Return ``(installation_path, link.exe)`` for VS with the C++ workload."""

    if not VSWHERE.is_file():
        return "", None
    rc, out, _ = util.run(
        [
            str(VSWHERE),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        timeout=60,
    )
    if rc != 0 or not out.strip():
        return "", None
    install = Path(out.strip().splitlines()[0])
    links = sorted(install.glob("VC/Tools/MSVC/*/bin/Hostx64/x64/link.exe"))
    linker = links[-1] if links else None
    return str(install), str(linker) if linker else None


def _find_dxcompiler(victory_dir: str = "", xcl_dir: str = "", configured: str = "") -> str:
    """Locate ``dxcompiler.dll``: config, env override, build output, then the SDK."""

    env_dir = configured or os.environ.get("XCL_DXC_DIR") or os.environ.get("VICTORY_DXC_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if candidate.is_file():
            return str(candidate)
        found = candidate / "dxcompiler.dll"
        if found.is_file():
            return str(found)

    for root in (victory_dir, xcl_dir):
        if not root:
            continue
        for pattern in ("target/release/dxcompiler.dll", "target/diag/dxcompiler.dll"):
            candidate = Path(root) / pattern
            if candidate.is_file():
                return str(candidate)

    if WINDOWS_KITS.is_dir():
        candidates = sorted(WINDOWS_KITS.glob("*/x64/dxcompiler.dll"))
        if candidates:
            return str(candidates[-1])
    return ""


def _find_gcc(toolchain_bin: str = "") -> str | None:
    if toolchain_bin:
        candidate = Path(toolchain_bin) / "gcc.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("gcc")


def detect(
    *,
    victory_dir: str = "",
    xcl_dir: str = "",
    game_dir: str = "",
    dxc_dir: str = "",
    toolchain_bin: str = "",
) -> Environment:
    env = Environment()

    os_info = util.powershell_json(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption,Version,BuildNumber | ConvertTo-Json -Compress"
    )
    if isinstance(os_info, dict):
        env.os_caption = str(os_info.get("Caption") or "")
        env.os_version = str(os_info.get("Version") or "")
        env.os_build = str(os_info.get("BuildNumber") or "")

    gpus = util.powershell_json(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,DriverVersion,AdapterRAM | ConvertTo-Json -Compress"
    )
    if isinstance(gpus, dict):
        gpus = [gpus]
    for gpu in gpus or []:
        if not isinstance(gpu, dict):
            continue
        name = str(gpu.get("Name") or "")
        if not name or "remote" in name.lower():
            continue
        env.gpu = name
        env.gpu_driver = str(gpu.get("DriverVersion") or "")
        env.gpu_reported_gib = util.gib(gpu.get("AdapterRAM"))
        break

    memory = util.powershell_json(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object TotalPhysicalMemory | ConvertTo-Json -Compress"
    )
    if isinstance(memory, dict):
        env.ram_gib = util.gib(memory.get("TotalPhysicalMemory"))

    env.vs_install, linker = _detect_vs()
    env.dxcompiler = _find_dxcompiler(victory_dir, xcl_dir, dxc_dir)
    env.cargo_home = str(Path(os.environ.get("USERPROFILE") or "") / ".cargo")

    cargo = _find_cargo_bin("cargo")
    rustc = _find_cargo_bin("rustc")
    rustup = _find_cargo_bin("rustup")
    env.tools = {
        "cargo": ToolInfo("cargo", cargo, _version_of(cargo)),
        "rustc": ToolInfo("rustc", rustc, _version_of(rustc)),
        "rustup": ToolInfo("rustup", rustup, _version_of(rustup)),
        "link": ToolInfo("link", linker, _version_of(linker, ("/?" ,))),
        "gcc": ToolInfo("gcc", _find_gcc(toolchain_bin), _version_of(_find_gcc(toolchain_bin))),
        "dxcompiler": ToolInfo("dxcompiler", env.dxcompiler or None, "found" if env.dxcompiler else None),
        "dotnet": ToolInfo("dotnet", shutil.which("dotnet"), _version_of(shutil.which("dotnet"))),
        "cmake": ToolInfo("cmake", shutil.which("cmake"), _version_of(shutil.which("cmake"))),
        "python": ToolInfo("python", shutil.which("python"), _version_of(shutil.which("python"))),
        "git": ToolInfo("git", shutil.which("git"), _version_of(shutil.which("git"))),
    }
    return env


def disk_free_gib(path: str | os.PathLike) -> float:
    try:
        target = Path(path)
        root = target.anchor or str(target)
        return round(shutil.disk_usage(root).free / util.GIB, 1)
    except OSError:
        try:
            return round(shutil.disk_usage(Path.cwd()).free / util.GIB, 1)
        except OSError:  # pragma: no cover - defensive
            return 0.0
