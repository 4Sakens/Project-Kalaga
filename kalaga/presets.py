"""Named launch presets: a console profile plus VICTORY_* switches for one PC.

A preset is chosen with ``[launch] preset = '<name>'`` in kalaga.toml or
``kalaga launch --preset <name>``. Its switches are applied before
``[launch.extra_env]``, so anything set there still wins, and its console is
used only when ``[launch] console`` is not set.

The presets here target this project's machine (Ryzen 5 5600X, 32 GiB, Radeon
RX 7600 8 GB). Why these runtimes and values: docs/hardware-pick.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import REPO_ROOT


@dataclass(frozen=True)
class Preset:
    name: str
    summary: str
    # Which VIctory checkout the switches belong to ("belobug" or "fork").
    # Switches one fork reads are ignored by another, so a mismatch is
    # harmless but does nothing.
    checkout: str
    console: str
    env: dict[str, str] = field(default_factory=dict)
    # Append docs/amd-skips.txt as VICTORY_SKIP_PIPELINES.
    amd_skips: bool = False


# What Belobug's scripts\play.ps1 always sets (the settings its measurements use).
_BELOBUG_BASE = {
    "VICTORY_TEXTURE_NO_WAIT": "1",
    "VICTORY_RELAY": "2",
    "VICTORY_WIDE_BACK": "1",
    "VICTORY_CARD_REHASH_RUNS": "1",
    "VICTORY_JOIN_COPIES": "1",
    "VICTORY_INDIRECT_WINDOW": "1",
    "VICTORY_RELAY_COPY": "1",
    "VICTORY_CARD_STEPS": "2",
    "VICTORY_INDIRECT_BATCH": "2",
    "VICTORY_MAP_THREADS": "1",
    "VICTORY_TITLE_PRIORITIES": "0",
    "VICTORY_CARD_AWAKE": "1",
    "VICTORY_SHOW_AFTER": "1",
    "VICTORY_AMBIENT": "0.8",
}
# play.ps1 without -Safe.
_BELOBUG_FAST_WAYS = {
    "VICTORY_THIN": "1",
    "VICTORY_JOIN_PARTS": "8",
    "VICTORY_UPLOAD_AHEAD": "1",
}
# play.ps1 -Safe.
_BELOBUG_SAFE_WAYS = {
    "VICTORY_UNDER_WIDE": "0",
    "VICTORY_LAND_ECHO": "0",
}
# The renderer patches (off by default upstream while they are tested). They
# cut CPU time on the submit thread, which is what limits a 6-core 5600X.
_BELOBUG_PORT = {
    "VICTORY_PORT_CONSTANTS": "1",
    "VICTORY_PORT_DESCRIPTORS": "1",
    "VICTORY_PORT_CBV": "1",
    "VICTORY_PORT_GUARD": "1",
    "VICTORY_PORT_JOURNAL": "1",
}
# An 8 GB card: leave more of the budget to title buffers than the 90 % default
# tuned on a 24 GB 7900 XTX.
_EIGHT_GB = {
    "VICTORY_TEXTURE_ROOM_PERCENT": "85",
}

# The fxceless/victory-fork switches measured in docs/pc-test.md (run 3).
_FORK_PC_TEST = {
    "VICTORY_SHADER_LOOP_LIMIT": "256",
    "VICTORY_INPLACE_MB": "4096",
    "VICTORY_RELAY": "2",
    "VICTORY_INPLACE": "2",
    "VICTORY_WIDE_BACK": "1",
    "VICTORY_CARD_BUFFERS_MIN_MB": "1",
    "VICTORY_CARD_BUFFERS_MB": "1024",
    "VICTORY_JOIN_COPIES": "1",
    "VICTORY_CARD_REHASH_RUNS": "1",
    "VICTORY_TEXTURE_NO_WAIT": "1",
}

PRESETS: dict[str, Preset] = {
    p.name: p
    for p in (
        Preset(
            name="rx7600-belobug",
            summary="Belobug runtime, Series S, play.ps1 settings, 8 GB texture room (recommended start)",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_BASE, **_BELOBUG_FAST_WAYS, **_EIGHT_GB},
        ),
        Preset(
            name="rx7600-belobug-fast",
            summary="rx7600-belobug plus the five renderer patches (VICTORY_PORT_*)",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_BASE, **_BELOBUG_FAST_WAYS, **_EIGHT_GB, **_BELOBUG_PORT},
        ),
        Preset(
            name="rx7600-belobug-safe",
            summary="Belobug runtime, Series S, play.ps1 -Safe: try first when something breaks",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_BASE, **_BELOBUG_SAFE_WAYS, **_EIGHT_GB},
        ),
        Preset(
            name="rx7600-fork",
            summary="current fxceless/victory-fork checkout, Series S, docs/pc-test.md switches + AMD skips",
            checkout="fork",
            console="series-s",
            env=dict(_FORK_PC_TEST),
            amd_skips=True,
        ),
    )
}


def get(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise RuntimeError(f"unknown preset {name!r}; known presets: {known}") from None


def amd_skip_list() -> str:
    path = REPO_ROOT / "docs" / "amd-skips.txt"
    if not path.is_file():
        return ""
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return ",".join(line for line in lines if line and not line.startswith("#"))


def environment(preset: Preset) -> dict[str, str]:
    """The VICTORY_* variables the preset sets."""

    env = dict(preset.env)
    if preset.amd_skips:
        skips = amd_skip_list()
        if skips:
            env["VICTORY_SKIP_PIPELINES"] = skips
    return env
