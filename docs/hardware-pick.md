# Which runtime fits this PC (2026-11-26)

Machine: Ryzen 5 5600X (6 cores), 32 GiB RAM, Radeon RX 7600 (8 GB, RDNA3),
Windows 11. Source list: the PortWatch tracker
(`portwatch-vi.xyz/data/tracker.json`), read on 2026-11-26, and shallow
clones of the public repositories below. Nothing here was run on this
machine yet; every number is the owner's or PortWatch's.

## Pick: Belobug/VIctory-Belobug-AMD

| | |
|---|---|
| Repo | `https://github.com/Belobug/VIctory-Belobug-AMD` (`main` @ `4eb6cfd`), GPL-3.0 |
| Why | The fastest public AMD code. Same tree as AvatarManz's `VIctory-7900XTX` (35 files differ), and `fxceless/victory-fork` now pulls fixes from it. All 25,790 used shaders translate, so the 43-entry AMD skip list is not needed. |
| Measured (7900 XTX, i9-12900K, 64 GB) | City street, Series S, renderer patches on: ~45 ms (22 fps). Series X: ~53 ms (19 fps). Kalaga's current fork base: ~4 fps on this PC. |
| Bottleneck upstream | One submit thread (~40 ms/frame) — CPU-side. The `VICTORY_PORT_*` patches attack exactly that. |
| Same layout as our checkout | `apps/victory`, `victory.exe`, `victory.toml`, `--console series-s`: `kalaga build`/`launch` work unchanged with `victory_dir` pointed at it. |

### The catch on this PC

Upstream reports **~30 GB private memory and 10.5 GB VRAM**, and recommends
64 GB RAM. This PC has 32 GiB and 8 GB. Expect paging and texture
streaming limits; real frame rate here will be well under the 7900 XTX
number. That is why every preset below uses the **Series S** profile: on
8 GB cards it roughly doubles the frame rate and fits the card (CCS03 and
LNX-victory on 8 GB GPUs), and on Belobug it is ~5 ms faster. Set the
Windows page file to system-managed on an SSD with 40+ GB free before
trying.

## Presets added

`python -m kalaga presets` lists them; `kalaga launch --preset NAME` or
`[launch] preset = 'NAME'` uses one. `[launch.extra_env]` and an explicit
`[launch] console` still override the preset.

| Preset | Runtime checkout | What it sets |
|---|---|---|
| `rx7600-belobug` | Belobug | Series S; the switches Belobug's `scripts\play.ps1` uses |
| `rx7600-belobug-quality` | Belobug | Series X profile drawn at native 1080p (`VICTORY_OUTPUT=1920x1080` + `VICTORY_RENDER_SCALE=1.0`; without the scale the title draws 1280x720 and upscales): sharpest picture, most VRAM |
| `rx7600-belobug-6core` | Belobug | `rx7600-belobug` + list and compare pools sized for 12 threads (experiment) |
| `rx7600-belobug-fast` | Belobug | the above + `VICTORY_PORT_CONSTANTS/DESCRIPTORS/CBV/GUARD/JOURNAL=1` (upstream measures −8 to −10 ms a frame for the three it times; off by default there while tested) |
| `rx7600-belobug-safe` | Belobug | Series S + `play.ps1 -Safe` settings. First thing to try after a crash |
| `rx7600-fork` | current `D:\VIctory` (`fxceless/victory-fork`) | Series X + exactly the docs/pc-test.md run-3 switches + `docs/amd-skips.txt`: the known-good fallback |

All Belobug presets also set `VICTORY_WINDOW_BUDGET_MB=1536` (release idle
copies under memory pressure) and `VICTORY_PIPELINE_BOOK=1` (record pipelines
for `kalaga prepare`). With a preset, `VICTORY_*` switches left in your shell
(for example the README's `VICTORY_SKIP_PIPELINES`) are ignored and listed in
the launch notes; paths such as `VICTORY_DATA_DIR` are kept. Put anything you
want on top in `[launch.extra_env]`. What to test and in which order:
[optimization-plan.md](optimization-plan.md).

## Setting it up

```powershell
git clone https://github.com/Belobug/VIctory-Belobug-AMD D:\VIctory-Belobug
copy D:\VIctory-Belobug\victory.example.toml D:\VIctory-Belobug\victory.toml   # set paths
```

In `kalaga.toml`:

```toml
[runtime]
victory_dir = 'D:\VIctory-Belobug'   # keep D:\VIctory for the old fork

[launch]
preset = 'rx7600-belobug'
```

Then `python -m kalaga build`, `python -m kalaga prepare` (same switches as
the preset you will play; translate shaders
and build pipelines ahead, so the first run does not stutter) and
`python -m kalaga launch --dry-run` to check the command. Our `patches/` are written against `fxceless/victory-fork`
and are **not** applied to Belobug; it has its own mouse/keyboard mapping
(`VICTORY_KBM_GTA=1`, add it in `[launch.extra_env]`). Ray tracing
(`VICTORY_BVH_BUILDER=1`) is left off: it costs about a third of the frame
upstream and needs more memory than this card has.

Order to test: `rx7600-belobug-safe` (does it boot and reach the cell?) →
`rx7600-belobug` → `rx7600-belobug-fast`. Record fps and peak VRAM/RAM from
Task Manager for each so the presets can be tuned from real numbers.

## The rest of the board, for this PC

| Effort | Fit for RX 7600 / 32 GB | Why |
|---|---|---|
| AvatarManz `VIctory-7900XTX` | Second choice | Same code as Belobug, best fps on the board (16–25), but 40–46 GB memory measured; Belobug is the same tree with more contributors |
| DexNom `VIctory` | No | AMD with ray tracing working, but ~1 fps with it on; tuned for 24 GB |
| CCS03, LNX-victory, neptune-8gb, Victory-RTX2080 | Ideas only | Built for 8 GB **NVIDIA** cards (3–8 fps). Their lesson (Series S on 8 GB, texture skipping) is folded into the presets |
| Kelvaroq, ZETTROX, VItoriaBr | No | NVIDIA-tested; ZETTROX repo is gone |
| NotNozy, Doomsday, darkworldhm, suri, omonkey | Can't | No public code |
| CGBJ | Can't | Repo returns 404; tested with 16 GB VRAM |
| XCL, ScarlettX, TuxBox, OpenScarlett, scarlett-layer, xbox-emulator | No | General runtimes; none plays GTA VI's world yet |
| Leonida, americas-recomp | Can't | Deleted (DMCA / 404) |
