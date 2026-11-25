# BVH builder / trace test — 2026-11-24

Question: can the fork's ray-tracing structure builder and trace path restore
indirect light in the prologue without removing the device? **No.** The builder
does run now, but it crashes the title; the quarantine variant survives without
a device removal, restores no usable indirect light, and runs at about one
frame every 5.7 seconds.

The stable checkout and binary were not touched. The test used a detached
worktree at the same source commit.

## Setup

- Copy: `D:\VIctory-bvh`, a `git worktree` of `D:\VIctory` at `1684989`
  plus `patches/0001-opening-60fps-window.patch`; diagnostics release built
  from that worktree.
- Stable: `D:\VIctory` stayed at `1684989` with only the uncommitted
  `crates/victory-gpu/src/frame.rs` opening patch; its 17:24 binary was not
  rebuilt or replaced.
- Launch: `kalaga` with `logs/bvh-config.toml` pointing
  `runtime.victory_dir` at the worktree, the stable graphics settings
  (`gamma=15`, `vSync=2`, FSR off, AF off), `VICTORY_DISPLAY_MODE=640x360`,
  the AMD skip list, `VICTORY_SHADER_LOOP_LIMIT=256`, relay/in-place/wide-back
  settings, and `VICTORY_BVH_BUILDER=1`.
- The test copy was removed after the runs; evidence remains in `logs/`.

## Run 1 — builder enabled

Command environment: `VICTORY_BVH_BUILDER=1`.

The builder was allowed and all of its pipelines were present:

```text
INFO victory_gpu::pipeline: the ray-tracing structure builder runs:
all of its programs have host pipelines pipelines=53
```

There was **no device removal**, but the title died before a lit frame:

```text
victory exited with code 3221225477 (0xC0000005)
hint: access violation inside the title
```

The crash happened at `22:41:11`, seven seconds after the builder line
(`22:41:04`). The window was gone (desktop), so no lighting result exists for
this run.

Evidence: `logs/bvh-run-console.log`, `logs/bvh-1.png`,
`logs/victory-20261124-173924.log`.

## Run 2 — builder quarantined

Command environment: `VICTORY_BVH_BUILDER=1 VICTORY_BVH_QUARANTINE=1`
(the builder's stores are kept out of title memory).

The builder again ran with all 53 host pipelines. The process stayed alive and
had **zero device removals**, but:

- frame time was **5,658.9 ms** (~0 fps), 1,168 draws/frame;
- the captured scene is a blue/over-exposed cutscene with the foreground
  character still black — not the missing bounce/lamp light restored;
- the scene is not usable at that frame rate.

Evidence: `logs/bvh-quarantine-console.log`,
`logs/bvh-quarantine-2.png`, `logs/victory-20261124-174214.log`.

## Conclusion

The builder path is now runnable enough to report its pipeline count, but it
does not produce a usable lit frame:

| Variant | Builder | Device removal | Indirect light | Usable |
|---|---|---|---|---|
| Stable | off | none in the stable run | no | yes, 3.4–4.0 fps |
| `BVH_BUILDER=1` | 53 pipelines | **no** | no frame; title access violation | no |
| `+ BVH_QUARANTINE=1` | 53 pipelines | **no** | not restored; black foreground, blue cast | no, ~0 fps |

This is a title-side crash in the builder path, not a GPU device removal. It
does not justify enabling the builder in `kalaga.toml`. The next useful
step is to isolate which builder pipeline writes the bad data, with
`VICTORY_BVH_QUARANTINE=1` as the safe baseline; the stable build stays as-is
until that is fixed.

The stable settings remain `gamma=15`, `vSync=2`, `fsrQuality=0`,
`anisotropicFiltering=0`.
