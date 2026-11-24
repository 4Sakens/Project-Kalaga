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
game dir   : D:\GTA 6\GTA6.Xbox.v1.0.2.1-CYBERLEEK
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
`python -m projectz build --diag` in 1m 03s.

## Run — what actually happened

Command composed by `projectz launch`:

```text
D:\VIctory\target\x86_64-pc-windows-gnu\release\victory.exe run "D:\GTA 6\GTA6.Xbox.v1.0.2.1-CYBERLEEK\game_scarlett_master.exe" --execute --console series-x
```

Boot sequence from the log:

```text
build          unknown (b99f876b74d4a77f03af5f878223b27bd647b5c35a79d5decd9f716504239e93)
image mapped base=0x7ff8a7170000 preferred=0x140000000
title          7952987A, storage ...\victory\data\7952987A/storage (2048 MB)
virtual drive  drive=G root=D:\GTA 6\GTA6.Xbox.v1.0.2.1-CYBERLEEK
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

### Where the front end stops

The start-screen key art renders, then the host device is removed while the
menu scene compiles and draws. Measured on both adapters:

* **WARP:** three runs removed the device with DXGI 0x887A0004 / 0x887A0005,
  once at a 1-list submission with no breadcrumbs and once at a 28-list
  submission (DRED breadcrumbs: 2048² and 4096² compute passes, 32³ volume
  upload). Skipping the five heaviest compute pipelines removed all dispatches
  (`dispatched=0`) but the device was still removed during front-end resource
  work, so this is not only post-processing cost.
* **RX 7600:** the cached run translated 1,826 shaders, then removed the device
  after an 11-list submission with 0x887A0006. At that point it was at
  0.6 fps / 1,600 ms per frame, 1,448 draws/frame with 1,561 draws dropped for
  missing host pipelines. The desktop stayed responsive; the title's D3D12
  device was removed and the process exited.
* The log names mesh `093c64546c55554e` (11 draws/frame) and compute shaders
  that fail translation with "a structured buffer of unknown stride",
  "image_gather4_l", "a lane mask holding lanes elsewhere read as data", and
  "a descriptor neither loaded nor built".

The menu buttons/options were therefore never presented, and no world/gameplay
frame was reached.

## What is implemented, what is verified

| | Implemented | Verified |
|---|---|---|
| Dump discovery + identity | yes | yes, on the real 208 GiB dump |
| Archive/manifest validation | yes | yes |
| Hardware/toolchain doctor | yes | yes |
| Runtime planning with fixes | yes | yes |
| Runtime build (release + diag) | yes | yes, 2 successful builds |
| DXC staging | yes | yes, DLLs copied next to the exe |
| Launch + logging + exit diagnosis | yes | yes, 10 runs (release + diag, WARP + hardware) |
| Title boot / rendering / audio / input | upstream | yes, evidence above |
| Menus beyond first boot | upstream | yes — account picker, legal notices, setup wizard, terms, loading art, start-screen art |
| Start-screen menu buttons | upstream | no — host device removed while the menu scene draws |
| World / gameplay | upstream, incomplete | no — not reached |

## Remaining barriers

1. **Front-end scene** (upstream): after 1,826 translated shaders the host
   device is removed while the start-screen menu draws, on WARP and on the
   RX 7600. Measured 1,600 ms/frame and 1,561 dropped draws at that point.
2. **Shader translation gaps** (upstream): compute shaders using unknown-stride
   structured buffers, `image_gather4_l`, cross-lane masks, or descriptors
   neither loaded nor built are dropped; mesh `093c64546c55554e` has no host
   pipeline.
3. **World rendering** remains untested behind the front-end failure; the
   earlier upstream warning about world entry and display-driver hangs still
   stands.
4. **No Visual Studio** on this machine: fine for the GNU target, but upstream
   CI and D3D12 debugging aids assume MSVC.

## Next steps

1. Reproduce the hardware 11-list submission with `VICTORY_D3D12_DEBUG=1` and
   `VICTORY_GPU_TIMING=1`; identify the invalid command, then add the missing
   converter op or skip only that pipeline.
2. Close the four converter gaps above so the start-screen menu can present,
   then capture its buttons/options.
3. Only then measure world frames with `VICTORY_SHADER_LOOP_LIMIT` and
   `VICTORY_SKIP_PIPELINES` — this is the upstream bottleneck, not a launcher
   issue.
4. Build XCL through the same tooling (`projectz build --runtime xcl`) and
   compare GTA VI bring-up progress between the two runtimes.
5. Add a packaged, one-command setup for the toolchain (Rust + mingw + DXC) so a
   clean machine needs no manual steps.
