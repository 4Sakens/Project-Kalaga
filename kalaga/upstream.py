"""Apply a picked upstream-PR series (patches/<runtime>/) to a runtime checkout.

Each patch goes in with ``git am --3way``, one at a time. A patch that does
not apply is backed out and reported, and the rest still go in, so one
upstream change does not cost the whole series. Used by ``kalaga patches``
at home and by .github/workflows/runtimes.yml.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import util
from .config import REPO_ROOT

PATCH_ROOT = REPO_ROOT / "patches"


@dataclass(frozen=True)
class Upstream:
    runtime: str
    repo: str
    branch: str
    commit: str
    patches: tuple[Path, ...]


@dataclass
class Outcome:
    patch: str
    applied: bool
    detail: str = ""


@dataclass
class Report:
    runtime: str
    base: str
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def failed(self) -> list[Outcome]:
        return [o for o in self.outcomes if not o.applied]

    def markdown(self) -> str:
        lines = [
            f"### {self.runtime} @ `{self.base[:12]}`",
            "",
            "| Patch | Result |",
            "|---|---|",
        ]
        for o in self.outcomes:
            result = "applied" if o.applied else f"**did not apply** — {o.detail}"
            lines.append(f"| `{o.patch}` | {result} |")
        lines.append("")
        ok = len(self.outcomes) - len(self.failed)
        lines.append(f"{ok} of {len(self.outcomes)} applied.")
        return "\n".join(lines)


def fingerprint(series: Upstream) -> str:
    """A short hash of the series: its base commit and every patch's bytes.

    Written into the checkout after the series goes in, so ``kalaga home``
    can tell a checkout patched with an older series (after a pull of
    Kalaga) and patch it again on its own.
    """
    import hashlib

    h = hashlib.sha256(series.commit.encode())
    for patch in series.patches:
        h.update(patch.name.encode())
        h.update(patch.read_bytes())
    return h.hexdigest()[:16]


STAMP = "kalaga-series"


def stamp_path(checkout: Path) -> Path:
    """Where the fingerprint of the series last applied is kept (inside .git)."""
    return Path(checkout) / ".git" / STAMP


def applied_fingerprint(checkout: Path) -> str | None:
    try:
        return stamp_path(checkout).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_fingerprint(checkout: Path, series: Upstream) -> None:
    path = stamp_path(checkout)
    if path.parent.is_dir():
        path.write_text(fingerprint(series) + "\n", encoding="utf-8")


def runtimes() -> list[str]:
    if not PATCH_ROOT.is_dir():
        return []
    return sorted(d.name for d in PATCH_ROOT.iterdir() if (d / "UPSTREAM.toml").is_file())


def load(runtime: str, root: Path = PATCH_ROOT) -> Upstream:
    folder = root / runtime
    meta = folder / "UPSTREAM.toml"
    if not meta.is_file():
        known = ", ".join(runtimes()) or "none"
        raise RuntimeError(f"no patch series {runtime!r} (known: {known})")
    data = tomllib.loads(meta.read_text(encoding="utf-8"))
    return Upstream(
        runtime=runtime,
        repo=str(data["repo"]),
        branch=str(data.get("branch", "main")),
        commit=str(data["commit"]),
        patches=tuple(sorted(folder.glob("*.patch"))),
    )


def _git(directory: Path, *args: str, timeout: int = 300) -> tuple[int, str]:
    rc, out, err = util.run(
        ["git", "-c", "user.name=kalaga", "-c", "user.email=kalaga@localhost",
         "-c", "core.autocrlf=false", *args],
        cwd=str(directory),
        timeout=timeout,
    )
    return rc, (out + err).strip()


def apply(upstream: Upstream, directory: Path) -> Report:
    """Apply every patch of the series that goes in; report each one."""

    directory = Path(directory)
    rc, head = _git(directory, "rev-parse", "HEAD")
    if rc != 0:
        raise RuntimeError(f"{directory} is not a git checkout: {head}")
    rc, dirty = _git(directory, "status", "--porcelain", "--untracked-files=no")
    if rc == 0 and dirty:
        raise RuntimeError(f"{directory} has uncommitted changes; commit or stash them first")
    report = Report(runtime=upstream.runtime, base=head.splitlines()[-1])
    for patch in upstream.patches:
        rc, out = _git(directory, "am", "--3way", "--keep-cr", str(patch))
        if rc == 0:
            report.outcomes.append(Outcome(patch.name, True))
            continue
        _git(directory, "am", "--abort")
        first = next((line for line in out.splitlines()
                      if line.startswith(("error:", "CONFLICT", "Patch failed"))), out[-200:])
        report.outcomes.append(Outcome(patch.name, False, first.strip()))
    return report
