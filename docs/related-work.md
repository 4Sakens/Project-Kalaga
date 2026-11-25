# Related work: who else has the lighting working (2026-11-24/25)

A survey of the projects doing the same thing, to see whether anyone has the
ray-traced lighting (the black shadows) working. All read-only through the
GitHub API. Fork comparisons are against `fxceless/victory-fork` `main`
(formerly `victory-gta6`).

## Answer

**Nobody has it working at a usable speed.** The closest report is
fxceless/victory-fork#543. On an RX 9070 XT (RDNA4) with the structure builder
on (`VICTORY_BVH_BUILDER=1 VICTORY_BVH_QUARANTINE=1`), the tester describes
“the correct-looking picture”: a lit interior with sunlight falling off into
the room, readable materials and reflections, the yard populated. It ran at
**0 fps (2.9–3.8 s per frame)**. With the builder on, the runtime keeps
re-copying title memory: 43–87 GB of refreshes per frame. Builder off, the same
scene is flat. Every other report (RTX 3060–5080, RX 6800/7600/7800/9070) shows
the same black shadows we see. Issue #512 explains it the same way we did:
missing light, not missing textures.

So the lighting path is known to work once the builder runs. What is unsolved
is the cost of the memory refresh it triggers.

## Where the projects stand

| Project | State relevant to lighting |
|---|---|
| `fxceless/victory-fork` (2,043 stars, 495 forks) | Builder off by default. 60+ open PRs, mostly from testers. Main is `31714de` (our test copy). |
| `Marvisak/VIctory` (upstream, 11,437 stars) | Generic runtime. Open work on BVH instruction emulation (#1533 “emulate image_bvh as miss”, #1794 a16 rays / unsorted nodes, #1883 traversal lane masks). Nothing GTA-lighting specific is working. |
| `ivall/xcl` (7,877 stars) | No BVH or ray-tracing issues found; not on this path. |
| FiveStar, Xbox2Windows | Separate implementations (see [upstream-review.md](upstream-review.md)); no ray-traced lighting. |

## The builder on other cards

- **RDNA4 / RDNA3 (64-lane capable):** all 53 builder pipelines get host
  pipelines with no change (#543, #16 comment on RX 9070 XT). This machine's
  RX 7600 also ran all 53 ([bvh-test.md](bvh-test.md)).
- **NVIDIA (32-lane):** three prefix-sum passes refused. Fixed by
  `VICTORY_FIRSTLANE_OWN` (now in fork `main`) or by PR #497's exact form.
- **The crash with the builder on, without quarantine:** reported on RTX 5070,
  3080 Ti, 5080 and RX 9070 XT (#16), 7–14 s after the builder starts. One
  comment traces it to f32 empty-box bounds the builder never fills in. That
  matches this machine's earlier crash.

## Patches worth taking, by gap

| Our gap | Patch | Status |
|---|---|---|
| `b22a…` 16-bit wave sum, `ceb5…`, 3 pixel “descriptor read only as data” | PR #203 (`triippywhale:fix/shader-gaps`, `0e49a91`), tested on an RX 7900 XT. Part of the five-PR stack in #471 that validates 98.1 % of the retail shader pack with no regressions | **Applied to the test copy** (step 1) |
| Video frames out of order (loading montage) | PR #509 (hot textures hashed every check) and PR #555 (guard the aliasing views themselves). Same cause as our `0003-video-texture-order.patch`; #555 is the more complete fix | Ours applied; #555 to evaluate |
| BVH traversal sorting an absent child before a real hit | PR #230 / #414 / issue #173 (in tdogghockey's and SwavyJayden's forks) | Needed once the builder runs |
| Builder's f16 box bounds rounding | `s_round_mode` for `v_cvt_f16_f32` (SaymonMaster14's fork, with PR #156) | Candidate for the builder crash |
| Builder memory refresh (43–87 GB/frame) | #284 (dirty-page mask), Emiriley's fork (parallel copy refresh), SwavyJayden's “only the builder names memory by constants” | The real wall; open |
| AMD shader-compiler crash (`amdxc64.dll+0x85fd0f`) | #422: `VICTORY_SHADER_OPT=59` clears it on RDNA4 | Candidate replacement for the 43-entry AMD skip list (step 2) |

## Forks with the most extra work

By commits ahead of fork `main` on their default branch:
danielzhang122 (316, mostly tooling/policy), SaymonMaster14 (160: shadow-ray
traces and the whole builder on 32-lane GPUs, staging waits, table CBVs),
SwavyJayden (88: builder memory naming, BVH sort fix, texture refresh without
remap waits), Emiriley (75: parallel and adaptive copy refresh), triippywhale
(38: the AMD view-heap clamp already in main, and PR #203), tdogghockey (35:
BVH absent-child ordering in DXIL).
