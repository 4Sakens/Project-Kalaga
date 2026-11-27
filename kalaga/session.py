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


ASKED_LINE = re.compile(r"the title asks for (?P<name>[\w ]+?) input")


def input_kinds(text: str) -> list[str]:
    """The input kinds the title asked for in a run (the runtime's GameInput log)."""

    seen: list[str] = []
    for m in ASKED_LINE.finditer(text):
        if m["name"] not in seen:
            seen.append(m["name"])
    return seen


def keyboard_prompts_note(kinds: list[str]) -> str:
    """What the kinds asked for say about keyboard button prompts."""

    if not kinds:
        return ("Input kinds: not in this log (a runtime built before Kalaga's GameInput "
                "patch, or the run ended before the menus).")
    kb = [k for k in kinds if k in ("keyboard", "mouse")]
    if kb:
        return (f"Input kinds the game asked for: {', '.join(kinds)}. It asks for {' and '.join(kb)} "
                "itself, so it likely has keyboard play and keyboard button prompts of its own: "
                "worth feeding it a real keyboard and mouse.")
    return (f"Input kinds the game asked for: {', '.join(kinds)}. No keyboard or mouse: it only ever "
            "shows pad prompts, so keyboard prompts need its button icons swapped.")


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


def exit_label(code: int | str | None, log_text: str) -> int | str | None:
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


class ScreenShooter:
    """One screenshot of the screen per run, taken in the world (Windows).

    Fed the runtime's output line by line (``launch.execute(on_line=...)``):
    after ``after`` seconds in the world (frame lines with over
    ``WORLD_DRAWS`` draws) it saves the primary screen as a PNG. The session
    asks the player to stand still in the same spot then, so the presets'
    pictures compare (fuzziness, black textures). Taken with GDI from
    PowerShell: VIctory's full screen is a frameless window, which the
    desktop composes, so the copy shows the game.
    """

    SCRIPT = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "Add-Type -Name U -Namespace K -MemberDefinition "
        "'[DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();';"
        "[void][K.U]::SetProcessDPIAware();"
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
        "$m=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($m);"
        "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
        "$m.Save('{path}',[System.Drawing.Imaging.ImageFormat]::Png)"
    )

    def __init__(self, path, after: int = 20) -> None:
        self.path = path
        self.after = after
        self.world_seconds = 0
        self.taken: bool = False
        self._thread: threading.Thread | None = None

    def feed(self, line: str) -> None:
        if self._thread is not None:
            return
        m = FRAME_LINE.search(line)
        if not m or int(m["draws"]) <= WORLD_DRAWS:
            return
        self.world_seconds += 1
        if self.world_seconds >= self.after and sys.platform == "win32":
            self._thread = threading.Thread(target=self._shoot, daemon=True)
            self._thread.start()

    def _shoot(self) -> None:
        script = self.SCRIPT.format(path=str(self.path).replace("'", "''"))
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return

    def finish(self) -> bool:
        """Waits for a shot in flight; whether a picture was saved."""
        if self._thread is not None:
            self._thread.join(timeout=35)
        from pathlib import Path
        self.taken = Path(self.path).is_file() and Path(self.path).stat().st_size > 0
        return self.taken


# The card's 8 GB less what Windows and the desktop keep: over this a preset
# lives on borrowed system memory (late textures, stutter, device removal).
VRAM_LIMIT_GB = 7.5
# RAM: 32 GiB less ~2.5 for Windows; over it the page file carries the game.
RAM_LIMIT_GB = 29.5
# The frame rate a pick must hold, and how far under the fastest it may be
# for a better picture.
MIN_FPS = 18.0
QUALITY_SLACK = 0.85


def picture_rank(env: dict[str, str], console: str) -> int:
    """Higher = better picture: Series X native 1080p > Series X at a lower
    render scale > Series S."""

    if console != "series-x":
        return 1
    try:
        scale = float(env.get("VICTORY_RENDER_SCALE", "0.667"))
    except ValueError:
        scale = 0.667
    return 3 if scale >= 0.99 else 2


@dataclass
class Pick:
    preset: str | None
    why: str
    dropped: list[tuple[str, str]] = field(default_factory=list)


def choose(results: list[Result], ranks: dict[str, int]) -> Pick:
    """The best-looking preset that plays well, from one session's runs."""

    ok: list[tuple[Result, float]] = []
    dropped: list[tuple[str, str]] = []
    for r in results:
        st = r.stats()
        if r.exit_code not in ("time up", 0):
            dropped.append((r.preset, f"crashed or stopped (exit {r.exit_code})"))
        elif st.get("world_s", 0) < 30:
            dropped.append((r.preset, f"only {st.get('world_s', 0)} s in the world"))
        elif r.vram_peak_gb is not None and r.vram_peak_gb > VRAM_LIMIT_GB:
            dropped.append((r.preset, f"{r.vram_peak_gb:.1f} GB graphics memory (over {VRAM_LIMIT_GB})"))
        elif r.ram_peak_gb is not None and r.ram_peak_gb > RAM_LIMIT_GB:
            dropped.append((r.preset, f"{r.ram_peak_gb:.1f} GB RAM (over {RAM_LIMIT_GB}: paging)"))
        else:
            ok.append((r, st["fps_median"]))
    if not ok:
        return Pick(None, "no preset ran cleanly: start from the -safe preset and send the logs", dropped)
    fastest = max(fps for _, fps in ok)
    floor = max(MIN_FPS, QUALITY_SLACK * fastest)
    good = [(r, fps) for r, fps in ok if fps >= floor]
    if good:
        best, fps = max(good, key=lambda x: (ranks.get(x[0].preset, 0), x[1]))
        why = (f"best picture at {fps:.1f} fps median (fastest clean run {fastest:.1f}; "
               f"picks may be up to {100 - QUALITY_SLACK * 100:.0f} % slower and must hold {MIN_FPS:g})")
    else:
        best, fps = max(ok, key=lambda x: x[1])
        why = f"fastest clean run ({fps:.1f} fps median); none held {floor:.1f} fps"
    return Pick(best.preset, why, dropped)


def set_preset_in_config(text: str, preset: str) -> str:
    """kalaga.toml with [launch] preset set (the section made if missing)."""

    import re

    line = f"preset = '{preset}'"
    m = re.search(r"(?ms)^\[launch\][^\n]*\n(.*?)(?=^\[|\Z)", text)
    if not m:
        return text.rstrip("\n") + f"\n\n[launch]\n{line}\n"
    body = m.group(1)
    if re.search(r"(?m)^\s*preset\s*=", body):
        body = re.sub(r"(?m)^\s*preset\s*=.*$", line, body, count=1)
    else:
        body = line + "\n" + body
    return text[: m.start(1)] + body + text[m.end(1):]
