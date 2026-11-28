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
| Vice-Tay 1fa36ec, 903aa10 (rdna only) | Warm-up worker failures; device-loss range pattern | stability |

Not taken: Vice-Tay c133996 (warm skipped on a fresh cache) solves what Belobug #456, already in the series, solves the other way (its test failed against it); Belobug 4ad8527 (port 2 sync parts) competes with AvatarManz's
port 2 rework above; Vice-Tay 3fe4811, 5307ba7, 7993c1b, e95a2f5, a550e0c
conflict with code these trees changed differently. Vice-Tay 2b51c6c (21 → 6
fps from exact copies of structured views) concerns cards without raw-twin
heaps (its RTX 4090); not this tree's path on AMD.

## Fourth pass (2026-11-27 morning)

**VIctory-RDNA moved** `2c5a395` → `68402ce` (merged AvatarManz 014d52d: the
port 1/2 ordering and prelude-texture fixes; an RX 7900 XT run of 23 min 50 s
at 20.8 fps median, 30.8 peak, 20.3 in heavy scenes). The rdna series is
re-pinned there: seven of its patches are now upstream and were dropped
(4da7c0b, 8eaf2dc, 4aeb6d0, 631400f, 3e04ca0, 15c3d0e, 5d6bd84); Vice-Tay
7168410 was ported by hand onto the new `Pending::make` (it skips keys the
driver's compiler crashed on; a Rust panic in one build is now caught too).

VIctory-RDNA's preset now sets `VICTORY_PORT_CONSTANTS_ORDER=0` (8ba4f34),
for speed. Its code says that with it off palms and trees went missing for
runs of frames while the camera moved; its README lists distant vegetation
flicker. Kalaga's presets set it to `1`. Its preset also sets
`VICTORY_THIN_THREADS=14` (+2.8 fps on a 24-thread CPU); not copied for a
12-thread 5600X (the session's `-6core` run tests the other direction).

New Belobug PRs taken (single commits, authors kept):

| PR | What | rdna | belobug |
|---|---|---|---|
| #460 | Two GPU reads that aborted instead of failing gracefully | yes | yes |
| #475 | A damaged shader operand no longer panics (parsers fuzzed in tests) | yes | yes |
| #552 | Device removal handled in the keep-awake fence | yes | yes |
| #612 | Shader translation: root constants' dword 0 as a dynamic offset | yes | yes |
| #614 | VRAM accounting and eviction count mapped tile bytes of levels-on-demand textures: **8 GB** | yes | yes |
| #548 | Only the indexed-texture batch due this pass is selected (CPU) | yes | yes |
| #560 | Matching copy-queue upload buffers reused (CPU, memory) | yes | yes |
| #565 | Straddling 16-bit global loads joined across dwords (picture) | no (does not apply) | yes |
| #569 | In-place memory turned on only after the host heap is checked coherent | no (does not apply) | yes |
| #537 | Idle thin recording buffers bounded by bytes (memory) | no (does not apply) | yes |

Looked at, do not apply to either yet (worth porting when upstream settles):
#470 failed texture detile retried, #618 LDS index clamp, #577 join EXEC
restore, #623 v_cube denormals, #555 texture-cache staging files, #497 XMA
audio on slow frames.

## Fifth pass: black and blurry textures (2026-11-27)

Both series (rdna 0049-0055, belobug 0044-0049):

| Fix | What it does on screen |
|---|---|
| up-d15d8e7 BC7 entry 0 | BC7 blocks that pick dictionary entry 0 decoded wrong: black or garbled patches on compressed textures |
| up-dbfb5a9 heap samplers keep point mips | anisotropic samplers from the heap blended mip levels the title asked to keep apart: a soft, smeared look on ground and walls at an angle |
| up-037c531 comparison sampler | a comparison sampler kept the filter's min/max reduction: shadow lookups came back all-dark |
| up-7ae1afc readback stays pending | a texture read back before its copy landed came back zeroed: black textures after a GPU write |
| up-26aeded sparse read of holes | a read of only unmapped tiles replaced the texture's digest, so the texture was never refreshed again |
| up-7993c1b GPU-written views copied | a view of a texture the GPU wrote after a CPU upload kept showing the old (often black) contents |

RDNA only: belobug-pr287 (avatarmanz#256) a texture the card had no memory
for kept a null, black view for good; it is now made again on the next ask.
Belobug's a-publier has no `resource::retrying` yet, so this one waits there.

Not taken: c92d5cf (publish cached mips; RDNA reworked the upload into
`PreludeUpload`, 6 conflicts), c44e2ce (#283 on-demand levels within the VRAM
budget, 525 lines), 79d0b2b (overlaps #287), #470 (detile retry, 360-line
conflict). 1ad6e67 (Series S black screen) is already in RDNA as 85a663d.

## Sixth pass: DexNom/VIctory and the original Marvisak/VIctory (2026-11-27)

DexNom/VIctory is a fork of Marvisak/VIctory carrying ZSlayerHQ's
victory-world Radeon line as one squashed import (570a941e, 170 files) plus
20 commits. Marvisak/VIctory is the original; it diverged from VIctory-RDNA
at ffe310e (2026-11-24), and many of its fixes are already in RDNA under
other wording. Both series (rdna 0056-0059, belobug 0050-0053):

| Fix | What it does |
|---|---|
| dexnom-76749ce5 wave64 mask from scalar copies | a wave64 mask parked in two SGPRs and restored dword by dword was not recognised: the voxel visibility shader failed to translate |
| dexnom-ddb73326 sampler chosen by a branch | a phi of two immediate samplers could not be lowered: DexNom counts 40 world shader variants lost (their draws were dropped) |
| dexnom-921d8d3b interior mips | a streaming texture with only its middle levels mapped counted as absent and stayed black |
| marvisak-78ed12eb null CBV | a null constant buffer description cleared nothing, so the slot kept another buffer's constants |

Already in RDNA: integer-target blending (`host_blend`), the base-2 LOD
fix, pixel quad reads reaching helpers, normalized buffer codes.

Not taken: DexNom 5f4c3df4 (City texture streaming and Radeon shadow
pipelines, 2,600 lines over 27 files) and bc3cd4b0/b8ff22e4 (ray tracing
preview), both built on the victory-world tree; the rest of 921d8d3b
(early depth pipeline queue: RDNA's queue is different; ray buffer views).
Marvisak 0736f8b3 (Series S UI planes composited) is already in both trees in
another form: `compose.rs` lays the second (UI) plane over the scene, on by
default (`VICTORY_PLANES`, from codec-d/cool_fox). 61bfc773
(placed unordered texture views), 842b0cb7 (depth bounds reach the host),
315cea18 (barrier start states): large conflicts. 4a53da72 fixes a bug in
discard handling that RDNA does not have. 77fd8195 (cube denormals) needs
an ftz helper RDNA lacks. e53474cd is an NVIDIA-only device removal. ea488a9f (typed UAV format
check) applies as text but needs helpers neither tree has (CI caught it).

## Seventh pass (2026-11-27 afternoon)

**VIctory-RDNA moved** `68402ce` → `9cd7782`: four docs commits, a 7900 XTX
benchmark. Its A/B confirms what our presets set: `VICTORY_PORT_BUFFERS=1` +
`VICTORY_INPLACE=2` take 3-5 ms of CPU preparation off a frame. The series
applies unchanged.

rdna 0060, **dexnom-5f4c3df4** (the idea, not the code): the texture pass
served every slot waiting for its memory before any new one, so a city's
backlog could keep new textures from ever being made (black or low-detail
surfaces). With both waiting, the waiting ones now take at most half a pass
and the two take turns; with room for all, nothing changes. The rest of
5f4c3df4 (packed masks, guest addresses for ray shaders, shadow pipelines)
is built on lowerer state VIctory-RDNA does not have.

**Belobug/VIctory-Belobug-AMD stopped answering anonymous fetches** today
(a login prompt from GitHub's own runners too: private, deleted or down).
The CI skips its legs with a warning until it comes back; the series stays
as it was (0001-0053) and is not extended, since nothing new could be built
or tested. A Belobug checkout made before today still works with it.

From the first `kalaga candidates` run (rdna 0061-0062):

| Fix | What it does here |
|---|---|
| fxceless-pr1442 pipeline library loads | loads of different pipelines shared 64 locks by name hash, so two unrelated loads could wait seconds on each other: stutter while pipelines come in. Now only the same name waits |
| fxceless-pr1491 audio DSP convolutions | TVs, phone calls and reverb go through the console's audio DSP, whose outputs were zeros: those were silent and reverb dry. Mono 1024-frame convolutions are computed now (`VICTORY_DSP_CONVOLVE=0` off, `VICTORY_DSP_GAIN`) |

Marvisak #2254 (v_mad_i64_i32 literal sign) applied as text, but VIctory-RDNA
does not translate v_mad_i64_i32 at all, so its test failed in CI: dropped.

rdna 0063 (Kalaga's own): GameInput says once which input kinds the title
asks for. Whether GTA VI's Xbox build ever asks for keyboard or mouse
readings decides how keyboard button prompts can be had: fed a real keyboard
and mouse if it does, or its pad button icons swapped if it does not. The
session summary and `kalaga bug` read the answer from the log.

## Eighth pass: VIctory-NVIDIA, foxhound, Kelvaroq (2026-11-27 evening)

New public projects from the PortWatch tracker: trustno1-coder/VIctory-NVIDIA
(80% story, ~20 fps, verified; shares history with VIctory-RDNA, ~800 commits
ours lacks, now based on foxhound), readmet3xt-lab/foxhound (NVIDIA-tuned,
history squashed to 2 commits: hand ports only), stellarr-studio/kelvaroq
(its own codebase, 25% story). CGBJ's codec-d/cool_fox went private.

rdna 0064, **vicetay-d8247162 NaN guard** (the "black blobs" fix VIctory-NVIDIA
describes): a NaN a pixel program exports to a colour target becomes 0 and an
infinity ±65504, the same for typed stores (only the GPU's own NaN pattern,
so integer bits pass). One bad pixel no longer spreads through the title's
history buffers, blur and upscaler into black patches on faces and in the air.
`VICTORY_NAN_GUARD=0` turns it off; part of the shader cache fingerprint.

Looked at, not taken:
- **FSR 3 frame generation** (VIctory-NVIDIA 29d8dbf7): runs on their
  Streamline layer, and without DLSS upscaling (any AMD card) the title stops
  on a check 5-11 s in, on either console (their issues #272, #308, #331; their
  df2daafe now refuses it without DLSS). Waits for a cause, and for a PC to
  test on. AFMF stays the frame generation for the RX 7600.
- **Open water without dark blocks** (35c15608): the two water light programs
  go dark only in the wave-wide form a 32-lane host needs. VIctory-RDNA on a
  Radeon declares their wave size (64) and runs them natively.

## Ninth pass: CPU time and long sessions, from foxhound (2026-11-27 night)

The frame rate on this runtime is set by one CPU thread that prepares and
submits each frame (VIctory-RDNA's own benchmark: ~30 ms of preparing a frame
on a 24-thread Zen 3 at 4K; foxhound: the card idle a third of the time where
fps drops). On a 6-core 5600X that thread matters most. From
readmet3xt-lab/foxhound 0.2.0-pre.4 (VIctory-RDNA pin moved to c0d38c3, docs
only upstream):

| Patch | What it does |
|---|---|
| rdna 0065 foxhound-texsweep | a texture whose host copy was let go kept its last-use stamp, so every later sweep sorted it and took its lock for nothing: sweeps grew through a session (3 ms after a minute, 14 ms after 30 in foxhound; "5 fps after 10 minutes", stuttering sound). The stamp is cleared when the copy goes |
| rdna 0066 foxhound-dstorage-priority | streaming workers (one per processor) run below normal, so the threads a frame waits for get the cores first while a scene streams in (`VICTORY_DSTORAGE_PRIORITY=-1`; 0 as before, which the `+safe` crash retry sets; `VICTORY_DSTORAGE_WORKERS`) |
| rdna 0067 foxhound-passes-hot | copy helpers woken at each submission's start (`VICTORY_PASSES_HOT=1` in the rdna presets, as foxhound's launcher; longest frame 525 -> 145 ms in their walk) |

Not taken: `VICTORY_TEXSPK_PASS_MS` (a frame's texture passes within 8 ms:
+20% fps in foxhound, but new textures show later; VIctory-RDNA gives texture
passes 250 ms and triples that while a backlog drains so surfaces are not
black, which is the problem being chased here), and the prelude pool (memory,
not time).

CI: the rdna bare and patched legs now run the runtime's GPU-free timing
tests (`Speed tests` in the job summary) so a patch that slows the CPU side
shows before a PC run.

## Tenth pass (2026-11-27 late)

rdna 0068 **foxhound-lds-first-init**: a compute program whose LDS set-up is
done by the group's first thread alone skipped it when that thread had left,
and on a PC the group then read leftovers: 71 of 124 such tiles of the water's
tiled light wrote nothing (dark slabs on water along the horizon and beside
rocks and hulls). The first thread now always does it
(`VICTORY_LDS_FIRST_INIT=0`: as the console). Not wave-size specific.

From the evening's candidates run (41 applied cleanly; taken where they help
this PC):

| Patch | What it does here |
|---|---|
| 0069 marvisak-pr3383 | XMA audio: voices boxed, inactive slots skipped in the pump, per-frame scratch reused (less audio CPU time beside the frame on 6 cores) |
| 0070 marvisak-pr2795 | XMA2 inverse MDCT 24-29% faster |
| 0071 marvisak-pr2663 | XMA: 10-bit VLC lookup table, 64-bit bit peeks, quant-factor table |
| 0072 marvisak-pr3629 | XMA: paired overlap samples walked directly |
| 0073 dexnom-pr96 | tests for XMA interleaving and empty packet chains (the fix itself is in VIctory-RDNA already) |
| 0074 marvisak-pr1437 | packed D16 image loads keep the unwritten high half |
| 0075 dexnom-pr140 | v_writelane_b32 takes its lane from S1[5:0] in wave64 (the RX 7600 runs those programs as wave64) |
| 0076 fxceless-pr1006 | the shader code table starts after the instructions (a device fault on RTX 5090, port of Marvisak #2143) |

Not taken: foxhound's `VICTORY_LDS_LOOP_ATOMICS` (cloud tiles' sort): built
on an LDS ordering pass VIctory-RDNA does not have; Marvisak #3631 (did not
apply after the other XMA changes); diagnostics, Proton/Linux, docs and
test-only PRs.

A backup bundle of VIctory-RDNA at c0d38c3 with a `kalaga-prs` branch (all
patches applied) was handed to the user, as Belobug's was.

## Eleventh pass: measured CPU work per frame (2026-11-27 night)

Kalaga's `bench` branch runs VIctory-RDNA's GPU-free frame benchmark
(`refresh_tests::frame_of_refreshes`: a recorded frame's 30 submissions of
buffer refreshes, 4,400 copies, a 174 MB heap with landed pieces) on the
patched tree with phase timers and the runtime's diagnostics counters, on
GitHub's Windows runner (4 threads; numbers are noisy run to run, so every
comparison is within one run).

- **`VICTORY_ASK_SPREAD=1` is slower**, and is now left out of the rdna
  presets (VIctory-RDNA's preset turns it on; its history says "not yet
  measured"). Several threads asking the kernel's write watch at once wait on
  each other inside the kernel: refreshes 35 ms a frame with it, 27-29
  without; kernel time in askings 71 ms (all threads) against 7.
- **rdna 0077 `VICTORY_ASK_GAP_KB`** (Kalaga's): how far apart a
  submission's ranges may be and still be one asking (8 MiB by default, as
  before). 1 MiB walked 1.0 GB a frame instead of 2.6 GB and took the
  refreshes from 18.5-21.0 to 15.6 ms (and 30-34 to 26-28.6 on a slower
  runner); 256 KiB was no better; 16 MiB was worse. Where each reset call
  costs more (more cores), a wider gap may win, so the default stays and the
  test session gets `rx7600-rdna-askgap` (1 MiB) to measure on the PC.
- `VICTORY_ASK_NORESET=1` was slower here too (not used).
- What is left in a refresh: `copy_stale` ~14 ms (all threads; ~124 MB a
  frame copied, mostly pieces the card wrote landing back through another
  copy of the same memory), `watch::writes` 7-8 ms. Cutting those means
  changing the journal's design; left for game-side profiles.

## Twelfth pass: lighting without rays (2026-11-27 night)

GTA VI ray traces its indirect light (probes, bounce, reflections). The real
thing (`VICTORY_BVH_BUILDER=1`) costs ~40 ms of a 7900 XTX's time a frame
and runs at 3-5 fps on the tracker's cards; on an RX 7600 it is out of reach.
Without it, everything the sun does not reach is black, and VIctory-RDNA's
stand-in (`VICTORY_AMBIENT=0.8`, on in the presets) estimates that light from
the frame. From trustno1-coder/VIctory-NVIDIA (readmet3xt-lab and Ahyildiz),
hand-merged with VIctory-RDNA's band and settling:

| Patch | What it does |
|---|---|
| rdna 0078 nvidia-826ba150 | the bluer kind of violet garbage the probes leave is dropped (a purple-blue glow on bright surfaces); the magenta kind was already |
| rdna 0079 nvidia-8cf0a752 | `VICTORY_AMBIENT_ONCE=1` (off): the stand-in's own light no longer comes back to it, one bounce of the title's light instead of settling 1.3-1.75x brighter (overexposed rooms). The pass's constants grew from 16 to 20 to hold it beside VIctory-RDNA's |
| rdna 0080 nvidia-2db59d48 | `VICTORY_AMBIENT_SPECULAR=<share>[,<sky>]`: reflections whose rays found nothing took the sky's light, 100-1000x the room and blue (eyes glowing blue-white, blue blotches on floors); now the light estimate along the reflected direction. Screen-space reflections still write over it. Also hooked on VIctory-RDNA's indirect dispatch path, where nothing is held back |
| rdna 0081 nvidia-9f6fb779 | only opaque surfaces (the alpha layer's depth is what lies behind glass and water: dark patches around boats); `VICTORY_AMBIENT_SPECULAR_ALPHA=1` puts it back |

The rdna presets set `VICTORY_AMBIENT_SPECULAR=1` (as foxhound's launcher);
the `+safe` crash retry sets it to 0.
