# Plan: fixing the lighting and graphics

Written 2026-11-24 from the test copy (`D:\VIctory-pc`, fork `main`
`31714de` plus the Project Kalaga patches) at native 1920×1080. All figures are
from the run logs named below.

## What is actually wrong

The models and textures load. Three separate faults make the picture look
wrong:

1. **No indirect light or lamp light.** The game ray-traces its bounce light,
   lamp light and most shadows in its own compute programs. That output does
   not reach the screen, so anything the sun does not hit directly is
   near-black: faces, clothing, interiors. Lamp fixtures glow but light
   nothing around them (cell capture, [shadow-mask-test.md](shadow-mask-test.md)).
   This is most of what looks like “colours are off”. The warm orange cast in
   the prologue is the game's own sunset grade.
2. **About 8 % of draws are dropped.** In gameplay the runtime draws about
   4,860 calls a frame and drops about 380 that have no host pipeline
   (`logs/victory-20261124-200726.log`). The dropped draws come from:
   - the AMD skip list: 43 programs (41 `CS_RaytracingResolve` variants and 2
     meshlet-culling programs), 2–3 draws each per frame;
   - `b22a16a178976e1b`, the transpose utility that gates the prologue light:
     14–28 draws a frame.
3. **Five programs still do not translate** on the fork's newest code:

   | Hash | Kind | Why |
   |---|---|---|
   | `b22a16a178976e1b` | compute | 16-bit wave sum where not every lane runs |
   | `ceb5eb68cd99cb07` | compute | a descriptor's address or format read as data |
   | `7d0f14ce44746d7e`, `2fd01fca16993001`, `6b6db9f1a526daeb` | pixel (deferred / composite) | a descriptor read only as data |

   The fork's newest `main` already fixed five others that failed at the
   stable base: the three “first-half interpolation” pixel programs and the
   two whole-wave programs (`5dc3…`, `6f22…`).

The dynamic BVH builder (the structure the ray tracing traces against) is
also off. When enabled it crashes the title ([bvh-test.md](bvh-test.md)).

## The plan, in order

Each step is tested the same way: a native run past the prologue, the frame
line (fps, dropped draws, device removals), and before/after captures of the
same shots (doorway, cell block, common room).

Revised 2026-11-25 after the survey in [related-work.md](related-work.md):
someone else already has the lighting rendering correctly with the builder on
(fork issue #543, at about 0.3 fps), so the order below follows that path.

### 1. Take PR #203 — done (partly kept)

PR #203 (`triippywhale:fix/shader-gaps`, saved as
[`patches/0004-pr203-shader-gaps.patch`](../patches/0004-pr203-shader-gaps.patch)
with its author) translates the 16-bit wave sum with lanes gone (`b22a…`),
the descriptor size/format reads (`ceb5…`) and the pixel “descriptor read
only as data” programs. It replaced both the old step 1 (porting the
approximate half-sum switch) and the old step 3. It was tested on an
RX 7900 XT, the same architecture as this card, and is part of the stack that
validates 98.1 % of the retail shader pack (#471).

**Result** (test copy, native, `logs/victory-20261124-211251.log` and the A/B
run after it):

- All five programs translate. The log has no “does not translate” lines at
  all. `victory-shader` tests: 215 passed, 3 ignored.
- Dropped draws fell from about 380 to about 345 per frame. Gameplay is still
  3.8–4.3 fps, with 0 device removals.
- **The compute fixes light the room.** At the cell doorway, the walls beside
  the door are now shaded by the sun instead of black. The area left of the
  door, black before, shows the outside horizon. Whether that is a real
  opening or a wall that no longer draws is not confirmed yet.
- **The three pixel programs light the jacket but corrupt it.** With them on,
  the jacket shows its colours under light, with noisy red/blue patches over
  it. With them skipped, the jacket is dark and clean.
  `logs/pr203-ab.png` is the side-by-side.
- Kept: PR #203 in the binary, with `7d0f14ce44746d7e`, `2fd01fca16993001`
  and `6b6db9f1a526daeb` added to the test config's skip list. Next for these:
  find which of the three makes the patches. The PR's own notes call its
  8-dword case (taking an unused descriptor as a 2D texture) a shortcut.

### 2. Replace the AMD skip list — in progress

The 43 skips work around AMD's shader compiler crashing
(`amdxc64.dll+0x85fd0f`). Fork issue #422 reports that `VICTORY_SHADER_OPT=59`
clears that crash on RDNA4. `59` keeps every clean-up pass except pass 4 (“one
instruction for one value”).

Results on the RX 7600 (test copy with PR #203, native):

| Run | Skip list | `SHADER_OPT` | Crash | Gameplay fps (warm) | GPU ms | Draws/frame | Log |
|---|---|---|---|---|---|---|---|
| reference | 43 AMD + 3 jacket | all passes | none | 3.8–4.3 | 120–160 | ~4,800 | `victory-20261124-211251.log` |
| A | 43 AMD + 3 jacket | 59 | none | 3.8–5.4 | 75–148 | 4,400–5,700 | `victory-20261124-214908.log` |
| B | 3 jacket only | 59 | **none in 10+ min** | 0.9–1.0 | 887 | ~6,800 | `victory-20261124-213256.log` |
| B′ | 3 jacket only | 59, GPU timing on | none | 2.0–2.1 | ~300 | 6,500–7,300 | `victory-20261124-215801.log` |

- `SHADER_OPT=59` costs nothing (A).
- **Without the skip list, AMD's compiler did not crash on this card.** 12 of
  the 43 programs were used in the prologue and all compiled: ten
  `CS_RaytracingResolve` variants and the two meshlet-culling programs
  (`eeed82b877b44b5f`, `fc5e66f8f873d3bb`). The other 31 were not used in
  these scenes.
- **But it is much slower and looks wrong in places.** Draws per frame rise
  from ~4,800 to 6,500–7,300, and gameplay drops to 0.9–2.1 fps. One capture
  of the common room has no ceiling (sky where earlier runs show the ceiling
  and lamps; `logs/step2-opt59-commonroom.png`). The rise in draws points at
  the two culling programs: with them running, more geometry is submitted, and
  some is culled wrongly. The prologue moves on by itself, so B and B′ are in
  different rooms from A. The fps numbers are not like-for-like, but the
  GPU-time gap is far larger than the scenes explain.
- Next: re-enable only the ten resolve variants (culling kept skipped) to
  split the two causes. That run (`logs/step2-resolves-config.toml`) was cut
  short when another session started a game. The list of the twelve is in
  `logs/step2-bound12.txt`.
- **Kept for now:** the full skip list in the test config. Playable speed
  matters more until the culling question is answered.

### 3. Turn the builder on — medium

This card (RDNA3) runs 64-lane waves, so all 53 builder pipelines already get
host pipelines ([bvh-test.md](bvh-test.md)). Earlier the builder crashed the
title without quarantine, and showed no usable light with it. That was before
the light-path programs translated. Now: take the BVH absent-child sort fix
(PR #230 / #414, issue #173), run `VICTORY_BVH_BUILDER=1
VICTORY_BVH_QUARANTINE=1`, and compare against #543's description. Expected:
correct-looking light at well under 1 fps.

### 4. Make the builder affordable — large, open

With the builder on, every builder write invalidates host copies, and the
runtime re-copies 43–87 GB of title memory a frame (#543, #284). That is the
real wall between “lit but 0 fps” and “lit and playable”. Candidates: a
dirty-page mask instead of whole-range refreshes (#284), keeping builder
memory on the GPU instead of round-tripping it (SwavyJayden's fork), parallel
and adaptive copy refresh (Emiriley's fork). Then the crash without quarantine
(empty-box bounds, #16; the `s_round_mode` f16 fix in SaymonMaster14's fork).

### 5. Optional stopgap: shadow fill — small, cosmetic

While steps 2–4 are in progress, a switchable post-process could raise only
the darkest pixels toward a low ambient level, so faces and interiors are
readable. It would not be correct lighting, and it would be off by default.
Global gamma was already ruled out because it washes out the sunlit areas
([graphics.md](graphics.md)).

## What to expect

- Steps 1–2 are days of testing. Step 3 should show correct light, but at a
  frame rate that is not playable.
- Step 4 decides whether lit play is possible. Nobody has solved it yet. It is
  open-ended, and nothing here guarantees it.
- Frame rate (about 4 fps in the world) is a separate wall; see
  [performance.md](performance.md). Restoring the lighting will cost GPU time,
  not save it. Upstream noted about 40 ms a frame for the irradiance
  programs alone.
