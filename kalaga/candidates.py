"""Which new upstream PRs would go onto our patched runtime: ``kalaga candidates``.

Lists the open pull requests of the VIctory repos we pick from that changed
in the last few days, leaves out the ones already in our series (matched by
commit subject), and tries each of the rest on top of the patched checkout
with ``git am --3way``, one at a time, backing each out again. The result is
a table of PRs that apply cleanly (worth a look, then a build in CI) and
those that conflict, written as markdown for the daily job summary.

Run by the ``candidates`` job of .github/workflows/runtimes.yml, which the
daily watch reads. Applying is not building: a PR that applies still has to
pass the patched build and tests before it joins a series.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import upstream

# The repos picked from (patches/UPSTREAM-PRS.md). Order is the table's.
REPOS = (
    "XaviFortes/VIctory-RDNA",
    "Belobug/VIctory-Belobug-AMD",
    "avatarmanz/VIctory-7900XTX",
    "TaynanGT/Vice-Tay",
    "fxceless/victory-fork",
    "Marvisak/VIctory",
    "DexNom/VIctory",
)
# More commits than this: a rework, not a pick (and slow to fetch).
MAX_COMMITS = 30


@dataclass
class PullRequest:
    repo: str
    number: int
    title: str
    url: str
    updated: str
    commits: int
    author: str = ""
    clone_url: str = ""  # default: the repo on GitHub


@dataclass
class Tried:
    pr: PullRequest
    result: str  # "applies", "conflicts", "already in", "skipped"
    detail: str = ""
    files: list[str] = field(default_factory=list)


def _get(url: str, token: str | None) -> object:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "kalaga-candidates",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def open_prs(repo: str, since: datetime, token: str | None = None) -> list[PullRequest]:
    """Open PRs of ``repo`` updated since ``since``, newest first."""

    url = f"https://api.github.com/repos/{repo}/pulls?state=open&sort=updated&direction=desc&per_page=50"
    data = _get(url, token)
    out = []
    for item in data if isinstance(data, list) else []:
        updated = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
        if updated < since:
            break
        number = int(item["number"])
        try:
            detail = _get(f"https://api.github.com/repos/{repo}/pulls/{number}", token)
            commits = int(detail.get("commits", 0)) if isinstance(detail, dict) else 0
        except (urllib.error.URLError, ValueError, TimeoutError):
            commits = 0
        out.append(PullRequest(repo, number, item["title"], item["html_url"], item["updated_at"],
                               commits, (item.get("user") or {}).get("login", "")))
    return out


def series_subjects(series: upstream.Upstream) -> set[str]:
    """The commit subjects in a series, normalised, to spot PRs already taken."""

    subjects = set()
    for patch in series.patches:
        text = patch.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^Subject: (?:\[PATCH[^\]]*\] )?(.+(?:\n .+)*)", text, re.M)
        if m:
            subjects.add(normalise(m.group(1).replace("\n ", " ")))
    return subjects


def normalise(subject: str) -> str:
    subject = re.sub(r"\s*\(#\d+\)\s*$", "", subject.strip())
    return re.sub(r"\s+", " ", subject).lower()


def try_pr(checkout: Path, pr: PullRequest, taken: set[str]) -> Tried:
    """Fetch the PR's commits and try them on the checkout's HEAD; back out."""

    if pr.commits <= 0 or pr.commits > MAX_COMMITS:
        return Tried(pr, "skipped", f"{pr.commits} commits")
    url = pr.clone_url or f"https://github.com/{pr.repo}.git"
    rc, out = upstream._git(checkout, "fetch", "-q", f"--depth={pr.commits + 1}", url,
                            f"pull/{pr.number}/head", timeout=600)
    if rc != 0:
        return Tried(pr, "skipped", f"fetch failed: {out[-160:]}")
    rc, subjects = upstream._git(checkout, "log", "--format=%s", f"-{pr.commits}", "FETCH_HEAD")
    wanted = [normalise(s) for s in subjects.splitlines() if not s.startswith("Merge ")]
    if wanted and all(s in taken for s in wanted):
        return Tried(pr, "already in")
    rc, files = upstream._git(checkout, "diff", "--name-only", f"FETCH_HEAD~{pr.commits}", "FETCH_HEAD")
    changed = [f for f in files.splitlines() if f] if rc == 0 else []
    rc, head = upstream._git(checkout, "rev-parse", "HEAD")
    patch_dir = checkout / ".git" / "kalaga-candidate"
    patch_dir.mkdir(exist_ok=True)
    for old in patch_dir.glob("*.patch"):
        old.unlink()
    rc, out = upstream._git(checkout, "format-patch", "-q", "--no-merges", "-o", str(patch_dir),
                            f"FETCH_HEAD~{pr.commits}..FETCH_HEAD")
    patches = sorted(patch_dir.glob("*.patch"))
    if rc != 0 or not patches:
        return Tried(pr, "skipped", "nothing to apply (merges only?)", changed)
    rc, out = upstream._git(checkout, "am", "--3way", "--keep-cr", *map(str, patches))
    if rc == 0:
        result, detail = "applies", f"{len(patches)} commit(s)"
    else:
        upstream._git(checkout, "am", "--abort")
        first = next((ln for ln in out.splitlines() if ln.startswith(("CONFLICT", "error:", "Patch failed"))),
                     out[-160:])
        result, detail = "conflicts", first.strip()
    upstream._git(checkout, "reset", "-q", "--hard", head.splitlines()[-1])
    return Tried(pr, result, detail, changed)


def markdown(runtime: str, tried: list[Tried], days: int) -> str:
    lines = [f"### New upstream PRs on the patched {runtime} (last {days} days)", ""]
    if not tried:
        return "\n".join(lines + ["No open PR changed in that time.", ""])
    order = {"applies": 0, "conflicts": 1, "skipped": 2, "already in": 3}
    lines += ["| PR | Result | Files | Detail |", "|---|---|---|---|"]
    for t in sorted(tried, key=lambda t: (order.get(t.result, 9), t.pr.repo, -t.pr.number)):
        files = ", ".join(Path(f).name for f in t.files[:4]) + (" …" if len(t.files) > 4 else "")
        title = t.pr.title.replace("|", "/")
        lines.append(f"| [{t.pr.repo}#{t.pr.number}]({t.pr.url}) {title} | **{t.result}** | {files} | "
                     f"{t.detail.replace('|', '/')} |")
    good = sum(t.result == "applies" for t in tried)
    lines += ["", f"{good} apply cleanly on top of our {runtime} series (still to build and test)."]
    return "\n".join(lines) + "\n"


def run(runtime: str, checkout: Path, days: int = 3, repos: tuple[str, ...] = REPOS,
        token: str | None = None) -> tuple[str, list[Tried]]:
    token = token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    series = upstream.load(runtime)
    taken = series_subjects(series)
    tried: list[Tried] = []
    for repo in repos:
        try:
            prs = open_prs(repo, since, token)
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            tried.append(Tried(PullRequest(repo, 0, "(could not list PRs)", f"https://github.com/{repo}",
                                           "", 0), "skipped", str(exc)[:120]))
            continue
        for pr in prs:
            tried.append(try_pr(Path(checkout), pr, taken))
    return markdown(runtime, tried, days), tried
