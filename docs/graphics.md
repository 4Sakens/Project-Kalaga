# Black uniforms, faces and shadowed surfaces

Measured 2026-11-24 on the RX 7600 with the fork at `1684989` plus the opening
patch. This is the investigation behind the “black jumpsuits / colours not
loading” report.

## What is actually black

The meshes and their textures are present. In the cell, the uniform's printed
panel is visible while the rest of the fabric, faces and hair are crushed to
black. Turning the translator's deep-skips form off for every program
(`VICTORY_WAVE_DEEP_SKIPS=0`) did **not** bring the cell's light back; it only
changed which surfaces drew. That rules out a blanket missing-texture or
missing-mesh explanation.

The fork's own status is explicit: its ray-traced bounce light and its
ray-traced sun/lamp shadows do not run yet, so anything the direct sun does not
hit is black. The mechanism is documented in `D:\VIctory\docs\fork-ray-tracing.md`:

- the title's indirect light (probes, bounce, reflections) and shadows are
  traversed by the title's own compute programs over title-built BVHs;
- the builder and trace programs only partly translate, and the builder stays
  off because some of its pipelines are refused;
- without the trace output the lighting composite has no fill term.

This is a lighting-path gap, not a mesh format or texture-upload bug.

## What was tried

### Deep-skips form, globally and per program

Fork issue #62 reports that on a 32-lane GPU a family of 14
`CS_ShadowRenderTiled*` programs loses cell lighting and uniform colour in the
deep-skips form, and that excluding the family restores the uniform's colour
and print on an RTX 4080. That is close to this symptom, so I:

1. ran the existing global switch (`VICTORY_WAVE_DEEP_SKIPS=0`) and captured the
   cell — the room stayed unlit, so this was not sufficient;
2. ported the per-program `VICTORY_WAVE_DEEP_SKIPS_NOT` / `_ONLY` switch from
   VIcky commit `e27b969` (GPL-3.0), added five parser/decision tests, and
   applied the 14 hashes from #62;
3. built it and ran at native resolution. The shader tests passed, but the
   device was removed (`0x887A0005`) before the scene settled, so the change was
   reverted. `main` is clean at `1684989` plus the opening patch.

The switch is not retained: it is an unmerged workaround, and on this run it
was not stable enough to keep. It remains a candidate for a future A/B on a
clean save, split from the instruction changes in #134.

### Brightness / gamma

The title's brightness setting (`gamma` in `settings.xml`, default 15) changes
how much of the dark range survives:

| gamma | Result |
|---|---|
| 15 (default) | cell faces, uniforms and hair crushed to black; yard exposure acceptable |
| 18 | cell still almost black |
| 21 | still crushed; that run also hit the intermittent device removal |
| 25 | faces, hair, badge and navy fabric visible; the sunlit yard clips to white |

No single global gamma gives both a readable interior and an unclipped
exterior. The stable default **15** was restored. Raising brightness to 20–25
in the game's settings is the only user-side workaround, at the cost of
blowing out the sunlit yard.

## What would fix it

1. **Run the title's light path**: finish the BVH builder and the remaining
   trace/shadow programs so the composite receives bounce and lamp light
   (`docs/fork-ray-tracing.md`). This is the real fix; it is a substantial
   feature, not a texture tweak.
2. **Or add a deliberate ambient fallback** in the host's lighting path: a
   small constant fill for surfaces with no traced light, plus a shadow-lift
   tone curve that leaves highlights alone. That needs a post-process pass or a
   translated-shader hook and was not attempted here; a global gamma is not a
   substitute.
3. Upstream VIctory's page-table/heap work (see `upstream-review.md`) may make
   the builder runnable, but merging it into the fork is the 36-file/274-hunk
   problem documented in fork issue #126.

## Evidence

- `logs/native-3.png` — sunlit prologue, original gamma: rim light only,
  uniform nearly black.
- `logs/deepskips-2.png` — cell with deep-skips off: printed panel visible,
  room still unlit.
- `logs/gamma-2.png` — gamma 25 close-up: face, hair, badge and fabric colour
  recovered.
- `logs/gamma-3.png` — gamma 25 yard: clipped to white.
- `logs/gamma18-2.png` — gamma 18 cell: still black.
- `logs/shadow-not-2.png` — native run of the per-program switch: desktop after
  the device removal.

## Quality profile that did help

A separate texture-quality change was successful and is now active:
`anisotropicFiltering=16`, `texLodScale_Mat_High=1.0`,
`texLodScale_Mat_Med=1.0`, `lodScale=0.8`, `gamma=15`, `vSync=2`, FSR off, and
`VICTORY_INPLACE_MB=4096` at native 1920×1080. It measured **4.0–4.1 fps** with
0 device removals (the low-quality native baseline was 3.9 fps). Hair, faces
and the uniform's printed panel are visibly sharper.

It does not fill the missing light; shadowed fabric and faces remain black.
The stable graphics settings are therefore `vSync=2`, `fsrQuality=0`,
`anisotropicFiltering=16`, `gamma=15`; backups are
`logs/settings-before-60.xml`, `logs/settings-quality-base.xml` and
`logs/settings-before-gamma.xml`.
