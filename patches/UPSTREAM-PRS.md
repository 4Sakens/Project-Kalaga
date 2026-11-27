# Upstream pull requests picked for VIctory-RDNA and Belobug (2026-11-26)

`patches/rdna/` and `patches/belobug/` hold open pull requests from
Belobug/VIctory-Belobug-AMD (~250 open) and TaynanGT/Vice-Tay (17 open),
the two busiest trees of this code family. VIctory-RDNA has none of its own.
Each file is the PR's own commit, author and message kept.

**Status: each series applies cleanly with `git am`, in order, to
VIctory-RDNA `2c5a395` and Belobug `a-publier` @ `4eb6cfd`. None of it has
been compiled or run** (the Windows toolchain is not available where they
were picked). Build, then play `-safe` first.

```powershell
cd D:\VIctory-RDNA            # or D:\VIctory-Belobug with patches\belobug
git switch -c kalaga-prs
git am --3way D:\Project-Kalaga\patches\rdna\*.patch
python -m kalaga build
python -m kalaga prepare --preset rx7600-rdna-safe   # 0001-0004 change shader translation
```

If a patch stops applying after `git pull`, `git am --abort` and drop that
file; the series is independent past 0002 (0002 is #442 with its test merged
next to #363's, which both add at the same place).

## What is in it

| # | PR | What it fixes | Kind | Switch |
|---|---|---|---|---|
| 0001 | Belobug #363 | `ds_bpermute_b32` read across a wave's two 32-lane halves; RDNA (GFX10/11) permutes each half on its own (LLVM, Mesa ACO). Wrong values in shaders that exchange lanes | picture | always |
| 0002 | Belobug #442 | Thread ids in 2-D/3-D groups on GPUs that fill groups in 2x2 quads: some ids never ran, some ran twice | picture | always |
| 0003 | Belobug #366 | Scalar results of divergent loops lost across wave32 halves | picture | always |
| 0004 | Belobug #345 | SGPR masks lost when an empty EXEC skips a compare-and-OR | picture | always |
| 0005 | Vice-Tay #114 | Parallel memory compares dropped the first partial piece: a title write could be missed (from fxceless/victory-fork #1407, found by Kelvaroq) | picture | always |
| 0006 (rdna) | Vice-Tay #112 | Parallel descriptor scans could overlap slot ranges (race) | stability | always |
| 0006 (belobug) | Vice-Tay #83 | Write-watch ranges already covered are not rescanned | CPU | always |
| 0007 | Belobug #372 | Idle draw lists (upstream: 9 GB of allocators) can be let go after N s | memory | `VICTORY_LIST_IDLE_TRIM_S=N` (off) |
| 0008 | Belobug #386 | Under memory pressure (≤ 3 GiB free RAM or ≤ 4 GiB commit) idle upload/staging memory is trimmed. With `VICTORY_RESIDENCY=1` (the rx7600-rdna presets) texture prefetch is also limited while under pressure | memory | always / with residency |
| 0009 (belobug) | Belobug #394 | Five memory switches for 32 GB PCs (resident waits for textures only, keep percent, staging in BAR, pressure by physical memory, windows BAR percent) | memory | all off by default |
| 0009/0010 | Belobug #410 | A pipeline still being made costs the full 500 ms wait only in its first frame | stutter | `VICTORY_PIPELINE_WAIT_AGAIN_MS=n` (off) |
| last | Belobug #426 | XMA audio decoder at higher thread priority: no crackle when the CPU is busy (matters on 6 cores) | audio | always |

The presets do not turn the new switches on: none has a measured value yet.
To test one, put it in `[launch.extra_env]`, e.g. `VICTORY_LIST_IDLE_TRIM_S = '30'`.

## Looked at, not taken

| PR | Why not |
|---|---|
| Belobug #397 hardware BVH4 ray tracing on RDNA 2+ (`VICTORY_HW_BVH=1`) | 1,121 lines, ray tracing is off on this PC anyway. **Worth revisiting**: it is the path that could make ray tracing affordable on AMD |
| Belobug #335 lazy list allocator retirement | No switch, no description, overlaps #372 |
| Belobug #394 on RDNA | Does not apply (RDNA changed the same lines) |
| Vice-Tay #103 held window copies counted in the RAM budget | Does not apply to either tree. Means `VICTORY_WINDOW_BUDGET_MB` (in the presets) may release less than set; harmless |
| Vice-Tay #109 integer bits in typed buffer stores, #113 cached mip publishing, #92 device-removal fence, #91, #111 | Do not apply; need porting by hand. #109 and #92 are the ones worth it |
| Belobug #432 frame-rate samples for benchmarks | Useful for a future `kalaga bench`; not needed to play |
| Geometry shaders (#433), DualSense (#420, #367), Wine (#421), RDNA4 compiler (#422), translations, docs, tests-only PRs | Not about this PC or not about playing |
