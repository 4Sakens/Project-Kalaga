# PC controls, loading pacing and frame-rate settings (test copy)

Tested 2026-11-24 in a separate worktree, `D:\VIctory-pc` (branch `pc-input`),
built from the fork's latest `main` (`31714de`, see below) plus the opening
patch and the mouse-look change. The stable `D:\VIctory` checkout, binary,
settings and saves were not modified. Every test run used a copied data
directory (`VICTORY_DATA_DIR=logs/pc-data`).

## Results

| Request | What was done | Result |
|---|---|---|
| Loading screen “rubber-bandy / glitchy” | Found the real cause: video frames shown out of order. Fixed in the texture refresh (below). Also dropped the 60 fps opening override | Loading montage: **0 % frames out of order (was 34 %)**, steady 29.6–30 fps up to the Jason/Lucia art |
| Low FPS | Added the measured performance switches to the launch config | Prologue gameplay **3.7–4.5 fps native 1920×1080** (was 2.2–2.4 with the stable launch config), 0 device removals |
| Colours / meshes / graphics | Not changed | Same cause as before: the ray-traced indirect light does not run, so shadowed areas are black. See [shadow-mask-test.md](shadow-mask-test.md) |
| Mouse camera | New mouse-look in the input layer | Works: scripted mouse movement turned the prologue camera |
| PC button prompts | Investigated only | No built-in PC prompt mode found; see below |

## Loading montage shown out of order (fixed)

The painted montage before the Jason/Lucia art (eagle, oranges, jungle,
flamingos, “My Freedom”) and the Jason/Lucia art itself are videos. The title
decodes them into a ring of textures: a 3840×2160 plane (8.3 MB) and two
1920×1152 planes (2.2 MB) per frame, three frames deep, so 9 textures.

**Cause.** These textures sit in view memory. The runtime watches them with a
guard that only notices CPU writes it can trap directly. Anything else is
found by a whole-texture hash, which runs only every 8th frame per texture.
The video decoder's writes get past the guard, so each ring slot was
refreshed at most every 8th frame. The screen kept showing a slot's old
picture: the montage jumped back in time in **34 %** of its changing frames
(`logs/load-rec/`, 21 grabs/s; for example 17.14–17.48 s alternates
jungle → oranges close-up → oranges wide → jungle).

**Fix** (`patches/0003-video-texture-order.patch`,
`crates/victory-gpu/src/texture.rs`):

1. When the periodic hash finds a change the guard did not see, that texture
   is marked “unguarded” and checked at every refresh.
2. For marked textures, a 16 KB fingerprint (1,024 slices spread across the
   texture) is compared first. The whole hash runs only when the fingerprint
   changed, or on the texture's every-8th-frame turn. This keeps the cost of
   checking 9 × 4K planes per frame down.
3. After 90 checks with no change (~3 s), a texture goes back to the cheap
   guard.

The log lists each marked texture
(`texture written past the guard: hashed at every check`). In every run so
far it was exactly these 9 video textures.

| Run | Build | Out-of-order frames in the montage | Loading fps (5 s windows) |
|---|---|---|---|
| `load-rec` | before | **66 / 197 (34 %)** | 30 |
| `load-rec-g0` | before, `VICTORY_TEXTURE_GUARD=0` (hash everything) | 0 / 182 | 26–30 |
| `load-rec-fix` | marked textures hashed whole every frame | 0 / 119 | 11–30 (texture time 15–50 ms) |
| `load-rec-fix5` | final, warm pipeline cache | **0 / 181** | **29.6–30** (texture time ≤ 5 ms) |

The first launch after rebuilding the runtime recompiles about 1,900 host
pipelines in the background (`being made` in the frame line). That launch's
loading phase dips to 17–28 fps. From the second launch on, the pipelines
come from the cache.

Gameplay with the fix: 3.6–4.1 fps native, 0 device removals, the same as
without it. Tests: a new fingerprint test; `victory-gpu` texture tests
11 passed, 1 ignored.

## Loading pacing

`patches/0001-opening-60fps-window.patch` forces 16.7 ms frames for the first
60 s, although the title asks for 33.3 ms. The front end's animated art is
authored for 30 fps ticks. Forcing 60 fps and then dropping back to 30 at the
60 s mark, often in the middle of the loading art, made the pacing uneven
(the main fault was the out-of-order video above). With the override off, every frame line in the loading
phase is 30.0–31.0 fps and the title never changes interval
(`frame interval title=33.333ms interval=33.333ms`). The patch is still in the
binary; leaving the two variables unset disables it.

## Frame rate

The stable `kalaga.toml` passes only `VICTORY_INPLACE_MB=4096`. The 4 fps
results in [performance.md](performance.md) also used the relay and in-place
switches. The test config adds them at native resolution:

```text
VICTORY_SKIP_PIPELINES=<docs/amd-skips.txt joined by commas>
VICTORY_SHADER_LOOP_LIMIT=256
VICTORY_INPLACE_MB=4096
VICTORY_RELAY=2
VICTORY_INPLACE=2
VICTORY_WIDE_BACK=1
VICTORY_CARD_BUFFERS_MIN_MB=1
VICTORY_CARD_BUFFERS_MB=1024
VICTORY_JOIN_COPIES=1
VICTORY_CARD_REHASH_RUNS=1
```

| Run | Config | Gameplay fps | Removals | Log |
|---|---|---|---|---|
| 2 | skips + loop limit + `INPLACE_MB` only | 2.2–2.4 | 0 | `logs/victory-20261124-194129.log` |
| 3 | run 2 + switches above | **3.7–4.5** (mostly 3.8–4.0) | 0 | `logs/victory-20261124-194930.log` |

Picture at native resolution: `logs/pc-test3/054-t350.png`. This is the same
~4 fps wall described in performance.md (title-buffer readback and
single-record indirect draws). 15–30 fps still needs the fork changes listed
there.

## Fork and upstream updates used

Fetched read-only:

- **`fxceless/victory-fork`** (formerly `victory-gta6`): `main` moved
  `2119b0e` → `31714de`, adding `3bff182` (a combined PR branch: double-precision
  shader instructions, paired-interpolation reads, earlier eviction of idle
  textures under memory pressure, a DirectStorage write retry, a texture
  catch-up budget, zlib-rs) and `31714de` (AMD view-heap clamp, permlane
  lowering). The test copy is built on it. Unlike the earlier trial of similar
  PRs ([upstream-review.md](upstream-review.md)), the world ran at
  3.7–4.5 fps with 0 removals. It still refuses `b22a16a178976e1b` without
  `VICTORY_WAVE_HALF_SUM_ANY=1`.
- **`Marvisak/VIctory`**: `70564ae` → `4118f33` (device-removed reason logging,
  f16 interpolation, helper-lane fixes). Not merged: the fork does not
  merge cleanly with upstream (fork issue #126).
- **XCL**: `20cf130` → `8c4a46a`, 22 commits (per-lane mask fixes, mesh PSO
  topology, direct-DXIL caching, a fast-boot commit). Its “device type”
  option sets the console model, not the controller type; nothing applies to
  input prompts. Not integrated.

## Mouse-look

Patch: [`patches/0002-mouse-look.patch`](../patches/0002-mouse-look.patch)
(`crates/victory-hle/src/modules/gameinput.rs`).

- While the game window is in front, the cursor is hidden and held at the
  window's centre. Mouse movement drives the keyboard stand-in pad's right
  stick. Alt-Tab (or any other window taking focus) gives the cursor back.
- Right mouse button → left trigger (aim); left mouse button → right trigger
  (fire). The existing keys still work (WASD move, I/J/K/L camera, Enter = A,
  Backspace = B, Esc = Menu, Tab = View, Q/E shoulders, Z/C triggers).
- Mouse speed becomes stick deflection, averaged over 180 ms so the title still
  sees it at ~4 fps. The smallest moving deflection is 0.22, so slow movement
  clears the title's stick dead zone.
- Tuning: `VICTORY_MOUSE_SPEED` (pixels/s for full turn speed, default 1800;
  lower is more sensitive), `VICTORY_MOUSE_FLOOR` (default 0.22),
  `VICTORY_MOUSE_LOOK=0` to turn it off.
- **Esc (pause menu) gives the mouse back.** Esc still opens the game's
  menu, and the cursor is released and shown. Esc again takes it back. If the
  menu was closed another way (Backspace, or choosing Resume), a left click in
  the window takes the cursor back. That click is not passed on as a trigger
  pull. A click on the title bar does not take it back, so the window can still
  be moved.
- Mouse-look only applies when no real controller is connected.
- The title draws into its own window class (`sgaWindowClass`), not the
  runtime's, so the check accepts any window of the game's process except a
  console.
- Tests: three new unit tests; `victory-hle` gameinput tests 10/10 pass.
- Esc verified in game (`logs/esc-test/`): cursor clipped → Esc → free (menu
  dims the screen) → click → clipped → Esc → free → Esc → clipped.

Verified: the log shows `mouse-look holding the cursor`, and a script moving
the cursor 20 px right each step turned the prologue camera right across
`logs/pc-test/056…072`. Feel and sensitivity have **not** been judged by a
person.

## PC button prompts

Not changed. The title registers input callbacks for gamepads (`0x40000`) and
the keyboard (`0x10`) only, never the mouse (`0x20`). It has no sign of a
keyboard/mouse prompt mode to switch on. The glyphs (“Hold LT to interact”,
the stick icons) are drawn from the title's own UI art. Showing PC keys would
need the glyph images found and replaced at load time, with labels matching
the key mapping above. That is a separate asset-replacement investigation and
was not attempted.

## Other findings

- The account picker waits for A (Enter). An unattended run sits there; the
  earlier runs advanced because someone pressed a button.
- Focus scripts must use the thread-input attach (`logs/focusgame.ps1`);
  a plain `SetForegroundWindow` from a background process does not give the
  game keyboard focus.
