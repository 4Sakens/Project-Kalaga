# Opening / front-end smoothness

Measured 2026-11-24 on the same machine as
[performance.md](performance.md): RX 7600, 1920×1080, Series X profile,
fork `fxceless/victory-gta6` at `1684989`.

## What was happening

The title asks the runtime for **33.333 ms frames** during the front end
(`frame interval interval=33.333ms` in the log), so the account picker, logo
and loading sequence are authored at 30 fps. In the captured 30 fps opening
the first 64 presented frames averaged **55.2 ms/frame** while pipelines were
being made, then settled to ~33 ms. The opening is also mostly a black screen
with a small spinner for roughly the first 32 s, before the painted loading
art and the Jason/Lucia key art.

Turning the frame clock to 60 fps for the whole run did make the loading phase
60 fps, but it produced queue warnings once the title's own 30 fps cadence
took over:

```
WARN victory_gpu::queue: a wait for a memory value was not met at a present
WARN victory_gpu::queue: a queue still held a submission at a present
```

The 30 fps runs have **zero** of those warnings. An unrestricted 60 fps
override is therefore not safe.

## What was changed

A small, reversible patch to `crates/victory-gpu/src/frame.rs`:

- `VICTORY_FRAME_INTERVAL_US=16667` overrides the interval the title asks for.
- `VICTORY_FRAME_60_SECONDS=60` (default) ends the override after that many
  seconds and restores the title's own interval, resetting the tick clock
  cleanly so no tick is lost or repeated.

The patch is [`patches/0001-opening-60fps-window.patch`](../patches/0001-opening-60fps-window.patch).
`projectz.toml` passes the two values through `[launch.extra_env]`, so a normal
`python -m projectz launch` uses them.

## Measured result

From `logs/victory-20261124-164520.log`:

| Phase | Frame line | Interval | Warnings |
|---|---|---|---|
| Loading / account picker | **60.0–62.0 fps, 16.1–16.7 ms** | `title=33.333ms interval=16.667ms seconds=60` | 0 |
| After the 60 s cutoff (key art) | **30.0 fps, 33.3 ms** | title's own | 0 |

The loading art is visibly smoother at 60 fps, and the key art is a static
image, so its 30 fps cadence does not matter. The run had no device removal.
The 60 fps phase adds no loading step: it only changes how the existing real
time frames are paced.

### Settings that keep the world stable

The 60 fps window was verified with `vSync=2`, `fsrQuality=0`. A later quality
profile — `anisotropicFiltering=16`, near-material LOD `1.0`, `lodScale=0.8`,
`VICTORY_INPLACE_MB=4096` — also held at native 1920×1080: **4.0–4.1 fps with
0 device removals**, and visibly sharper materials. The combination that
removed the device was FSR quality 2 with `vSync=1`; keep FSR off and test the
world after changing the display settings. Details are in
[performance.md](performance.md) and [graphics.md](graphics.md).

## Limits

- This smooths the **real-time** spinner/logo/loading frames. It does not add
  frames to pre-rendered 30 fps video content.
- The key art and the title's post-loading front end stay at the title's
  authored 30 fps; that is deliberate.
- Audio/video sync during the 60 s window was **not listened to**. If the
  opening's audio drifts, lower `VICTORY_FRAME_60_SECONDS` (for example to 30)
  or remove the override.
- The black loading screen itself is the title's own screen; this patch makes
  it smoother, not busier. A custom splash would be a separate launcher
  feature and was not added.

## Apply / revert

Apply and rebuild:

```powershell
cd D:\VIctory
git apply D:\ZZ-box\patches\0001-opening-60fps-window.patch
$env:PATH = 'D:\projectz-deps\mingw64\bin;' + $env:PATH
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = 'gcc.exe'
cargo +1.98.1-x86_64-pc-windows-gnu build --profile release --features diagnostics `
  -p victory --target x86_64-pc-windows-gnu
```

`projectz.toml`:

```toml
[launch.extra_env]
VICTORY_FRAME_INTERVAL_US = "16667"
VICTORY_FRAME_60_SECONDS = "60"
```

Revert by removing those two lines and checking the file back out in
`D:\VIctory`, then rebuilding. Without the patch the environment variables are
ignored and the runtime behaves exactly as before.
