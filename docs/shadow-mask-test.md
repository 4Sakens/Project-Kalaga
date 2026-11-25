# Five light-path programs — implementation, exactness and cell test

Tested 2026-11-24 in an isolated worktree, `D:\VIctory-shadow`, at `1684989`
plus the opening patch and an upstream cherry-pick. The stable `D:\VIctory`
checkout and binary were not modified.

**Result: all five now translate and the prologue's sunlit surfaces are lit,
but the cell and cell block stay essentially unlit: lamp fixtures glow, while
walls, faces and clothing remain near-black (run D). The missing indirect
bounce and lamp fill are not restored.** The
label “shadow-mask trace” was a working name. The `.cdxil` containers show
that the five are a raytracing resolve, two irradiance-cache shade programs, a
matrix transpose utility, and water optical-depth processing.

## The five programs

| Hash | `.cdxil` name | Old refusal |
|---|---|---|
| `7f05ddab771799a9` | `CS_RaytracingResolve_a56bfb9c_Wrapped` | lane mask holding lanes elsewhere read as data |
| `a53a7977fe762268` | `CS_IrradianceCache_Shade_823aad37_Wrapped` | lane mask holding lanes elsewhere read as data |
| `be14e72d86362031` | `CS_IrradianceCache_ShadeSecondary_185f8341_Wrapped` | lane mask holding lanes elsewhere read as data |
| `b22a16a178976e1b` | `CS_TransposeVecMatMulAlignedOperation_81003b08_Wrapped` | 16-bit wave sum where not every lane runs |
| `a929109552ce1e84` | `CS_WaterTransmittanceOpticalDepthProcessing_44443e79_Wrapped` | `v_permlanex16_b32` is not supported |

The two irradiance-cache shaders are the indirect-light passes. The resolve
composites traced results. The water pass is not a cell-lighting pass. The
transpose utility is not a light pass by name, but its failure gates the
visible result in this scene; its exact role still needs a dispatch/resource
capture.

## Implementation and upstream update

Worktree history:

- `f9bc747` on branch `shadow-mask-trace`: the permlane and half-sum work.
- `fbf18a1` on branch `shadow-mask-upstream`: the same five-program commit plus
  upstream `90228a7`, “restore parked lane-mask pairs a few instructions apart;
  relative VGPR reads keep parked lanes”.

Changes:

- **`v_permlane16_b32` / `v_permlanex16_b32`** and **`v_cvt_f32_f64`** ported
  from the fork's `ada39e5` translator work. This makes the water program
  translate.
- **Upstream `90228a7`** restores the parked lane-mask pair exactly. It makes
  the resolve and both irradiance-cache shaders translate without an
  approximation. It is the preferred fix for those three.
- **`VICTORY_WAVE_MASK_ELSEWHERE=1`** was the earlier approximate fallback for
  the lane masks. It is no longer needed for these programs once `90228a7` is
  present, and the new run leaves it off.
- **`VICTORY_WAVE_HALF_SUM_ANY=1`** allows the exact 16-bit balanced-tree sum
  where not every lane runs. It relies on the title's `v_cndmask` giving
  inactive lanes zero. The transpose program still needs this switch; without
  it the prologue remains black.

Launch also needs the normal AMD skip list and loop limit:

```text
VICTORY_SKIP_PIPELINES=<docs/amd-skips.txt joined by commas>
VICTORY_SHADER_LOOP_LIMIT=256
VICTORY_WAVE_MASK_ELSEWHERE=0
VICTORY_WAVE_HALF_SUM_ANY=1
```

## Test matrix

All runs used the AMD skip list, loop limit 256, 640×360 diagnostic display,
and the BVH builder off.

| Run | Tree | Mask / half-sum | Five | Result |
|---|---|---|---|---|
| A | `f9bc747` | `1` / `1` | 5/5 | prologue doorway lit; 3.7–4.0 fps; 0 removals; **no cell capture** (see below) |
| B | `fbf18a1` | `0` / `0` | 4/5; `b22a…` fails | prologue face black; 1.8 fps at capture |
| C | `fbf18a1` | `0` / `1` | 5/5 | prologue hair, yard and background prisoners lit; 3.6 fps; 0 removals |
| D | `fbf18a1` | `0` / `1` | 5/5 | cell and cell block captured: sunlit hair and windows lit, lamps glow, walls/faces/clothing near-black; 3.2–5.2 fps; 0 removals |

Run B isolates the dependency: exact masks alone are not enough. The transpose
program must translate for the prologue to light. Run C is the better
configuration, because it retires the mask approximation and keeps only the
half-sum approximation.

## Visual result

- A: **correction.** The files earlier cited as A's cell evidence do not show
  the cell. `shadow-cell-1/2/4/5.png` are captures of the bare desktop (the
  game window was not in front), `shadow-cell-6.png` is the white “PROLOGUE”
  title card, and `shadow-cell-3/7.png` are the prologue doorway shot. The
  “bunk, bars and bedding visible” description is not supported by any saved
  image, so run A provides no cell evidence.
- B: prologue face is black, matching stable. Evidence:
  `logs/shadow-upstream.png`.
- C: gameplay angle shows the back of the head with lit hair, a lit yard and
  readable background prisoners. The capture does **not** show a front-facing
  face. Evidence: `logs/shadow-upstream-half-2.png`.
- D (2026-11-24 19:11, same binary and flags as C, plus a copied data
  directory): the window was captured every ~5 s for 7.5 min with a
  window-rectangle grab. The run went through the opening cutscene and the
  PROLOGUE card into gameplay. The player character then walked from the cell
  through the cell block toward the yard. The capture script sent no input.
  - Cell, looking out of the door: the yard beyond is sunlit; the cell interior
    and the character's back are dark except for sun-rim on the hair.
    `logs/cell-exact-door.png`.
  - Cell block under ceiling lamps: the lamp panels are bright and the hair
    catches the window light, but the walls, floor, bunks and clothing next to
    the lamps are near-black brown. The lamps light nothing around them.
    `logs/cell-exact-block.png`.
  - Common room: two inmates are silhouettes against a sunlit window; faces
    and clothing are black. `logs/cell-exact-room.png`.
  - Corridor to the yard: sky-lit fog and geometry readable, figures
    silhouetted. `logs/cell-exact-corridor.png`.

So the answer to “do they restore light in the cell?” is **no, not
measurably.** Sun-facing surfaces and windows are lit, as in stable, but
there is no visible lamp fill or indirect bounce indoors, and faces stay
black. Run C/D's gain is confined to sunlit exteriors and rim light. The
cause is not established. Candidates, none tested here: the dynamic BVH
builder was off; the AMD skip list still drops 41 `CS_RaytracingResolve`
variants; and the remaining failures below can drop composite draws. Further
work on these five programs alone is unlikely to light the cell.

## Remaining failures outside the five

- `ceb5eb68cd99cb07` — a descriptor's address or format read as data;
- `5dc3b25986622949`, `6f225b641c5b0708` — whole-wave section simulation;
- three pixel programs reading a descriptor as data, and three with first-half
  interpolation.

These are not part of the five light-path programs.

## Verification

- `victory-shader` on `shadow-mask-upstream`: **212 passed, 2 ignored**
  (`logs/shadow-upstream-tests.log`).
- Release + diagnostics build succeeds (35.5 s).
- Run C has **0 device removals**; gameplay was 3.6 fps after the prologue
  transition.
- `cargo fmt --check` could not run: rustfmt is not installed for the pinned
  GNU toolchain. The changed code follows the surrounding formatting.
- Stable `D:\VIctory` remains at `1684989` with only the opening-patch change
  in `crates/victory-gpu/src/frame.rs`; its binary timestamp is unchanged.

- Run D: all five hashes `first bind` + `translated`; **0 device removals**;
  gameplay 3.2–5.2 fps (mostly 3.5–4.0); stable `settings.xml` hash unchanged
  because the run used `VICTORY_DATA_DIR=logs/cell-exact-data`.

Evidence logs: `logs/victory-20261124-182440.log`,
`logs/victory-20261124-184119.log`, `logs/victory-20261124-184356.log`,
`logs/victory-20261124-191102.log` (run D), `logs/cell-exact-config.toml`,
`logs/cell-exact/` (67 frames), `logs/shadow-run3-console.log`,
`logs/shaders-upstream-half/`.
