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

### 1. Bring back the transpose program — small

Port the opt-in 16-bit half-sum switch (`VICTORY_WAVE_HALF_SUM_ANY=1`) from
the experimental branch (`shadow-mask-trace` `f9bc747`) to the test copy. It is
not in the fork's `main`. The fork's `main` already has the exact lane-mask fix
and the permlane lowering from that branch. This makes all five light-path
programs translate and returns 14–28 draws a frame. On the experimental tree
that combination lit the prologue hair, yard and prisoners with 0 removals
(run C). Expected effect indoors: small. The cell stayed dark in run D.

### 2. Re-test the AMD skip list on this card — medium

The 43 skips come from an RX 9060 XT / 9070 XT report against an older
translator, where those programs crashed AMD's shader compiler. They have not
been re-tested on the RX 7600 with the current translator. Un-skip them in
halves, then quarters, to find which still crash. Every
`CS_RaytracingResolve` variant brought back is part of how the traced light
is composited onto the screen. This is the step most likely to give a visible
indoor change. Risk: a bad one hangs or removes the GPU, so each group gets
its own run with saves copied.

### 3. Translate “descriptor read as data” — medium to large

Teach the shader translator the case where a program reads a texture or
buffer descriptor's raw words: its address, format or size. This covers the
three deferred pixel programs and `ceb5…`. Missing deferred programs mean
missing or flat-coloured surfaces in the composite. Check XCL and upstream
VIctory for an existing implementation before writing one; XCL has recent
descriptor and per-lane work.

### 4. Make the BVH builder run — large

Without a dynamic BVH, moving objects and characters are not in the
structures the light is traced against. The builder needs its last refused
pipelines (programs that still ask for 64-lane waves on this 32-lane GPU) to
run. Then it can be enabled without quarantine and checked for the earlier
crash (bad bounds written into title memory). This is the largest and least
certain step.

### 5. Optional stopgap: shadow fill — small, cosmetic

While steps 2–4 are in progress, a switchable post-process could raise only
the darkest pixels toward a low ambient level, so faces and interiors are
readable. It would not be correct lighting, and it would be off by default.
Global gamma was already ruled out because it washes out the sunlit areas
([graphics.md](graphics.md)).

## What to expect

- Steps 1–2 are days of testing and can show a difference indoors.
- Step 3 is translator work: days to a couple of weeks.
- Step 4 decides whether full ray-traced lighting works. It is open-ended,
  and nothing here guarantees it.
- Frame rate (about 4 fps in the world) is a separate wall; see
  [performance.md](performance.md). Restoring the lighting will cost GPU time,
  not save it. Upstream noted about 40 ms a frame for the irradiance
  programs alone.
