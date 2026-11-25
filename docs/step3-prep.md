# Step 3 prep: builder patches on a new worktree (2026-11-24)

Code, build and unit-test work only. The game was not launched. `D:\VIctory`,
`D:\VIctory-pc` and the running `victory.exe` were not touched. Nothing was
pushed.

## Worktree

- Path: `D:\VIctory-step3`, made with `git worktree` from the `D:\VIctory` repository.
- Branch: `step3-builder`, cut from `pc-input` (0c84e3f). Head is now `dc979e4`.
- Target dir: `D:\VIctory-step3\target` (the worktree's own).

## Baseline (pc-input, before any change)

| Crate | Result |
|---|---|
| victory-shader | 215 passed, 0 failed, 3 ignored (matches the expected baseline) |
| victory-gpu | 113 passed, 0 failed, 1 ignored |

victory-gpu failed once, on the very first run (`test failed, to rerun pass -p victory-gpu --lib`).
The output didn't name the test. The next four runs of the same unchanged tree
all passed. Something else was using the GPU at the time (the other session),
so this looks like a flaky test, not a real failure. It never came back after
the patches.

## Candidates

### 1. BVH traversal: an absent child can sort before a real hit (#173). APPLIED

All three PRs (#230 space-de, #414 AndradeTK, #217 Flyander) make the same
code change. In `bvh::boxes` (the CPU reference) the hit test now also
requires `children[n] != NONE`. In the DXIL emitter (`emit/intersect.rs`)
`child <u NONE` is ANDed into the hit mask. The base did not have it.

| Source | Author | What was taken | Conflicts |
|---|---|---|---|
| `11f80604ad` (PR #414, AndradeTK/victory-fork `fix/bvh-sorted-absent-child`) | devan (AndradeTK) | Whole commit: the code fix plus the CPU regression test `sorted_boxes_put_absent_children_after_real_hits` | none |
| `f44603055d` (PR #217, Flyander/victory-fork `fix/bvh-ignore-missing-children`) | Flyander | Only its GPU test `absent_child_sorted_box_gpu_matches_reference` (`emit/intersect_tests.rs`) | bvh.rs and intersect.rs conflicted on the same lines; resolved by keeping #414's identical code |

PR #230's fork (space-de) no longer exists ("Repository not found"). Its code
is the same anyway.

Tests: victory-shader 217 passed / 3 ignored. The GPU test ran on the RX 7600
and on WARP, and both gave `[8, NONE, NONE, NONE]`.

### 2. `s_round_mode` sets the rounding of `v_cvt_f16_f32`. APPLIED (round-mode part only)

- Source: `5f99cc0eeb` in `SaymonMaster14/victory-fork` `main`, author Davi Andrei.
- What it does: a new `round16` field in the lowerer follows the last
  `s_round_mode` (MODE bits 3:2). `f16_directed()` rounds f32 to f16 toward
  +inf, toward -inf or toward zero, using the existing `f16_toward_zero`.
  Both `v_cvt_f16_f32` lowering sites use it when the mode is not
  round-to-nearest. With the default mode, behaviour is unchanged.
- Conflicts: `git cherry-pick` applied without a reported conflict, but it
  also brought along that commit's removal of "the duplicate v_cvt_f32_f64".
  That removal deleted `f64_pair` and `f64_to_f32_bits`, which this tree's
  only `v_cvt_f32_f64` lowering still uses. I threw the automatic result away
  and applied the round-mode hunks by hand, keeping our `v_cvt_f32_f64`. The
  new test `s_round_mode_rounds_a_16_bit_conversion_outward` was taken as is.
- Tests: victory-shader 218 passed / 3 ignored. The new test ran on the card
  (no "not run" skip message).
- Limit, as the upstream comment says: the mode is followed in lowering order,
  as if the code were straight-line. Other f16 narrowing paths (packed and
  interpolation conversions) still ignore the mode, as upstream does.

### 3. "Only the structure builder names memory by constants and writes by address". APPLIED, needs a decision

- Source: `4c378b099d` in `SwavyJayden/victory-fork` `main` (part of fxceless PR #294), author ALFREDOHDEZ.
- Size: `crates/victory-gpu/src/draw.rs`, +9 -1. Cherry-picked cleanly.
- What it does: in `State::memory_ready`, root constants are scanned for title
  addresses only when the pipeline is a structure-builder pipeline, and
  `writes` (copy the numbered copies back to title memory after the dispatch)
  is forced off for every other pipeline. The goal is to stop the traversal
  programs from declaring every copy written. That leaked the quarantined
  builder's results back into title memory and cost a compare of every copy.
- Tests: victory-gpu 113 passed / 1 ignored (run twice). No victory-shader
  change.
- Risk: any non-builder shader that uses title memory by raw address
  (`SLOT_MEMORY`, meaning any global/flat access, not only BVH walks) now
  loses its address stores, which are no longer copied back. It also no
  longer has memory named by its root constants made ready before the
  dispatch, so the first frame faults and the page is ready from the next
  frame. If the A/B run shows new breakage outside ray tracing, revert this
  commit first (`git revert dc979e4`, the top commit).

### 4. Builder memory-refresh cost. NOT APPLIED (report only)

- `Emiriley/victory-fork` `05ee438706` "GPU: parallelize copy refreshes on
  multicore hosts" (spacede, `host.rs` +32 -2) only changes the default of
  the existing `VICTORY_WIDE_REFRESH` switch. It turns parallel copy refreshes
  on when there are 4 or more logical CPUs, with `=0` to disable. It adds a
  small unit test. `5a32c08c29` is the README text for it. This tree already
  has the switch (off by default), so **`VICTORY_WIDE_REFRESH=1` at launch
  gives the same behaviour** without the patch. Also, `git apply --check`
  fails on its last hunk, a stray trailing newline at the end of `host.rs`.
- Issue #284 / PR #346 (Gargalindis, open): "stores through title memory by
  address mark their copy, and only marked copies are taken for written".
  2 commits (`c3db707754` and a card test `ac3615585c`), +368 -38 across
  `victory-gpu/src/memory.rs` and 6 victory-shader emit files (`host.rs`,
  `intersect.rs`, `lower.rs`, `memory_tests.rs`, `mod.rs`, `shader.rs`). This
  is the real fix for the 43-87 GB/frame write-back. It also covers what
  candidate 3 does crudely, and it would conflict with candidate 3 in
  intent. Not attempted: too large for this step.

## Final commits on `step3-builder`

`git log --oneline pc-input..step3-builder`:

```
dc979e4 GPU: only the structure builder names memory by constants and writes by address
076a1e3 Shaders: s_round_mode sets the rounding of v_cvt_f16_f32 (toward +inf, -inf, zero), for the ray-tracing builders' conservative f16 box bounds
27cb231 Shader tests: a sorted BVH node with an absent child, on the card (test of #217)
9c91da7 Fix BVH sorted box hits: absent child can sort before a real hit (#173)
```

Each commit keeps its upstream author and has a `(cherry picked from ...)` line.

## Tests vs baseline

| Crate | Baseline | step3-builder | Change |
|---|---|---|---|
| victory-shader | 215 / 0 failed / 3 ignored | 218 / 0 failed / 3 ignored | +3 new tests (CPU BVH, GPU BVH, round mode), no regressions |
| victory-gpu | 113 / 0 failed / 1 ignored | 113 / 0 failed / 1 ignored | none |

## Binary

`D:\VIctory-step3\target\x86_64-pc-windows-gnu\release\victory.exe`:
release profile plus `diagnostics`, built 2026-11-24 21:52:04 (-05:00),
62,274,186 bytes, at commit `dc979e4`. Built with no warnings.

## Launch switches to try next

Run it the same way as the earlier BVH test: a kalaga config whose
`runtime.victory_dir` points at `D:\VIctory-step3`, with the stable
graphics/skip settings. Only one game instance can use the GPU at a time.

| Run | Environment added | What to look for |
|---|---|---|
| A | `VICTORY_BVH_BUILDER=1` | Does the access violation 7-14 s after the builder starts still happen? The round-mode patch targets the f16 box bounds of #16. |
| B | `VICTORY_BVH_BUILDER=1 VICTORY_BVH_QUARANTINE=1` | Is the lit picture correct, as in #543? What is the frame time vs the earlier 5.7 s? |
| A' / B' | add `VICTORY_WIDE_REFRESH=1` | Do the "copies" ms in the frame line go down? |

For each run, check the log for the line "the ray-tracing structure builder
runs: all of its programs have host pipelines pipelines=53".

## Needs a human decision

1. Candidate 3 changes how every non-builder shader that uses memory by
   address behaves, not only the BVH walk. Keep it for the A/B runs, or drop
   it (`git revert dc979e4`) if anything outside ray tracing regresses.
2. Whether to pursue PR #346 (dirty-copy marking) as the real step 4 fix
   for the memory refresh wall. It overlaps with candidate 3.
3. The single unexplained victory-gpu failure in the first baseline run. It
   didn't come back in 6 later runs.
