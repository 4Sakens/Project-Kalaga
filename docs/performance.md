# Performance: prologue frame rate on the RX 7600

Measured 2026-11-24 on Windows 11 26300, Ryzen 5 5600X, 32 GiB, Radeon RX
7600 8 GB, native D3D12, title `7952987A` v1.0.2.1, Series X profile.

The separate opening-pacing work (60 fps for the first 60 s, then the title's
30 fps) is in [opening.md](opening.md).

## Result

**The 15–30 fps target was not reached.** The best stable result is
**4.0–4.2 fps (240–249 ms/frame)** in the prologue, rendered at 640×360 and
scaled to the window. The scene is correct (yard, characters, watchtower,
sky) and the run had no device removal. Menus remain at 29–30 fps.

That is about **1.9×** the earlier 2.2 fps prologue result, but still short of
15 fps by 3.6×.

| Run | Build / render size | Configuration | FPS | Frame | GPU | Prepare | Readback | Draws |
|---|---|---|---|---|---|---|---|---|
| baseline | diag, 1080p | AMD skips, loop limit 256, DRED | 2.2 | 460 ms | 210 ms | 156 ms | 85 ms | ~5,000 |
| A | release, 1080p | low settings, in-place 2, 1 GiB card buffers, no relay | 2.7 | 373 ms | 230 ms | 88 ms | 46 ms | 4,970 |
| B | optimized diag, 1280×720 | in-place 2, GPU timing + DRED, no relay | 2.4 (timing on) | 420 ms | 262 ms | 100 ms | 48 ms | 4,966 |
| C | release, 640×360 | relay 2, in-place 1, card buffers | 3.5 | 285 ms | 162 ms | 114 ms | 195 ms | ~7,000 |
| **D** | **optimized diag, 640×360** | **relay 2, in-place 2, card buffers** | **4.0–4.2** | **240–249 ms** | **132–142 ms** | **96–97 ms** | **165–177 ms** | **4,900** |
| E | release, 640×360 | D + `VICTORY_INDIRECT_WINDOW=1` | **device removed** | — | — | — | — | 135,526 groups/frame |

Run D is the recommended configuration below. Run B's frame rate includes the
cost of timing every list; its value is the per-command breakdown, not its
fps.

## Where the time goes

Run B, one prologue frame, summed over the GPU's commands:

| Command kind | Time | Commands |
|---|---|---|
| indirect | 94–99 ms | 5,090 |
| dispatch | 35–37 ms | 3,787 |
| mesh | 4.9–5.5 ms | 378 |
| draw | 4.4–4.8 ms | 318 |
| alias copy | 3.9–4.0 ms | 78 |
| indexed, copy, texture, read | ~0.9 ms | 141 |

The GPU work is dominated by **single-record indirect mesh draws**, about
18 µs each. It is not fill rate: 1280×720 cut the total GPU section from
~230 ms to ~140 ms, but the indirect records still cost ~95 ms.

The steady 640×360 frame is three stages that the relay overlaps only partly:

- GPU 132–142 ms;
- preparation 96–105 ms, mostly 115–125 MB of title-memory copies per frame;
- readback 164–177 ms for 71–74 MB of shader-written title buffers.

Even with perfect overlap, run D cannot go below its largest stage, the
164–177 ms readback: that is ~6 fps. Without the relay but with in-place
stage 2, readback falls to 46 ms, but the GPU and preparation are then
serialized (run A: 373 ms, 2.7 fps).

In the no-relay stage-2 run, 3,518 title buffers (30 MB) were placed but
1,310 requests were turned down because they are view memory (the page
pool), which the host cannot open as a heap. The remaining 71–74 MB/frame is what the readback
costs. Stage 2 is also documented as incompatible with late waits, so it
cannot be combined with the relay's overlap.

## What was tried and rejected

- **`VICTORY_INDIRECT_WINDOW=1`** is the right optimization on paper: merge
  the title's one-record-per-call mesh draws into windows of up to 64,
  removing the per-record clamp. At `1684989` it folded in a 59,153-group
  record, asked for 135,526 groups/frame (normal is ~21,000), hung the GPU and
  removed the device (`0x887A0005`). Do not enable it on this commit.
- **`VICTORY_COPY_MODE=plain`** skips the mapped-page guard. It is documented
  as a timing aid, not a correctness mode, and was not used for the stable
  result.
- **XCL** is not an alternative yet: it has no release binary and its own
  reports for this title stop at world loading (issues #505 and #646: GPU
  watchdog / access violation). It was not built here because MSVC and the
  Windows SDK are absent.
- Resolution alone cannot reach the target: reducing 1280×720 to 640×360
  helped the GPU, but the 71–74 MB readback is title buffer state, not pixels,
  and did not shrink.

## Recommended configuration (run D)

Settings in the title's own `settings.xml` (backup before the experiment:
`logs/settings-before-perf.xml`, git-ignored):

```text
graphicsQualityPreset 0
lodScale 0.6
smallCullThreshold 0.5
grassLod 0
motionBlur false; motionBlurLimit 0; motionBlurScale 0
rtDynamicShadows false; rtLODLightShadows false
waterReflectionSSR false; ssroSampleCount 0
shadowParticleShadows false; shadowLongShadows false
fsrQuality 0
desiredFPS 60; frameRateLimit 60
```

Launch (release configuration, `logs/release-config.toml`):

```powershell
$env:VICTORY_SKIP_PIPELINES = (Get-Content docs/amd-skips.txt) -join ','
$env:VICTORY_SHADER_LOOP_LIMIT = '256'
$env:VICTORY_DISPLAY_MODE = '640x360'
$env:VICTORY_RELAY = '2'
$env:VICTORY_INPLACE = '2'
$env:VICTORY_INPLACE_MB = '4096'
$env:VICTORY_WIDE_BACK = '1'
$env:VICTORY_CARD_BUFFERS_MIN_MB = '1'
$env:VICTORY_CARD_BUFFERS_MB = '1024'
$env:VICTORY_JOIN_COPIES = '1'
$env:VICTORY_CARD_REHASH_RUNS = '1'
python -m kalaga launch --config logs/release-config.toml --timeout 900
```

### Quality profile at native resolution (2026-11-24)

The image was sharper at essentially the same frame rate, because the frame is
not fill-rate bound. This profile was tested at **1920×1080**:

```text
anisotropicFiltering 16
texLodScale_Mat_High 1.0
texLodScale_Mat_Med 1.0
lodScale 0.8
fsrQuality 0
gamma 15
vSync 2
```

with the same launch settings as above plus `VICTORY_INPLACE_MB=4096`. It ran
at **4.0–4.1 fps (244–252 ms/frame, 4,885 draws/frame)** with **0 device
removals**, versus 3.9 fps for the lower-quality native run. Hair, faces and
the uniform's printed panel are visibly sharper. The shadows and shadowed
clothing are still black; that is the missing ray-traced light in
[graphics.md](graphics.md), not texture filtering.

The run used the optimized diagnostics build (release profile with the
`diagnostics` feature); a plain release build may be marginally faster but
was not remeasured at 640×360. Logs: `logs/perf5-console.log`,
`logs/perf7-console.log`, and the matching `logs/victory-*.log` files.

## What would be needed for 15–30 fps

1. **Fix the indirect window.** Cap window records by their group/index count
   and reject a tail record that asks for more than a sane budget. Removing
   the ~95 ms of per-record cost is the only change here that plausibly moves
   the prologue into double digits. A safe window plus the current relay
   could put the frame near the readback floor (~165 ms, 6 fps), so it is
   necessary but not sufficient.
2. **Place view memory in place, or write shader results into title memory
   directly.** Removing the 71–74 MB readback is the other half. That is what
   takes the floor from ~6 fps toward 10–15.
3. Only after both: revisit resolution and the remaining compute passes.

Both are runtime changes in `D:\VIctory`, not configuration. Until they are
made and measured, 15–30 fps in the world is not a supported claim for this
machine.
