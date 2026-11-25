# Light passes — map and repository check (2026-11-24)

This maps the light-related shader passes seen in the diagnostic tree
`D:\VIctory-shadow` and records what changed in the local/upstream repositories.
The stable `D:\VIctory` checkout and binary were not modified.

## Result in one paragraph

The five hashes previously called “shadow-mask trace programs” are **not five
shadow traces**. Their `.cdxil` containers carry debug names: one raytracing
resolve, the two irradiance-cache shade programs, a matrix transpose utility,
and water optical-depth processing. Upstream commit `90228a7` restores parked
lane-mask pairs and makes the resolve and both irradiance shaders translate
exactly. The tiny transpose program still needs the approximate 16-bit half-sum
relaxation; without it the prologue stays black even though the other four
translate. With exact masks plus that one relaxation, all five translate, the
prologue is clearly lit, there are 0 device removals, and gameplay is 3.6 fps.
A follow-up cell capture with the same combination (run D) shows the cell and
cell block still essentially unlit: lamp panels glow but light nothing around
them, and faces and clothing are black. The earlier “partial cell light” claim
for run A had no supporting image (its cited captures are the desktop and the
PROLOGUE card), so it is withdrawn. The gain is a prologue/sunlit-exterior
result, not indoor light.

## The five programs, by their container names

| Hash | `.cdxil` debug name | Observed role | Old refusal | Exact now? |
|---|---|---|---|---|
| `7f05ddab771799a9` | `CS_RaytracingResolve_a56bfb9c_Wrapped` | raytracing resolve / composite of traced results | lane mask holding lanes elsewhere | yes, upstream `90228a7` |
| `a53a7977fe762268` | `CS_IrradianceCache_Shade_823aad37_Wrapped` | primary irradiance-cache shading (indirect light) | lane mask holding lanes elsewhere | yes, upstream `90228a7` |
| `be14e72d86362031` | `CS_IrradianceCache_ShadeSecondary_185f8341_Wrapped` | secondary irradiance-cache shading | lane mask holding lanes elsewhere | yes, upstream `90228a7` |
| `b22a16a178976e1b` | `CS_TransposeVecMatMulAlignedOperation_81003b08_Wrapped` | matrix transpose / vector-matrix utility used near the light dispatch | 16-bit wave sum where not every lane runs | no; `VICTORY_WAVE_HALF_SUM_ANY=1` only |
| `a929109552ce1e84` | `CS_WaterTransmittanceOpticalDepthProcessing_44443e79_Wrapped` | water transmittance / optical depth | `v_permlanex16_b32` | yes, this worktree's permlane port |

The names come from ASCII labels embedded in the `.cdxil` containers in
`logs/shaders-upstream-half/`. The names are diagnostic strings, not source
code or game assets.

Binding order in the successful log (`first bind`, not necessarily dispatch
order):

| Frame | Hash | Program |
|---:|---|---|
| 4230 | `7f05ddab771799a9` | `CS_RaytracingResolve_a56bfb9c` |
| 4230 | `a53a7977fe762268` | `CS_IrradianceCache_Shade` |
| 4230 | `be14e72d86362031` | `CS_IrradianceCache_ShadeSecondary` |
| 4232 | `b22a16a178976e1b` | `CS_TransposeVecMatMulAlignedOperation` |
| 4325 | `a929109552ce1e84` | `CS_WaterTransmittanceOpticalDepthProcessing` |

The first three form the light cluster. The transpose utility is bound two
frames later and is required for the visible result in this scene; its exact
role still needs a dispatch/resource capture. The water pass is later and is
not a cell-lighting pass — it should not be described as one.

## Pipeline map

The dump is a translated-container inventory, not proof that every variant is
bound at runtime. It contains 1,354 `.cdxil` containers whose names match the
light/ray/shadow vocabulary, and each has a matching `.dxil`. Many are
material variants.

| Stage | Representative programs seen in the dump | Status |
|---|---|---|
| 0. static/dynamic BVH | static `core_bvh4.rpf`; `XboxBvhBuilder.dll` computes | static data used; dynamic builder off in stable and this test; 49/52 translate |
| 1. ray setup / scheduling | `CS_GenerateRayCoords`, `CS_RayBudgeting_*`, `CS_GenerateRayBins`, `CS_ClearRayBins`, `CS_ScreenProbes_*` | translated in the dump |
| 2. shadow visibility | `CS_LaserLightShadowRaytracing_c3ab3042` (`32ed…`), `CS_TraceShadowRays_Checkerboard_c568be8a` (`559d…`), five `CS_RTDistantShadow*`, `CS_IrradianceCache_ShadowTrace_WithFar` (`f607…`) | translated; these are the actual shadow-trace families in this dump |
| 3. shadow-mask raster / filter | 18 `CS_ShadowRenderTiled*` variants, two `CS_GenerateShadowMasks_*`, `CS_DenoiseShadowMaskLDSPacked`, `CS_ShadowMaskPrunePrescalarizedLightMask`, `CS_ShadowUnifiedClearRaster`, `CS_ShadowRevealTiles*`, `CS_CopyShadowTileCounts` | translated in the dump; the AMD skip list still drops some at runtime |
| 4. resolve / indirect | 356 `CS_RaytracingResolve_*` variants, 27 `CS_IrradianceCache_*` programs (including `Shade`, `ShadeSecondary`, `IntegrateIrradianceSH`, `SpatialFilter`, `LightMixer_SampleIrradianceCache`) | translated; `Shade`/`ShadeSecondary` needed the exact parked-mask fix |
| 5. utility / water | `CS_TransposeVecMatMulAlignedOperation` (`b22a…`), `CS_WaterTransmittanceOpticalDepthProcessing` (`a929…`) | transpose needs half-sum relaxation; water needs permlane support |
| 6. deferred / composite | many `PS_DeferredTextured*`, `PS_ResolveDeferred_*`, `PS_DeferredPedTextured*` | most translate; six pixel programs still fail (below) |
| 7. present / post | title's present and UI passes | stable 29–30 fps menus; not re-audited here |

Notably, **`CS_RTShadowTrace*` names are absent from this dump's `.cdxil`
labels**. Earlier fork documentation names
`CS_RTShadowTrace32HQ_TiledFarOnly` and related programs; their current
translation status was not re-established from this dump. Do not merge them
into the translated list without a separate check.

## Experiment matrix

All runs used the normal AMD skip list, `VICTORY_SHADER_LOOP_LIMIT=256`,
640×360 diagnostic display, and the builder off.

| Run | Tree / commit | Mask / half-sum flags | Five translation | Visible result |
|---|---|---|---|---|
| A | `shadow-mask-trace` `f9bc747` | `1` / `1` | 5/5 | prologue doorway lit; 3.7–4.0 fps; 0 removals; no cell capture |
| B | `shadow-mask-upstream` `fbf18a1` (upstream `90228a7` cherry-picked) | `0` / `0` | 4/5; `b22a…` still fails | prologue face black; 1.8 fps at capture |
| C | `shadow-mask-upstream` `fbf18a1` | `0` / `1` | 5/5 | prologue hair, yard and background prisoners lit; 3.6 fps; 0 removals |
| D | `shadow-mask-upstream` `fbf18a1` | `0` / `1` | 5/5 | cell and cell block: lamps glow, walls/faces/clothing near-black; 3.2–5.2 fps; 0 removals |

Run B isolates the cause: exact masks are not enough. `b22a…` — a generic
matrix utility by name — gates the visible light. Run C is the better
configuration: the mask approximation is retired, and only the half-sum
approximation remains.

Evidence:

- B, black: `logs/shadow-upstream.png`
- C, lit: `logs/shadow-upstream-half-2.png`
- D, cell: `logs/cell-exact-door.png`, `logs/cell-exact-block.png`,
  `logs/cell-exact-room.png`, `logs/cell-exact-corridor.png`; all frames in
  `logs/cell-exact/`
- D log: `logs/victory-20261124-191102.log`
- C log: `logs/victory-20261124-184356.log`
- B log: `logs/victory-20261124-184119.log`
- A log: `logs/victory-20261124-183039.log`
- A's former “cell” images (`logs/shadow-cell-*.png`) are desktop captures,
  the PROLOGUE card, or the doorway shot; none shows the cell.

The C capture is a gameplay angle showing the back of the head and hair, not a
front-facing face. Run D covers the cell: see
[shadow-mask-test.md](shadow-mask-test.md#visual-result).

## Repository updates checked

Fetches were read-only; no local branch was updated except the isolated
worktree branch named above.

| Repository | Local head | Fetched head | Delta | Effect on this work |
|---|---|---:|---:|---|
| `D:\VIctory` fork `gta6` | `1684989` | `2119b0e` | 5 commits | contains the exact lane-mask fix used in runs B/C |
| `D:\VIctory` fork `origin` | `1684989` | `70564ae` | 0 new | stable base unchanged |
| `D:\xcl` | `e50836b` | `20cf130` | 248 commits | per-lane mask/MSAA fixes; not integrated into the fork |
| `D:\ZZ-box\fivestar` | `68b6d06` | `98426b0` | 174 commits | loader/transient-pool and shader-container fixes; no direct irradiance fix |
| `D:\ZZ-box\xbox2windows` | `68969ed8` | `06cdc47d` | 606 commits | separate recompilation work; not on this light path |
| `D:\ZZ-box` | `08814d8` | — | docs only | this report is a local documentation update |

### VIctory `gta6/main`: the important update

Five commits after the stable base:

- `90228a7` — restore parked lane-mask pairs a few instructions apart;
  relative VGPR reads keep parked lanes. It explicitly names
  `CS_IrradianceCache_Shade` / `ShadeSecondary` and
  `CS_RaytracingResolve_a56bfb9c`; it also adds `VICTORY_TRANSLATE_ONLY` and
  `VICTORY_HOST_MAX_WAVE`.
- `9e49b8a` — took that change back out “for now”: its programs translated and
  ran, but the author could not show a lighting gain, it cost about 40 ms GPU
  per frame, and the picture was being rechecked from a known-good tree.
- `2119b0e` — put the change back; the tree is again as before the removal.
- `3930989` — mesh-pipeline test fix on unsupported GPUs.
- `4e17478` — the game is no longer named in the tree.

Run B explains the “no lighting gain” observation: the exact lane-mask fix
translates the resolve and both irradiance shaders, but `b22a…` still fails its
half-sum check, and the prologue remains black. Run C shows the combination
that does light the scene. The upstream commit's ~40 ms/frame cost note is
still relevant: run C measured 3.6 fps, in the same range as run A, but it is
not a performance win.

The worktree branch `shadow-mask-upstream` is local at `fbf18a1` and consists
of the earlier five-program commit plus the upstream `90228a7` cherry-pick. It
has not been merged into stable or pushed.

### Other repositories

- **XCL** (`20cf130`, 248 commits ahead of local): recent work includes an
  AMD MSAA `textureLoad` order fix (`425b869`), per-lane cache/mask handling
  (`bfb8133`, `66879ef`), and direct-DXIL changes. It is a separate runtime and
  was not integrated; the per-lane mask notes are reference material for the
  fork, not a fix applied here.
- **FiveStar** (`98426b0`, 174 commits ahead): driver-compile concurrency,
  transient-pool corruption diagnosis, wave64 exec half-writes, DXBC bounds and
  mesh PSV fixes. None is a direct irradiance-cache fix; the project is a
  reference implementation.
- **Xbox2Windows** (`06cdc47d`, 606 commits ahead): unrelated static
  recompilation and shader/startup fixes.
- No untracked changes were found in those checkouts during the fetch.

## Remaining gaps

- `ceb5eb68cd99cb07` still fails on a descriptor address/format read as data.
- `5dc3b25986622949` and `6f225b641c5b0708` still fail in whole-wave
  simulation.
- Six pixel programs still fail: three on a descriptor read as data
  (`7d0f14ce44746d7e`, `2fd01fca16993001`, `6b6db9f1a526daeb`) and three on
  first-half interpolation (`8445dcb2b63aa197`, `78f3f2fc53a69531`,
  `38bf0814e721a1b3`). They can drop composite/lighting draws.
- The exact-mask + half-sum cell capture (run D) shows no indoor lamp fill or
  bounce; the cause (builder off, skipped resolve variants, the failures
  above) is untested.
- `b22a…` needs a dispatch/resource trace to explain why a transpose utility
  gates the light; the half-sum relaxation is not proven exact for every lane
  state.
- The dynamic BVH builder was off, and the `CS_RTShadowTrace*` family was not
  present in this dump.
- `cargo fmt --check` is unavailable for the pinned GNU toolchain because
  rustfmt is not installed. The build and the 212 shader tests pass.

## Verification

- `victory-shader` on `shadow-mask-upstream`: **212 passed, 2 ignored**;
  `logs/shadow-upstream-tests.log`.
- Release + diagnostics build: success, 35.5 s.
- Run C: **0 device removals**, 3.6 fps after the prologue transition.
- Stable `D:\VIctory`: still at `1684989`, only the opening patch in
  `crates/victory-gpu/src/frame.rs`; its binary timestamp was unchanged at the
  last check.
