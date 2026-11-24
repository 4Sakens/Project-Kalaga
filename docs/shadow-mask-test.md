# Five shadow-mask trace programs — implementation and cell test

Tested 2026-11-24 in an isolated worktree, `D:\VIctory-shadow`, at `1684989`
plus the opening patch. The stable `D:\VIctory` checkout and binary were not
modified.

**Result: the five programs now translate, and they restore partial light in
the cell and prologue — not the missing indirect bounce.** The run had 0 device
removals after the normal AMD skip list was applied.

## The five programs

These were the five compute shaders loaded immediately after `core_bvh4.rpf`
that had no host translation. They are wave32/64 lane-mask and half-sum
programs; earlier logs named only their hashes.

| Hash | Old refusal |
|---|---|
| `7f05ddab771799a9` | lane mask holding lanes elsewhere read as data |
| `a53a7977fe762268` | lane mask holding lanes elsewhere read as data |
| `be14e72d86362031` | lane mask holding lanes elsewhere read as data |
| `b22a16a178976e1b` | 16-bit wave sum where not every lane runs |
| `a929109552ce1e84` | `v_permlanex16_b32` is not supported |

All five have both `.cdxil` and `.dxil` in the shader dump, and none appears in
the run's failed-translation log.

## Implementation

Worktree branch: `shadow-mask-trace`, commit `f9bc747`.

- **`v_permlane16_b32` / `v_permlanex16_b32`** and **`v_cvt_f32_f64`** ported
  from the fork's `ada39e5` translator work.
- **`VICTORY_WAVE_MASK_ELSEWHERE=1`** allows a mask that holds lanes outside
  the current branch to be materialised as the ballot of the lanes that run
  there. This is deliberately approximate for bits belonging to lanes that
  have left the branch.
- **`VICTORY_WAVE_HALF_SUM_ANY=1`** allows the exact 16-bit balanced-tree sum
  where not every lane runs. It relies on the title's `v_cndmask` giving
  inactive lanes zero, so their terms are zero.

Both relaxations are opt-in and are needed for these five programs. They are
not on by default because a program that counts or broadcasts the missing mask
bits will differ from the console.

Launch also needs the normal AMD skip list and loop limit:

```text
VICTORY_SKIP_PIPELINES=<docs/amd-skips.txt joined by commas>
VICTORY_SHADER_LOOP_LIMIT=256
VICTORY_WAVE_MASK_ELSEWHERE=1
VICTORY_WAVE_HALF_SUM_ANY=1
```

## Test result

- Without the AMD skip list, the run translated the five but removed the
  device (`0x887A0006`) before the cell. That was not a shader-translation
  failure in isolation; the skip list was missing from that launch.
- With the skip list and loop limit: **0 device removals**.
- Gameplay after the cutscene: **3.7–4.0 fps**, about 5,000 draws/frame.
  Cutscene frames were 1–2 fps.
- Prologue: Lucia's face and hair are lit, and the background prisoners are
  readable instead of silhouettes. Compare `logs/native-3.png` (stable, face
  black) with `logs/shadow-run3.png` (five programs, face lit).
- Cell cutscene: the bunk, bars and bedding are visible under cool interior
  light. The faces and the uniform's unlit fabric are still dark.
  Evidence: `logs/shadow-cell-4.png`, `logs/shadow-cell-6.png`.
- The builder was **off** for this test. This is the shadow-mask path alone,
  not the BVH builder and not the indirect irradiance cache.

So the answer to "do they restore any light in the cell?" is **yes, some**:
interior geometry and surfaces that were previously black are visible. It is
not a complete fix; the missing indirect bounce and lamp fill still leave
faces and fabric dark.

## Remaining failures outside the five

The same run still drops:

- `ceb5eb68cd99cb07` — a descriptor's address or format read as data;
- `5dc3b25986622949`, `6f225b641c5b0708` — whole-wave section simulation;
- three pixel programs reading a descriptor as data, and three with
  first-half interpolation.

These are not part of the five shadow-mask programs.

## Verification

- `victory-shader` tests: **212 passed, 2 ignored**.
- The worktree build succeeds with release + diagnostics.
- `cargo fmt --check` could not run: rustfmt is not installed for the pinned
  GNU toolchain. The changed code follows the surrounding formatting.
- Stable `D:\VIctory` remains at `1684989` with only the opening-patch change
  in `crates/victory-gpu/src/frame.rs`; its binary timestamp is unchanged.

Evidence logs: `logs/victory-20261124-182440.log`,
`logs/shadow-run3-console.log`, `logs/shaders-shadow2/`.
