# Status — measured 2026-11-24

Everything below was executed on the development machine, not copied from a
plan. Where a statement comes from an upstream project instead, it says so.

## Machine

| | |
|---|---|
| OS | Windows 11 Pro 10.0.26300 |
| CPU | AMD Ryzen 5 5600X (6C/12T) |
| GPU | AMD Radeon RX 7600, driver 32.0.32029.2010 |
| RAM | 31.9 GiB |
| Disk | D: 621.5 GiB free |
| Visual Studio | **not installed** |
| Windows SDK / DXC | **not installed** (standalone DXC 1.9.2609 used instead) |

## Game files

```text
game dir   : D:\GTA 6\GTA6.Xbox.v1.0.2.1
title      : Grand Theft Auto VI  id=7952987A  version=1.0.2.1
publisher  : Rockstar Games
executable : game_scarlett_master.exe
files      : 109  (208.6 GiB)
archives   : 22 RPF9, 0 unrecognised
manifest   : 108/108 files, 0 missing, 0 wrong size, 1 extra
  [warn] not in manifest: game_scarlett_master.exe
result     : OK
```

The extra file is the 120 MB loader executable the release adds; it is the one
`MicrosoftGame.Config` names, so its absence would have blocked the run. All 22
archives begin with the RPF9 magic (`39 46 50 52`), the largest being
`levels.rpf` (71 GB) and `audio.rpf` (27 GB). Package `data/ttdb` (57 GB) and
`pack/` (30 GB) are present.

Validation is name/size/header based; the 208 GiB was not re-hashed against
torrent piece hashes.

## Toolchain built for this machine

| Component | Version | Note |
|---|---|---|
| Rust (MSVC host) | 1.98.1 | installed with `--no-modify-path`; cargo home detected explicitly |
| Rust (GNU host) | 1.98.1-x86_64-pc-windows-gnu | used for the build, no MSVC needed |
| mingw-w64 | GCC 16.2.0 (winlibs UCRT) | `D:\projectz-deps\mingw64` |
| DirectX Shader Compiler | 1.9.2609.5 (x64) | `D:\projectz-deps\dxc` |

The first attempt with the MSVC host failed exactly as expected: without
`link.exe`, Rust's **host build scripts** fell through to the coreutils `link`
and failed with `link: extra operand`. A `gnullvm` target did not help for the
same reason (host scripts still link with the MSVC linker). The GNU host plus
mingw-w64 is the working no-Visual-Studio path.

## Build

```text
$ cargo +1.98.1-x86_64-pc-windows-gnu build --release -p victory --target x86_64-pc-windows-gnu
    Finished `release` profile [optimized + debuginfo] target(s) in 1m 00s
```

Output: `D:\VIctory\target\x86_64-pc-windows-gnu\release\victory.exe` — 45 MB,
valid PE32+ x64 (`machine 0x8664`). A diagnostics build
(`--profile diag --features diagnostics`) also succeeds through
`python -m kalaga build --diag` in 1m 03s.

## Run — what actually happened

Command composed by `kalaga launch`:

```text
D:\VIctory\target\x86_64-pc-windows-gnu\release\victory.exe run "D:\GTA 6\GTA6.Xbox.v1.0.2.1\game_scarlett_master.exe" --execute --console series-x
```

Boot sequence from the log:

```text
build          unknown (b99f876b74d4a77f03af5f878223b27bd647b5c35a79d5decd9f716504239e93)
image mapped base=0x7ff8a7170000 preferred=0x140000000
title          7952987A, storage ...\victory\data\7952987A/storage (2048 MB)
virtual drive  drive=G root=D:\GTA 6\GTA6.Xbox.v1.0.2.1
console        Xbox Series X
title dll      xboxbvhbuilder.dll, amd_fidelityfx_loader_xbox.dll
```

Steady state, sampled over 150 s:

```text
30.0 fps, 33.3 ms/frame ... 21 draws/frame, dropped 0 without a host pipeline, 0 indirect
frame presented frame=4096 draws=43008 drawn=43008 dispatches=2048 dispatched=2048
```

Audio and input:

```text
apu: audio decoder connected streams=256 memory=1064960 options=1
dsp: audio DSP connected base_length=393216 ir_seconds=30 max_streams=128
gameinput: input device device=4 connected=true, device=5 connected=true
dstorage: file opened path="G:\\audio.rpf"
```

Only four warnings in the whole session: `rpcrt4.dll` refused by the host
policy, two unimplemented D3D12 device methods (`slot=0x1c8`, `slot=0x218`),
and one unordered-access view the host disallows.

### Visual evidence

A diagnostics run with `VICTORY_CAPTURE` saved frames 1…1024. Frame 1024 shows
the title's own first-boot screen — dark background, bottom-right
**"ACCOUNT PICKER  (Y)   SCREEN NARRATION (OFF)  (X)   PLAYER  (A)"** with Xbox
button glyphs. That is the original game's UI, drawn by VIctory on the PC GPU.

Captures stay in `logs/capture*/` and are git-ignored: they are game content.

### Driving the boot screens

The diagnostics build's `VICTORY_KEYS=<seconds>:<key>,...` holds each key for
0.2 s, focus or not. Two WARP runs used it: A presses first (every 10–15 s), then
Down+Enter cycles from 190 s. The Terms screen had moved focus off Confirm, so
one focused-window injection (Up, Up, Enter, Down, Down, Enter, 220 ms holds)
checked Privacy and confirmed; that is the same host keyboard path, not a
different input mechanism.

What the title actually displayed, in order (WARP unless noted, seconds from
the first-boot run's input start):

| Screen | Seen at | What is on it |
|---|---|---|
| Account picker | 103 s | `ACCOUNT PICKER (Y)  PLAYER (A)` (the narration option appeared only before settings were saved) |
| Rockstar logo | 114–126 s | neon colour logo, then monochrome |
| Legal notices | 185 s | Copyright, then Photosensitivity Health Warning; `NEXT`, `BACK (B)` |
| UI text size | 198 s | Small (Default) … `CONTINUE (A)` |
| Subtitles | 212 s | Off (Default) … `CONTINUE (A)` |
| Brightness | 218 s | Brightness Level 15, `ADJUST`, `CONTINUE (A)` |
| Finish setup | 252 s | default controls note (LT to run and sprint), `SETTINGS`, `CONTINUE (A)` |
| Legal Terms & Policies | 277 s | Privacy Policy / Terms of Service checkboxes, `CONFIRM` |
| Terms accepted | 304 s | Terms checked, `Confirm — Confirm setup and start the game` |
| Loading | after confirm | dark screen, small spinner at bottom right |
| Loading art | WARP + hardware | original painted art (oranges, LEONIDA sign), then the Rockstar logo |
| Start-screen art | WARP (dimmed) + hardware (full colour) | Jason with the LEONIDA tank top; Lucia with the motel backdrop |

The brightness choice was written by the title to
`…\victory\data\7952987A\storage\settings\settings.xml` — `gamma=15`,
`desiredFPS=30`, `fsrQuality=2` — and a player save folder was created, so
these are the game's own settings/profile code paths, not a UI mock.

### Fork runtime: opening cutscene and prologue

`fxceless/victory-gta6` is a GTA VI-specific fork of VIctory. Its `main` at
`1684989` is seven commits ahead of the `ffe310e` this checkout had, so
`D:\VIctory` was fast-forwarded to it and rebuilt as a diag binary with the
same GNU toolchain.

The fork's AMD report (issue #3, RX 9060 XT / RX 9070 XT) supplies a
43-program skip list: 41 `CS_RaytracingResolve` variants that crash AMD's
shader compiler, plus `eeed82b877b44b5f` and `fc5e66f8f873d3bb` (meshlet
culling). The last is the program this machine saw fail translation earlier.
The exact list is in [`amd-skips.txt`](amd-skips.txt); pass it as
`VICTORY_SKIP_PIPELINES=$(paste -sd, docs/amd-skips.txt)`.
With that list, `VICTORY_SHADER_LOOP_LIMIT=256` and DRED on, a 15-minute
hardware run measured:

| Stage | Measured |
|---|---|
| Front end / start screen | 29 fps, 11 draws/frame while 735 pipelines were made |
| Opening cutscene | 0.6–1.6 fps, 588–2,783 draws/frame, 700–759 dropped |
| Prologue gameplay | 2.2 fps, 460 ms/frame (210 ms GPU, 156 ms preparing, 85 ms copy-back) |
| Device removals | **0** in 15 minutes |
| Saves | autosave written during the run |

A later performance run at 640×360 reached 4.0–4.2 fps, and a native
quality-profile run (AF 16, near-material LOD 1.0, `lodScale=0.8`,
`VICTORY_INPLACE_MB=4096`) held 4.0–4.1 fps at 1920×1080; see the frame-rate
investigation below.

The cutscene plays in order with its illustrated credit cards, and the
prologue renders a lit prison yard: characters, watchtower, sky, and the
game's own HUD prompts (“Move around” / “Move the camera”). Shadowed surfaces
are black, as the fork documents: its ray-traced bounce light and shadows are
not implemented yet. The movement prompt was observed but movement was not
actuated.

### Frame-rate investigation (2026-11-24)

The target was 15–30 fps in the prologue. The best stable result is **4.0–4.2
fps (240–249 ms/frame)** at 640×360 with the relay and in-place stage 2, up
from 2.2 fps. Menus remain at 29–30 fps. The full matrix, per-command GPU
timings, exact environment and the rejected switches are in
[performance.md](performance.md).

The measured frame is GPU 132–142 ms, preparation 96–105 ms and readback
164–177 ms for 71–74 MB. The GPU is dominated by 5,090 single-record indirect
mesh draws at ~18 µs each, not fill rate. `VICTORY_INDIRECT_WINDOW=1` targets
those records but folded in a 59,153-group record, asked for 135,526
groups/frame and removed the device (`0x887A0005`); it is not usable at
`1684989`. In-place stage 2 cannot be combined with the relay, and only 30 MB
of buffers were placeable, so the readback remains.

15–30 fps is therefore **not** a supported claim for the world on this
machine. The two changes that could get there are a safe indirect window and
in-place view memory / direct shader writes.

### Opening pacing (2026-11-24)

The title requests 33.333 ms frames for its front end. A reversible fork patch
(`patches/0001-opening-60fps-window.patch`) overrides that to 16.667 ms for the
first 60 seconds, then restores the title's interval. With the override passed
through `[launch.extra_env]`, the loading phase runs at **60–62 fps / 16.1–16.7
ms**, and after the cutoff the key art returns to **30 fps / 33.3 ms** with
**zero** “wait not met at a present” warnings. An unrestricted 60 fps override
produced those warnings and is not used. Details and caveats are in
[opening.md](opening.md).

### Upstream review (2026-11-24)

Every local Git checkout and the three named remotes were fetched and reviewed.
Fork commits `4e17478`/`90228a7`/`3930989` and the focused open PRs #134 (AMD
view-heap clamp + two shader instructions), #139 (writelane outside EXEC) and
#141 (relay staging wait) were applied on a trial branch. The tests passed (213
passed, 2 ignored) and the build succeeded, but the world became a 0.2–0.5 fps,
multi-GB texture upload with a black-looking picture, so the experiment was
rolled back. Upstream VIctory `70564ae` was not merged: a trial merge conflicts
in 36 files / 274 hunks (fork issue #126). XCL is 233 commits ahead but has no
MSVC/Windows-SDK build here; FiveStar and Xbox2Windows are separate
implementations; the `mkw-web` checkouts are unrelated. No upstream source was
copied. Full table and licences: [upstream-review.md](upstream-review.md).

A separate baseline run then removed the AMD device at world entry when FSR
quality 2 and `vSync=1` were enabled together. Restoring `vSync=2` and
`fsrQuality=0` produced a visible prologue at **3.4–4.0 fps with 0 removals**.
A later profile with `anisotropicFiltering=16`, near-material LOD 1.0,
`lodScale=0.8` and `VICTORY_INPLACE_MB=4096` held **4.0–4.1 fps at native
1920×1080 with 0 removals**, and is sharper. World entry is settings-sensitive;
see [opening.md](opening.md).

### Black uniforms and shadowed surfaces (2026-11-24)

The apparent missing colours are the fork's missing ray-traced indirect light,
not a mesh or texture-upload bug. The cell's uniform print is present while the
fabric and faces are black; disabling deep-skips globally did not restore the
light. A per-program deep-skips switch (fork issue #62, VIcky `e27b969`) was
ported and its five tests passed, but a native run removed the device, so it is
not retained. Gamma 25 recovers faces and uniform colours but clips the sunlit
yard; 15–21 leave the cell black. The stable default gamma 15 is restored. The
real fix is the fork's BVH/trace lighting path or a deliberate ambient
post-process. Details and captures: [graphics.md](graphics.md).

### BVH builder/trace test (2026-11-24)

On an isolated worktree at `1684989` (stable checkout untouched), enabling
`VICTORY_BVH_BUILDER=1` let the ray-tracing structure builder run — all 53 of
its pipelines had host pipelines — but the title then crashed with an access
violation (`0xC0000005`) before a lit frame. Adding
`VICTORY_BVH_QUARANTINE=1` avoided the crash and any device removal, but the
scene stayed effectively unlit with a blue cast and ran at ~5.7 s/frame. The
builder path does **not** restore usable indirect light and is not enabled in
the stable configuration. Details: [bvh-test.md](bvh-test.md).

### Light-path / shadow-mask test (2026-11-24)

In the isolated `D:\VIctory-shadow` worktree, the five remaining programs
previously grouped as shadow-mask traces now translate. Their `.cdxil` names
are `CS_RaytracingResolve_a56bfb9c`, `CS_IrradianceCache_Shade`,
`CS_IrradianceCache_ShadeSecondary`, a transpose utility, and water optical
depth — not five shadow traces.

Upstream `gta6/main` `90228a7` (fetched as `2119b0e`) restores the parked
lane-mask pairs exactly and translates the resolve and both irradiance-cache
shaders. With that cherry-pick, `VICTORY_WAVE_MASK_ELSEWHERE=0` and only
`VICTORY_WAVE_HALF_SUM_ANY=1` for the tiny transpose program, all five
translate: prologue hair/yard/prisoners are lit, gameplay is 3.6 fps, and the
run has **0 device removals**. Exact masks alone leave the face black because
the transpose program still fails; the mask approximation is no longer needed.
A cell capture with this exact-mask combination (run D, 0 removals, 3.2–5.2
fps) shows the cell and cell block still essentially unlit: lamp panels glow
but light nothing around them, and faces and clothing are black. The earlier
“partial cell light” claim had no supporting image and is withdrawn. Indoor
light is **not** restored. The builder was off. Details:
[shadow-mask-test.md](shadow-mask-test.md) and
[light-passes.md](light-passes.md).

### Upstream sources checked

* [`fxceless/victory-gta6`](https://github.com/fxceless/victory-gta6) at
  `gta6/main` `2119b0e` — the stable checkout is still `1684989`. Its five new
  commits include the exact parked-lane-mask fix (`90228a7`), a temporary
  removal (`9e49b8a`) and its restoration (`2119b0e`); the fork README still
  reports 30 fps menus, a lit opening cutscene, a 2–4 fps prologue and black
  shadows. Details and the local test: [light-passes.md](light-passes.md).
* [`xcl-dev/xcl`](https://github.com/xcl-dev/xcl) at `origin/main` `20cf130` —
  fetched but **not built**: it requires MSVC and the Windows SDK, neither
  installed here, and the local checkout is 248 commits behind. Its roadmap
  issue #1833 still tracks a retail title past world load; the fork credits XCL
  as a reference. Recent per-lane mask, AMD MSAA and direct-DXIL changes are
  reference material, not part of the GTA VI path here.

## What is implemented, what is verified

| | Implemented | Verified |
|---|---|---|
| Dump discovery + identity | yes | yes, on the real 208 GiB dump |
| Archive/manifest validation | yes | yes |
| Hardware/toolchain doctor | yes | yes |
| Runtime planning with fixes | yes | yes |
| Runtime build (release + diag) | yes | yes, 3 successful builds (release, diag, fork diag) |
| DXC staging | yes | yes, DLLs copied next to the exe |
| Launch + logging + exit diagnosis | yes | yes, 22 runs (release + diag, WARP + hardware + fork) |
| Title boot / rendering / audio / input | upstream | yes, evidence above |
| Menus beyond first boot | fork | yes — account picker, legal notices, setup wizard, terms, loading art, start-screen art, opening cutscene |
| Opening pacing | fork + patch | yes — 60 fps for the first 60 s of loading, then the title's 30 fps; zero present warnings |
| Start-screen menu buttons | fork | not captured — the profile picker advanced into the cutscene |
| World / gameplay | fork, incomplete | yes — prologue renders with HUD at 4.0–4.1 fps native with the quality profile, 4.0–4.2 fps at 640×360; movement not actuated |
| Material/texture quality | fork | yes — AF 16, near-material LOD 1.0, native 1920×1080; 0 device removals |
| Ray-traced shadows / bounce light | fork | no — shadowed surfaces are black |

## Remaining barriers

1. **Black shadows** (fork): the game's ray-traced bounce light and shadows do
   not run yet, so anything the sun does not hit directly is black.
2. **World frame rate** (fork): 4.0–4.1 fps native with the sharper quality
   profile, 4.0–4.2 fps in the low-resolution performance configuration. The
   measured wall is 71–74 MB/frame of title-buffer readback plus ~95 ms of
   single-record indirect mesh draws; see [performance.md](performance.md).
3. **Input and gameplay depth**: the prologue HUD prompts were seen, but
   movement, the pause menu and save/load in gameplay were not actuated.
4. **World beyond the prologue** was not reached in this run.
5. **No Visual Studio** on this machine: fine for the GNU target, but XCL and
   some D3D12 debugging aids assume MSVC.

## Next steps

1. Verify movement and the pause menu in the prologue (WASD / pad), then
   capture a moved frame and the menu.
2. In the fork, fix `VICTORY_INDIRECT_WINDOW` so a window cannot include a
   record above a sane group budget (it currently device-removes), and make
   view memory placeable or writable directly, to remove the 71–74 MB/frame
   readback. Both are required before 15 fps is plausible; see
   [performance.md](performance.md).
3. Implement the fork's missing ray-traced bounce light and shadows (see
   `docs/fork-ray-tracing.md`) so shadowed areas stop rendering black.
4. Build XCL when MSVC and the Windows SDK are available, or add a documented
   GNU build path, and compare it with the fork on the same save.
5. Add a packaged, one-command setup for the toolchain (Rust + mingw + DXC) so a
   clean machine needs no manual steps.
