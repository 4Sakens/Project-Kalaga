# Upstream and checkout review — 2026-11-24

Scope: every Git checkout in the environment, including the three named
repositories. "Reviewed" means the refs were fetched, the recent history and
branches read, and the open/merged/closed PRs and issues sampled through
`gh`. Nothing was merged wholesale.

## Checkouts

| Path | Remote | Head reviewed | Relevance |
|---|---|---|---|
| `D:\ZZ-box` | `4Sakens/Project-Kalaga` (GitHub now redirects to `4Sakens/Z-GTA`) | `7b80610` | **Main project.** Launcher, validation, build/launch glue. |
| `D:\VIctory` | fork `fxceless/victory-gta6`; upstream `Marvisak/VIctory` | fork `4e17478` (local main kept at `1684989` + opening patch) | GTA VI runtime that Project Kalaga builds and launches. |
| `D:\xcl` | upstream `xcl-dev/xcl`; `ivall/xcl` | `1d027e5` upstream (233 commits ahead of local `e50836b`) | General console runtime; not the current GTA VI path. |
| `D:\ZZ-box\fivestar` | `ThatRecompDev/five-star-recomp` | `f93d000` (109 commits ahead) | Separate C# GTA VI recompilation effort. |
| `D:\ZZ-box\xbox2windows` | `R0Y00/Xbox2Windows` | `18fe83d5` (425 commits ahead) | Static-recomp research and GPU tests. |
| `D:\mkw-web` | `4Sakens/mkw-web` | `7c06670` | Unrelated Mario Kart web project. |
| `D:\mkw-web\Wiicompiled` | `patchzyy/Wiicompiled` | `e11a76d` | Unrelated Wii web port. |
| `D:\mkw-web\emsdk` | `emscripten-core/emsdk` | `d7b4130` | Unrelated toolchain. |

## What the relevant upstreams contain

### Fork: `fxceless/victory-gta6`

`1684989` → `4e17478` is three commits:

- `4e17478` removes the game's name from the tree (wording only).
- `90228a7` restores parked lane-mask pairs and relative VGPR reads
  (shader correctness; PR #11).
- `3930989` fixes a mesh-pipeline test on unsupported GPUs (PR #14).

Open PRs reviewed: #142 async frame-capture encoding, #141 relay staging
wait, #140 texture-residency eviction, #139 `v_writelane_b32` outside EXEC,
#137 render-target/viewport exports, #135 AMD i64 compares, #134 AMD view-heap
clamp plus `v_cvt_f32_f64`/`v_permlane16/x16`, #132 report template, #131
borderless window, #130 SDL3 gamepad, #129 raw buffer dimensions, #128 Linux.
Merged: #1, #11, #14. Closed unmerged: #21, #58, #63, #65, #73 (sampled).
Issue #126 is the important one: a trial merge of upstream into the fork
conflicts in 36 files / 274 hunks, and only 3 of 28 upstream commits apply
cleanly. That rules out a safe wholesale merge.

### Upstream: `Marvisak/VIctory`

`origin/main` is `70564ae`, far beyond the fork's base `ffe310e`. The new work
rewrites copy tracking, the view heap, page tables, shader caching and
pipeline prebuild. Open PRs sampled include #1743 world-frame copy benchmark,
#1740/#1731 real occlusion queries, #1739 pipeline padding, #1738
interpolation, #1737 permlane flags, #1735 GPU timing, #1732 f32→half
rounding, #1730 shader-cache fill. Merged PRs sampled: #706, #696, #685, #681,
#680, #675, #671, #666. Closed unmerged: #1746, #1708, #1689, #1672, #1656.
These are not directly applicable to the fork's current GPU/translator split;
issue #126 documents the merge cost.

### `xcl-dev/xcl`

Local `e50836b`; upstream `1d027e5` (233 commits). Recent merged PRs include
#1806 (static samplers in `image_get_lod`), #1791 (ExecuteIndirect reads prior
arguments), #1748 (DXIL giant-shader IR blowup), #1747 (vram page tile
mappings), #1745 (per-lane direct DXIL), #1693 (heap memory windows). Open PRs
include #1851 title id, #1850 conditional `globallycoherent`, #1847 sparse
readback CPU writes, #1845 per-lane DPP bridge, #1844 iterative DXIL SSA joins,
#1841 f16 round-to-nearest-even, #1840 normalized buffer loads. Roadmap issue
#1833 still tracks a retail title past world load.

XCL is GPL-2.0 and was **not updated or built**: this machine has no MSVC or
Windows SDK, and the GTA VI path uses the VIctory fork, not XCL. Updating the
checkout without a build/test would change an untested platform layer.

### `five-star-recomp` and `Xbox2Windows`

FiveStar is GPL-3.0 and moved 109 commits (shader lanes, DXIL backend, texture
uploads, memory waits). Xbox2Windows is MIT and moved 425 commits (CPU/GPU
tests, packed fixtures, D3D12.X research). Both are adjacent research, not the
runtime Project Kalaga launches; copying either would duplicate a different
implementation. No changes were taken.

### Unrelated checkouts

`mkw-web`, `Wiicompiled` and `emsdk` are Mario Kart/web/emscripten work with
no GTA VI or Project Kalaga integration point. They were inspected and left alone.

## Integration attempt and rollback

I applied the three focused fork PRs on top of `4e17478`:

- #134 `8698a80` — AMD view-heap clamp and the two missing shader
  instructions.
- #139 `6a274bc`, `3c408b4` — `v_writelane_b32` outside EXEC, with its test.
- #141 `f909bf0` — wait before overwriting an in-flight texture staging buffer
  under `VICTORY_LATE_WAIT`/`RELAY`.

They applied without conflicts. `cargo test -p victory-shader -p victory-gpu`
reported **213 passed, 0 failed, 2 ignored**, and the diagnostics release
built. In game, the integrated build reached the world without a device
removal, but it ran at **0.2–0.5 fps**, uploaded several GB of textures, and
presented a black/unresponsive-looking world. That is not an improvement.

I preserved the trial as the local branch `integration-prs` at `e3089ea` in
`D:\VIctory` (do not confuse it with `main`). `main` was reset to the
known-good `1684989` with only the opening patch; it was rebuilt.

A later baseline run still removed the AMD device at world entry. The variable
was the image-quality settings added earlier (`vSync=1`, `fsrQuality=2`,
`anisotropicFiltering=16`). Restoring the pre-change settings
(`vSync=2`, `fsrQuality=0`, `anisotropicFiltering=0`) brought the prologue back
at **3.4–4.0 fps** with **zero device removals** and kept the 60 fps opening.
The exact interaction was not isolated to one setting; the stable set is what
is installed now.

## Decisions

| Change | Decision | Why |
|---|---|---|
| Fork `4e17478` wording/test commits | Not on `main` | Wording only; test already covered. The trial branch has them. |
| #134 AMD clamp + instructions | Not retained | Tests pass, but the world became a multi-GB texture upload at <1 fps. Needs splitting: instructions separately from the heap clamp. |
| #139 writelane | Not retained | Correct shader fix, but it rode with the same non-viable build; no in-game proof it is needed here. |
| #141 relay staging wait | Not retained | Relevant to `VICTORY_RELAY=2`, but no observed corruption to fix; avoid extra waits while diagnosing the black screen. |
| #140 texture eviction | Not used | Explicitly trades visible textures for memory; risky and untested here. |
| #131 borderless, #130 gamepad, #142 capture | Not used | UI/diagnostics/input scope, not the reported failure. |
| Upstream VIctory `70564ae` | Not merged | 36-file/274-hunk conflict (issue #126); would replace the fork's GPU core. |
| XCL `1d027e5` | Not updated | No MSVC/Windows SDK; not the active GTA VI runtime. |
| FiveStar / Xbox2Windows | Not used | Different implementations; no integration point. |

## Licences and attribution

- VIctory and the fork: **GPL-3.0**.
- XCL: **GPL-2.0**.
- FiveStar: **GPL-3.0**.
- Xbox2Windows: **MIT**.

No source from these repositories was copied into Project Kalaga in this review.
The retained fork change is the opening-pacing patch, already attributed in
`patches/0001-opening-60fps-window.patch` and `docs/opening.md`. The trial
commits keep their original authors and are GPL-3.0. Project Kalaga has no
top-level licence file; that policy decision is left to the owner rather than
silently relicensing the repo.

## Verification

- `cargo test -p victory-shader -p victory-gpu`: 213 passed, 0 failed, 2
  ignored.
- Diagnostics release build: exit 0.
- Integrated run: world reached, no device removal, but 0.2–0.5 fps and a
  black-looking world; rejected.
- Rolled-back run with stable settings: front end 60 fps, prologue visible at
  3.4–4.0 fps, 0 device removals, `Get-Process victory` responding.
- Native 1920×1080 stable-settings run: “PROLOGUE” card then the lit prison
yard, 3.9 fps, 0 device removals.
- Not run: XCL build/tests, FiveStar .NET tests, Xbox2Windows C++ tests, and
  any game test of #134's shader instructions without the heap clamp.

## Follow-ups

1. Split #134: take `v_cvt_f32_f64` and `v_permlane16/x16` without the
   heap-clamp change, and measure texture upload/frame time separately.
2. Re-test #141 only with `VICTORY_RELAY=2` and overlapping subtitles.
3. Do not merge upstream VIctory into the fork in one pass; use issue #126's
   topic split (translator gate first, then page table, heap views, copy-back).
4. Keep the stable settings file backed up at `logs/settings-before-60.xml`
   (vSync 2, FSR 0, AF 0). The rejected image-quality state is at
   `logs/settings-before-rollback.xml`.
