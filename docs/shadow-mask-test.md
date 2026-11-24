# Five light-path programs — implementation, exactness and cell test

Tested 2026-11-24 in an isolated worktree, `D:\VIctory-shadow`, at `1684989`
plus the opening patch and an upstream cherry-pick. The stable `D:\VIctory`
checkout and binary were not modified.

**Result: all five now translate, and they restore light in the prologue and
partial light in the cell — not the complete missing indirect bounce.** The
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
| A | `f9bc747` | `1` / `1` | 5/5 | partial cell light; prologue face lit; 3.7–4.0 fps; 0 removals |
| B | `fbf18a1` | `0` / `0` | 4/5; `b22a…` fails | prologue face black; 1.8 fps at capture |
| C | `fbf18a1` | `0` / `1` | 5/5 | prologue hair, yard and background prisoners lit; 3.6 fps; 0 removals |

Run B isolates the dependency: exact masks alone are not enough. The transpose
program must translate for the prologue to light. Run C is the better
configuration, because it retires the mask approximation and keeps only the
half-sum approximation.

## Visual result

- A, cell cutscene: the bunk, bars and bedding are visible under cool interior
  light; faces and unlit uniform fabric remain dark. Evidence:
  `logs/shadow-cell-4.png`, `logs/shadow-cell-6.png`.
- B: prologue face is black, matching stable. Evidence:
  `logs/shadow-upstream.png`.
- C: gameplay angle shows the back of the head with lit hair, a lit yard and
  readable background prisoners. The capture does **not** show a front-facing
  face, and the cell was not re-captured with the exact-mask combination.
  Evidence: `logs/shadow-upstream-half-2.png`.

So the answer to “do they restore any light in the cell?” is still **yes,
some** from run A: interior geometry is visible. The exact-mask run C proves
the prologue light path more cleanly but does not replace the cell evidence.
Full indirect bounce and lamp fill are still missing; the builder was off.

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

Evidence logs: `logs/victory-20261124-182440.log`,
`logs/victory-20261124-184119.log`, `logs/victory-20261124-184356.log`,
`logs/shadow-run3-console.log`, `logs/shaders-upstream-half/`.
