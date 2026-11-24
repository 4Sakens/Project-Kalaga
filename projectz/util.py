"""Small process / formatting helpers shared by the Project-Z tools."""

from __future__ import annotations

import json
import subprocess
from typing import Iterable, Sequence

GIB = 1024**3


def run(
    cmd: Sequence[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    stdin: str | None = None,
) -> tuple[int, str, str]:
    """Run a command, never raising for the usual failure modes.

    Returns ``(returncode, stdout, stderr)``.  A missing executable reports 127
    and a timeout reports 124, so callers can treat "not installed" as data
    instead of an exception.
    """

    try:
        proc = subprocess.run(
            list(cmd),
            cwd=cwd,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", f"executable not found: {cmd[0]}"
    except PermissionError as exc:  # pragma: no cover - platform specific
        return 126, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(cmd)}"


def powershell_json(script: str, timeout: int = 60):
    """Run a PowerShell snippet that emits JSON and return the decoded value."""

    rc, out, _err = run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )
    if rc != 0:
        return None
    text = out.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def gib(value: float | int | None) -> float:
    if not value:
        return 0.0
    return round(float(value) / GIB, 1)


def human_bytes(value: float | int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TiB"


def format_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    rows = [[str(c) for c in row] for row in rows]
    headers = [str(h) for h in headers]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def write_json(path: str, payload) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
