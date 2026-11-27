# Upstream pull requests picked for VIctory-RDNA and Belobug (2026-11-26)

`patches/rdna/` and `patches/belobug/` hold open pull requests from
Belobug/VIctory-Belobug-AMD (~250 open) and TaynanGT/Vice-Tay (17 open),
the two busiest trees of this code family. VIctory-RDNA has none of its own.
Each file is the PR's own commit, author and message kept.

**Status: each series applies cleanly to the base pinned in its
`UPSTREAM.toml`.** The **Runtimes** workflow (`.github/workflows/runtimes.yml`,
Actions tab) builds `victory.exe` and runs upstream's tests with the series on
a Windows machine on every change here and daily. **Verified 2026-11-27
(run 45929637837): both series build `victory.exe` and pass upstream's whole
test suite** — VIctory-RDNA 1,046 tests passed (1,026 unpatched: the patches
add 20), Belobug 1,087 (1,064 unpatched: +23). Two upstream tests that fail
on a GPU-less runner without our patches too are skipped
(`patches/rdna/KNOWN-FAILING.txt`). Not played yet.
Build, then play `-safe` first.

```powershell
cd D:\VIctory-RDNA            # or D:\VIctory-Belobug with --runtime belobug
git switch -c kalaga-prs
python -m kalaga patches --runtime rdna --dir D:\VIctory-RDNA   # skips and reports any that no longer apply
python -m kalaga build
python -m kalaga prepare --preset rx7600-rdna-safe   # 0001-0004 change shader translation
```

`kalaga patches` backs out a patch that no longer applies (after a
`git pull`, say) and applies the rest; the series is independent past 0002 (0002 is #442 with its test merged
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
| 0011 (rdna) / 0012 (belobug) | fxceless/victory-fork d036cea8 (#1366), what Vice-Tay #92 follows | **Device lost:** the fence then reads u64::MAX, and the relay took every flight as run and copied what the dead card's buffers held into title memory (a confusing crash later). A failed fence wait was ignored. Both now stop with a message naming the device removal. Ported by hand (Vice-Tay's own #92 only guards a readback pool these trees lack) | stability | always |
| 0010 (rdna) / 0011 (belobug) | Belobug #426 | XMA audio decoder at higher thread priority: no crackle when the CPU is busy (matters on 6 cores) | audio | always |
| 0012/0013 | Vice-Tay #123 | **Series S black world:** on Series S the title can pick AMD FidelityFX (type 7), whose DLL the host policy refuses: the world stays black. Both places the title asks (the picker and its per-frame copy) now return its own upscaler on the known build. `VICTORY_UPSCALER` still overrides; `VICTORY_TITLE_PATCHES=0` leaves the title's choice. On Belobug one hunk was placed by hand (`let mut prepared`) | picture | always on Series S |
| 0013/0014 | Vice-Tay #124 | **Slow-motion world below 15 fps:** the title never steps the world more than 1/15 s a frame, so at 8 fps it runs at half speed. `VICTORY_MAX_STEP_MS` (66.7-333; author: 100 is good) raises that limit on the known build; `VICTORY_STEP_LOG=1` logs game vs wall time | gameplay | `VICTORY_MAX_STEP_MS=100` (off) |
| 0014/0015 | Belobug #454 | **Upload-ahead race** (`VICTORY_UPLOAD_AHEAD=1`, on in every fast preset): a texture marked "upload pending" before its job was listed could be used before its texels arrived, or uploaded twice; a failed copy's waiters were still called | picture | always |
| 0015/0016 | Belobug #449 | Resource barriers from a state D3D12 does not allow (validation error, possible device removal); no-op barriers skipped | stability | always |
| 0016/0017 | Belobug #456 | `warm` on a fresh cache failed (os error 3: no pipelines folder): `kalaga prepare`'s first run at home. On VIctory-RDNA ported by hand (code only) | prepare | always |
| 0017/0018 | Belobug #397 | **AMD hardware ray tracing** (RDNA 2+): `image_bvh*_intersect_ray` through AMD's `IntersectBvhNode` intrinsic, per-lane software fallback. Reviewed: fully inert unless on (no shader gets its slots, the AMD extension is not loaded, the shader-cache key is unchanged). When on, a shader that needs the page VA table and does not get it is dropped with one log line. Ray tracing itself stays off in every preset | ray tracing | `VICTORY_HW_BVH=1` with `VICTORY_BVH_BUILDER=1` (off) |
| 0018-0020 (rdna) | Belobug ad0e5d5, 9460670, c485827 (in Belobug's base already) | **GTA V PC-style keyboard and mouse** (`VICTORY_KBM_GTA=1`): F2 or `` ` `` toggles mouse look, LMB/RMB shoot/aim, Shift sprint, Space jump, F enter, R reload, Tab weapon wheel, `VICTORY_MOUSE_SENS`, `VICTORY_MOUSE_INVERT_Y`; auto-hidden cursor; a pad takes over when used. VIctory-RDNA had only the keyboard-as-gamepad table (I/J/K/L camera). Code only (README excluded) | feel | on in every rdna/belobug preset |
| 0021 (rdna) / 0019 (belobug) | Belobug #420 | PS5 DualSense / Edge over HID (USB and Bluetooth, rumble) in pad slots XInput leaves empty: no Steam Input or DS4Windows. Xbox pads unaffected | feel | always |
| 0022 (rdna) / 0020 (belobug) | Vice-Tay 8ade3ab | **Full screen** (`VICTORY_FULLSCREEN=1`): the title's window a frameless popup over the primary monitor; AMD Fluid Motion Frames needs full screen. Vice-Tay's F11 toggle (3981f71) needs code these trees lack | feel | on in every rdna/belobug preset |

The presets do not turn the new switches on: none has a measured value yet.
To test one, put it in `[launch.extra_env]`, e.g. `VICTORY_LIST_IDLE_TRIM_S = '30'`.

## Looked at, not taken

| PR | Why not |
|---|---|
| Belobug #335 lazy list allocator retirement | No switch, no description, overlaps #372 |
| Belobug #394 on RDNA | Does not apply (RDNA changed the same lines) |
| Vice-Tay #103 held window copies counted in the RAM budget | Does not apply to either tree. Means `VICTORY_WINDOW_BUDGET_MB` (in the presets) may release less than set; harmless |
| Vice-Tay #109 integer bits in typed buffer stores | **Not needed:** it fixes Vice-Tay's NaN guard, which zeroed integers that look like NaN. VIctory-RDNA and Belobug have no NaN guard; their typed stores pass the bits through unchanged (a bitcast) |
| Vice-Tay #92 readback pool + device-removal check | The pool is Vice-Tay only; the device-removal fix it follows is ported from victory-fork instead (0011/0012 above) |
| Vice-Tay #113 cached mip publishing, #91, #111 | Do not apply; depend on Vice-Tay-only code |
| Second pass (2026-11-27 03:00 UTC): Belobug #451 exact-buffer pool rewrite (642 lines, perf), #453 "Radeon renderer fixes" bundle (576 lines, mixed), #444 (12 GB cards only); Vice-Tay #118 (readback-pool only), #125 monitor choice, #126 RAM keep-alive (Vice-Tay's RAM throttle only) | Not for this PC, too broad to take blind, or Vice-Tay-only code |
| Belobug #432 frame-rate samples for benchmarks | Useful for a future `kalaga bench`; not needed to play |
| Geometry shaders (#433), DualSense (#420, #367), Wine (#421), RDNA4 compiler (#422), translations, docs, tests-only PRs | Not about this PC or not about playing |

## Third pass: what the sibling trees fixed since VIctory-RDNA split off (2026-11-27)

VIctory-RDNA, Belobug and AvatarManz all branch from `c9c932c` (2026-11-26);
Vice-Tay merges from all of them. The commits since then that VIctory-RDNA
lacks were read (Belobug 31, AvatarManz 18, Vice-Tay 191) and these taken,
cherry-picked with `-x` (author and source commit kept):
`patches/rdna/0023-0042`, `patches/belobug/0021-0033` (those Belobug did not
already have and that apply).

| Source | What | Kind |
|---|---|---|
| Vice-Tay 00a21ef (from AvatarManz #206) | Under memory pressure idle texture copies go after 5 s. Measured on an RX 7900 XTX: 41 → 28.5 GB private at 18 min, 63.6 → 57.6 ms a frame. **The one for 32 GB** | memory, speed |
| Vice-Tay bd27027, 44b3757, 4ff4ea1 | Snapshot pool: let go of it when idle and shrink it under memory pressure; less lock contention between list threads | memory, CPU |
| AvatarManz 631400f, 3e04ca0, 15c3d0e | Renderer port 1 (`VICTORY_PORT_CONSTANTS`, on in the fast sets) ordering: indirect executions whose arguments the card reads in place are clamped alone. Its README: tree and lamp-lit room **flicker fixed** | picture |
| AvatarManz 4da7c0b, 8eaf2dc, 4aeb6d0 (rdna only) | Renderer port 2 (`VICTORY_PORT_DESCRIPTORS`): the frame allocator's table copies hooked; the fallback keeps the port's budget | picture, CPU |
| Belobug 5d6bd84 (rdna; Belobug has it) | Title textures uploaded in the submission prelude: **frame-order texture flicker** fixed | picture |
| Vice-Tay 8d56dd9 | BC7 channel rotation only in modes 4 and 5: **wrong texture colours** | picture |
| Vice-Tay 8fe3ccd | `v_fmac_f32` (VOP3) applies abs/neg to its accumulator: wrong shader maths. Only its own test kept (the conflict held Vice-Tay-only tests) | picture |
| Vice-Tay 17e3e2c | Wave sections scanned past an unmatched saveexec | picture |
| Vice-Tay 8cbd5cb, 53a1f16 | Texture retry deadlines kept when card room returns; pending texture changes kept when queues fill: **late or stale textures** | picture |
| Vice-Tay 7168410 (rdna only) | A panic while building one pipeline no longer kills its worker (every later pipeline on it went missing). Only its own test kept | stability |
| Vice-Tay 1fa36ec, c133996, 903aa10 (rdna only for two) | Warm-up worker failures; warm-up skipped when the title made no pipeline cache; device-loss range pattern | stability |

Not taken: Belobug 4ad8527 (port 2 sync parts) competes with AvatarManz's
port 2 rework above; Vice-Tay 3fe4811, 5307ba7, 7993c1b, e95a2f5, a550e0c
conflict with code these trees changed differently. Vice-Tay 2b51c6c (21 → 6
fps from exact copies of structured views) concerns cards without raw-twin
heaps (its RTX 4090); not this tree's path on AMD.
