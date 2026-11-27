# Optimization plan: faster without losing picture quality (2026-11-26)

For the VIctory-RDNA and Belobug runtimes (one code family) on this PC (Ryzen 5 5600X, 32 GiB, RX 7600 8 GB).
Written away from the machine. Nothing here is measured on it yet. Upstream
numbers are from Belobug's `docs/findings.md` (i9-12900K, 64 GB, 7900 XTX).

## What limits this PC (estimate)

Upstream, a 55 ms frame is **48 ms on the submit thread** (CPU) and **~41 ms
of card time**. This PC differs on both sides:

| | Upstream | This PC | Effect |
|---|---|---|---|
| CPU | 8 P-cores + 8 E-cores, 24 threads | 6 cores, 12 threads, ~15-20 % slower per core | Submit thread a little slower; its helper pools (8 + 6 + 6 + 4 + 8 threads) have half the cores to share |
| GPU | 7900 XTX, 24 GB | RX 7600, 8 GB, roughly 35-40 % of the raster speed | Card time likely **2-2.5×** longer: the card, not the CPU, is probably the wall here |
| RAM | 64 GB | 32 GB | Upstream uses 30-46 GB private. This PC will run in the runtime's memory-pressure modes and may page |

So, unlike upstream, the **picture settings decide the frame rate here**,
and memory decides whether it is smooth. That makes the order below matter:
remove costs that do not change the picture first, then pick the
quality/speed point with real numbers.

## Step 1 — free wins (no picture change)

| What | How | Why |
|---|---|---|
| No shader/pipeline stutter | `python -m kalaga prepare --preset NAME` after each build, and again after the first play session, for each preset you play (translations are cached per switch set: `-fast` turns on `VICTORY_PORT_CBV`, which changes them) | Upstream lost 270-660 s of a session to frames over 200 ms while pipelines were made. `prepare` runs `victory shaders` (translate everything) and `victory warm` (build every pipeline recorded by `VICTORY_PIPELINE_BOOK=1`, which the presets now set) |
| No out-of-memory crash on the 8 GB card | `VICTORY_TEXTURE_BUDGET_MB` 5120 / 4608 in every RDNA/Belobug preset | Series X ran out of graphics memory in the first cutscene on 8 GB cards in i95's runs. Below the cap textures load as before; above it, new ones wait instead of crashing the driver |
| Idle memory released under pressure | `VICTORY_WINDOW_BUDGET_MB=1536` (in all Belobug presets) | Window copies grow 2.8 → 4.3 GB in eight minutes. The cap applies only when Windows reports memory pressure, and a dropped copy is re-made on its next read |
| Commit headroom | Page file system-managed on the fastest SSD, 40+ GB free; close the browser/Discord | Belobug's memory bands use commit limit (RAM + page file). More headroom = fewer forced releases and no out-of-commit crash (error 1455) |
| Driver | Latest Adrenalin; run from a normal (non-admin) window | Admin runs put the driver shader cache elsewhere, so the warm cache is missed |

## Step 2 — pick the quality point (needs one test session)

| Preset | Picture | Expected cost |
|---|---|---|
| `rx7600-belobug-quality` | **Series X assets and settings**, drawn at native 1920x1080 (`VICTORY_RENDER_SCALE=1.0`) | Most VRAM (upstream 10.5 GB at 4K; 1080p is less, but probably still over 8 GB). ~2.1 Mpx a frame, fewer than Series X's default 2560x1440 |
| `rx7600-belobug` | Series S profile (1080p output from 1280x720, smaller textures) | Fits 8 GB on the 8 GB-card forks; softer image |

If the quality preset holds 8 GB without textures arriving late or turning
blurry, and is within ~20 % of the Series S fps, use it. If not, Series S.
The goal is the best picture that keeps the card under 8 GB. Running out of
VRAM costs more fps and picture than any setting.

Ray tracing (`VICTORY_BVH_BUILDER=1`) stays off for now. Upstream it costs
about a third of the frame and more memory; the title's ambient stand-in
(`VICTORY_AMBIENT=0.8`, in the presets) keeps interiors from going black.

## Step 3 — CPU-side speed (no picture change, needs testing)

| Preset | What it tries |
|---|---|
| `rx7600-belobug-6core` | List and compare pools sized to 12 threads (4 and 3, from 8 and 6) so they stop crowding the submit thread. Pipeline workers and the descriptor pools are left at upstream's counts: fewer pipeline workers means draws left out longer (missing objects), and the submit thread waits on the descriptor pool |
| `rx7600-belobug-fast` | The five `VICTORY_PORT_*` renderer patches: upstream −8 to −10 ms on the submit thread. Off by default upstream while tested; if anything looks wrong, drop back |

These matter only if Step 2 shows the CPU is the limit. Check: GPU usage in
Task Manager below ~90 % while fps is low means CPU-bound.

## The test session (one command, when home)

```powershell
git pull
python -m kalaga patches --runtime rdna --dir D:\VIctory-RDNA   # optional: the picked upstream PRs
python -m kalaga build
python -m kalaga prepare --preset rx7600-rdna
python -m kalaga session                       # rdna-safe, rdna, rdna-quality; ~6.5 min each
```

`kalaga session` starts each preset in turn (press Enter before each), keeps
it running for 4 minutes in the world plus 150 s to load, then stops it.
Play the same save and the same route every run. It reads the runtime's own
once-a-second frame line (only seconds with over 1,000 draws count, so menus
and loading do not), samples the game's RAM and dedicated graphics memory
every 20 s, and prints:

| Preset | In world | fps median (p10-p90; 1% low) | Prep / GPU ms | Bound | Hitches <10 fps | Dropped draws | Peak RAM | Peak VRAM | Exit |
|---|---|---|---|---|---|---|---|---|---|

"Bound" says which side the frame waits on: **GPU** means picture settings
decide the frame rate (Step 2), **CPU** means Step 3 matters. Exit "time up"
is a normal stop; any number is a crash (the log is in the bundle). Then the
Belobug runs: point `victory_dir` at it and `kalaga session --checkout belobug`.

Send `logs\session-<time>.zip`: the table, every run's log and the tail of
the runtime's crash log.

## Code work after the numbers (in order)

1. **Pool sizes from the core count**, in the runtime itself, if `-6core`
   helps: a small upstream PR to Belobug, useful to everyone on 6-8 core CPUs.
2. **Memory for 32 GB machines**: upstream lists list allocators 9 GB,
   windows 7 GB, uploads 4 GB. Candidates: a smaller idle-list pool
   (512 lists / 256 MB now) under the RAM bands, and the same budget idea for
   uploads. Measure with `VICTORY_MEMORY_MAP` in a `kalaga build --diag` run.
3. **Texture streaming on 8 GB**: `VICTORY_TEXTURE_ROOM_PERCENT` (upstream
   default 90 % of the card's budget, which already counts buffers and render
   targets, so it scales to 8 GB by itself). Change it only from the
   dedicated-memory numbers; late textures mean too low,
   blur or device loss means too high.
4. **Bring Kalaga's mouse-look and PC prompts over** only if Belobug's own
   `VICTORY_KBM_GTA=1` mapping falls short.
5. **Ray tracing** comes last: only once the frame has room for it, since
   it is the one quality feature that costs a third of the frame.
