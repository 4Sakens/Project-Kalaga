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
    # Which VIctory checkout the switches belong to ("rdna", "belobug" or "fork").
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
# 32 GiB of RAM: under memory pressure (Windows' numbers, Belobug's
# RamBand Watch/High), let idle copies of title windows go down to this many
# bytes. Upstream saw them grow 2.8 -> 4.3 GB in eight minutes. A dropped copy
# is made again on its next read: no picture change.
_THIRTY_TWO_GB = {
    "VICTORY_WINDOW_BUDGET_MB": "1536",
}
# Write down every pipeline the title makes, so `kalaga prepare` (victory
# warm) can build them all before the next run: no first-time stutter.
_PIPELINE_BOOK = {
    "VICTORY_PIPELINE_BOOK": "1",
}
# Pools sized for 6 cores / 12 threads. Upstream's fixed counts (8 list
# threads, 6 compare threads) were set on a 24-thread i9; on the 5600X they
# compete with the submit thread, which is the wall. Untested here: an
# experiment, not a default. Left alone on purpose: VICTORY_VIEW_THREADS (it
# also sizes the descriptor-record pool the submit thread waits on) and
# VICTORY_PIPELINE_WORKERS (fewer workers = draws left out longer while
# their pipelines are made: missing objects).
_SIX_CORES = {
    "VICTORY_THIN_THREADS": "4",
    "VICTORY_UNDER_THREADS": "3",
}
# Series X profile at native 1080p. VICTORY_OUTPUT alone makes the title
# draw at its 2/3 render scale (1280x720) and upscale; VICTORY_RENDER_SCALE
# 1.0 (upstream run res-4) makes it draw all 1920x1080. That is ~2.1 Mpx a
# frame, less than the Series X default (2560x1440 for 4K), and sharper than
# Series S (also 720p internal at 1080p output).
_SERIES_X_1080P = {
    "VICTORY_OUTPUT": "1920x1080",
    "VICTORY_RENDER_SCALE": "1.0",
}

# 8 GB card: a hard cap on title textures. On 8 GB cards Series X runs out
# of graphics memory in the first cutscene (i95's RTX 4060 runs, for Vice-Tay
# and VIctory-7900XTX, both this code family); every 8 GB setting on the
# board caps textures at 4-5 GB. The cap replaces the 90 % room test and does
# not reserve anything: below it, textures load as before.
# VICTORY_CARD_BUFFERS_MB is left alone on purpose: on budgets <= 12 GiB this
# family already defaults it to 512 MiB, and the board's 1024 would double it.
_EIGHT_GB_SERIES_S = {"VICTORY_TEXTURE_BUDGET_MB": "5120"}
# Series X's bigger render targets need more of the card.
_EIGHT_GB_SERIES_X = {"VICTORY_TEXTURE_BUDGET_MB": "4608"}

_BELOBUG_COMMON = {**_BELOBUG_BASE, **_THIRTY_TWO_GB, **_PIPELINE_BOOK}

# XaviFortes/VIctory-RDNA: VIctory-7900XTX tuned for RDNA3 (the RX 7600's
# architecture). scripts/rdna-preset.json "base" and "fast", its default.
_RDNA_BASE = {
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
    "VICTORY_CARD_BUFFERS_MIN_MB": "1",
}
_RDNA_FAST = {
    "VICTORY_THIN": "1",
    "VICTORY_JOIN_PARTS": "8",
    "VICTORY_UPLOAD_AHEAD": "1",
    "VICTORY_PORT_CONSTANTS": "1",
    "VICTORY_PORT_DESCRIPTORS": "1",
    "VICTORY_PORT_CBV": "1",
    "VICTORY_PORT_GUARD": "1",
    "VICTORY_PORT_JOURNAL": "1",
    "VICTORY_PORT_BUFFERS": "1",
    "VICTORY_INPLACE": "2",
    "VICTORY_ASK_SPREAD": "1",
    "VICTORY_RESIDENCY": "1",
    "VICTORY_SYNC_FINE": "1",
}
_RDNA_SAFE = {
    "VICTORY_UNDER_WIDE": "0",
    "VICTORY_LAND_ECHO": "0",
}
_RDNA_COMMON = {**_RDNA_BASE, **_THIRTY_TWO_GB, **_PIPELINE_BOOK}

# The fxceless/victory-fork switches measured in docs/pc-test.md (run 3),
# exactly: this preset is the known-good fallback (Series X, 0 removals).
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
}

PRESETS: dict[str, Preset] = {
    p.name: p
    for p in (
        Preset(
            name="rx7600-rdna",
            summary="VIctory-RDNA (RDNA3-tuned), Series S, its base+fast set, 5 GB texture cap (recommended start)",
            checkout="rdna",
            console="series-s",
            env={**_RDNA_COMMON, **_RDNA_FAST, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-rdna-quality",
            summary="VIctory-RDNA, Series X drawn at native 1080p: sharpest picture, most VRAM",
            checkout="rdna",
            console="series-x",
            env={**_RDNA_COMMON, **_RDNA_FAST, **_SERIES_X_1080P, **_EIGHT_GB_SERIES_X},
        ),
        Preset(
            name="rx7600-rdna-safe",
            summary="VIctory-RDNA, Series S, its base+safe set: try first when something breaks",
            checkout="rdna",
            console="series-s",
            env={**_RDNA_COMMON, **_RDNA_SAFE, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-belobug",
            summary="Belobug runtime, Series S, the settings of Belobug's play.ps1, 5 GB texture cap",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_COMMON, **_BELOBUG_FAST_WAYS, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-belobug-quality",
            summary="Series X profile drawn at native 1080p: sharpest picture; needs the most VRAM",
            checkout="belobug",
            console="series-x",
            env={**_BELOBUG_COMMON, **_BELOBUG_FAST_WAYS, **_SERIES_X_1080P, **_EIGHT_GB_SERIES_X},
        ),
        Preset(
            name="rx7600-belobug-6core",
            summary="rx7600-belobug with worker pools sized for 6 cores / 12 threads (experiment)",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_COMMON, **_BELOBUG_FAST_WAYS, **_SIX_CORES, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-belobug-fast",
            summary="rx7600-belobug plus the five renderer patches (VICTORY_PORT_*)",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_COMMON, **_BELOBUG_FAST_WAYS, **_BELOBUG_PORT, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-belobug-safe",
            summary="Belobug runtime, Series S, play.ps1 -Safe: try first when something breaks",
            checkout="belobug",
            console="series-s",
            env={**_BELOBUG_COMMON, **_BELOBUG_SAFE_WAYS, **_EIGHT_GB_SERIES_S},
        ),
        Preset(
            name="rx7600-fork",
            summary="current fxceless/victory-fork checkout, Series X, docs/pc-test.md run 3 + AMD skips",
            checkout="fork",
            console="series-x",
            env=dict(_FORK_PC_TEST),
            amd_skips=True,
        ),
    )
}


# Inherited variables a preset keeps: where files are, not how to run.
PATH_VARIABLES = frozenset({
    "VICTORY_CONFIG",
    "VICTORY_GAME_DIR",
    "VICTORY_CACHE_DIR",
    "VICTORY_DATA_DIR",
    "VICTORY_FIDELITYFX_DIR",
    "VICTORY_DXC_DIR",
})


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
