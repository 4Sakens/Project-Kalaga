"""kalaga session: play each preset for a few minutes and get one table back.

Each run starts the title with one preset, keeps it going for the set time
while you play the same stretch, samples the game's private memory and
dedicated graphics memory, then stops it. The numbers come from the runtime's
own once-a-second frame line, the same in VIctory-RDNA, Belobug and Vice-Tay:

    21.3 fps, 46.9 ms/frame (29.5 preparing: ...; 12.0 on the GPU; ...),
    1840 draws/frame, dropped 3 without a host pipeline (1 being made) ...

Only seconds with more than 1,000 draws count as "in the world" (Vice-Tay's
rule), so loading screens and menus do not flatter or sink the numbers.
"""

from __future__ import annotations

import re
import statistics
import subprocess
import sys
import threading
from dataclasses import dataclass, field

FRAME_LINE = re.compile(
    r"(?P<fps>\d+(?:\.\d+)?) fps, (?P<ms>\d+(?:\.\d+)?) ms/frame "
    r"\((?P<cpu>\d+(?:\.\d+)?) preparing:.*?; (?P<gpu>\d+(?:\.\d+)?) on the GPU;.*?\), "
    r"(?P<draws>\d+) draws/frame, dropped (?P<dropped>\d+) without a host pipeline "
    r"\((?P<making>\d+) being made\)"
)
WORLD_DRAWS = 1000
# A second under this many fps counts as a hitch.
HITCH_FPS = 10.0


@dataclass
class Second:
    fps: float
    ms: float
    cpu: float
    gpu: float
    draws: int
    dropped: int
    making: int


def parse(text: str) -> list[Second]:
    out = []
    for m in FRAME_LINE.finditer(text):
        out.append(Second(
            fps=float(m["fps"]), ms=float(m["ms"]), cpu=float(m["cpu"]), gpu=float(m["gpu"]),
            draws=int(m["draws"]), dropped=int(m["dropped"]), making=int(m["making"]),
        ))
    return out


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1))))
    return ordered[k]


@dataclass
class Result:
    preset: str
    seconds: list[Second] = field(default_factory=list)
    ram_peak_gb: float | None = None
    vram_peak_gb: float | None = None
    exit_code: int | str | None = None
    log: str = ""

    @property
    def world(self) -> list[Second]:
        return [s for s in self.seconds if s.draws > WORLD_DRAWS]

    def stats(self) -> dict[str, float]:
        w = self.world
        fps = [s.fps for s in w]
        if not w:
            return {"world_s": 0}
        return {
            "world_s": len(w),
            "fps_median": statistics.median(fps),
            "fps_p10": _pct(fps, 10),
            "fps_p90": _pct(fps, 90),
            "fps_1pct": _pct(fps, 1),
            "cpu_ms": statistics.median(s.cpu for s in w),
            "gpu_ms": statistics.median(s.gpu for s in w),
            "hitches": sum(1 for s in w if s.fps < HITCH_FPS),
            "dropped": statistics.mean(s.dropped for s in w),
        }

    def bound(self) -> str:
        """Which side the frame waits on: preparing (CPU) or the GPU."""

        st = self.stats()
        if not st.get("world_s"):
            return "-"
        cpu, gpu = st["cpu_ms"], st["gpu_ms"]
        if cpu > gpu * 1.2:
            return "CPU"
        if gpu > cpu * 1.2:
            return "GPU"
        return "both"


def exit_label(code: int | None, log_text: str) -> int | str | None:
    """'time up' for a run kalaga stopped on schedule; else the exit code (a crash, if not 0)."""

    if "# timed out after" in log_text:
        return "time up"
    return code


def table(results: list[Result]) -> str:
    lines = [
        "| Preset | In world | fps median (p10-p90; 1% low) | Prep / GPU ms | Bound | Hitches <10 fps | "
        "Dropped draws | Peak RAM | Peak VRAM | Exit |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        st = r.stats()
        gb = lambda v: f"{v:.1f} GB" if v is not None else "n/a"
        if not st.get("world_s"):
            lines.append(f"| `{r.preset}` | 0 s (never reached the world) | - | - | - | - | - | "
                         f"{gb(r.ram_peak_gb)} | {gb(r.vram_peak_gb)} | {r.exit_code} |")
            continue
        lines.append(
            f"| `{r.preset}` | {st['world_s']} s | {st['fps_median']:.1f} "
            f"({st['fps_p10']:.1f}-{st['fps_p90']:.1f}; {st['fps_1pct']:.1f}) | "
            f"{st['cpu_ms']:.1f} / {st['gpu_ms']:.1f} | {r.bound()} | {st['hitches']} | "
            f"{st['dropped']:.1f}/frame | {gb(r.ram_peak_gb)} | {gb(r.vram_peak_gb)} | {r.exit_code} |"
        )
    return "\n".join(lines)


class MemorySampler:
    """Peak private bytes and dedicated GPU memory of one process (Windows).

    One PowerShell call every ``interval`` seconds: Get-Process for private
    bytes and the "GPU Process Memory" counter for dedicated (card) memory.
    """

    SCRIPT = (
        "$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
        "if(-not $p){{exit 1}};"
        "$v=(Get-Counter '\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage' -ErrorAction SilentlyContinue)"
        ".CounterSamples|Measure-Object CookedValue -Sum;"
        "Write-Output \"$($p.PrivateMemorySize64) $([int64]$v.Sum)\""
    )

    def __init__(self, interval: float = 20.0) -> None:
        self.interval = interval
        self.ram_peak = 0
        self.vram_peak = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, pid: int) -> None:
        if sys.platform != "win32":
            return
        self._thread = threading.Thread(target=self._run, args=(pid,), daemon=True)
        self._thread.start()

    def _run(self, pid: int) -> None:
        while not self._stop.wait(self.interval):
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", self.SCRIPT.format(pid=pid)],
                    capture_output=True, text=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ).stdout.split()
            except (OSError, subprocess.TimeoutExpired):
                continue
            if len(out) == 2 and all(x.isdigit() for x in out):
                self.ram_peak = max(self.ram_peak, int(out[0]))
                self.vram_peak = max(self.vram_peak, int(out[1]))

    def stop(self) -> tuple[float | None, float | None]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=20)
        gb = lambda b: b / 2**30 if b else None
        return gb(self.ram_peak), gb(self.vram_peak)
