# AMD driver and Windows settings for the RX 7600 PC

Settings outside Kalaga that change how the game looks and feels. Checked
against AMD's pages on 2026-11-27; menu names move between driver versions.

## AMD Software: Adrenalin Edition

Make a profile for `victory.exe` (Gaming → Games → Add game, point at
`D:\VIctory-RDNA\target\...\victory.exe`) so nothing here changes your other
games.

| Setting | Value | Why |
|---|---|---|
| Driver version | 25.3.1 or newer | AFMF 2.1 needs it |
| **AMD Fluid Motion Frames (AFMF 2.1)** | **On**, for this profile only | Inserts a generated frame between each pair the game renders: ~15 → ~30, ~20 → ~40 on screen. Works in DirectX 12 games without the game's help, on RX 7000 in full screen or **borderless full screen**, which is why the presets now set `VICTORY_FULLSCREEN=1` |
| VSync (driver) | Off | AFMF requires VSync off in the driver and the game |
| AMD FreeSync (monitor + driver) | On, if the monitor has it | With AFMF and a varying frame rate, FreeSync removes tearing that VSync would otherwise fix |
| Radeon Anti-Lag | On | Cuts the input delay frame generation adds. (Anti-Lag **2** needs the game to support it; plain Anti-Lag works in any DirectX 12 game) |
| HYPR-RX one-click profile | **Do not use** | It also turns on Radeon Super Resolution and Radeon Boost, which lower the render resolution: a softer picture. Turn AFMF and Anti-Lag on by hand instead |
| Radeon Super Resolution, Radeon Boost | Off | Same reason |
| Radeon Chill | Off | Caps the frame rate |
| Texture Filtering Quality | High | Sharper textures at an angle for almost no cost |
| Surface Format Optimization | Off | Can change how render targets are stored |
| Tessellation Mode | Use application settings | |
| Smart Access Memory / Resizable BAR | On (also in the BIOS: Above 4G Decoding + Re-Size BAR) | VIctory-RDNA's measurements were all with ReBAR on; its in-place memory path uses it |

### What to expect from AFMF here

AMD recommends a base rate of at least **55 fps at 1080p** before
generating frames, and ideally around 60. This game will run well under that
on this PC (see the estimate in the README), so:

- **Motion looks smoother**: a 20 fps base shows 40 frames a second.
- **Input does not get faster.** It gets a frame later, about 25-50 ms at
  these rates. Anti-Lag takes back some of that.
- **Fast camera turns and the HUD can smear or wobble**: AFMF only sees the
  finished picture. AFMF 2.1 pauses itself during very fast motion.

Try it on a drive (smooth, predictable motion: it helps most) and in a gun
fight (fast turns: it helps least). Hotkey to toggle in game: Alt+Shift+G
by default (set it under Hotkeys).

## Windows 11

| Setting | Value | Why |
|---|---|---|
| Virtual memory (page file) | System managed, on the fastest SSD, 40+ GB free | The runtimes use 23-46 GB of private memory; with 32 GB of RAM the page file decides whether a spike stutters or crashes (error 1455) |
| Hardware-accelerated GPU scheduling | On (Settings → Display → Graphics → Change default graphics settings) | Recommended for AMD's frame generation |
| Game Mode | On | Keeps background work off the game's cores, which matters on 6 cores |
| Power plan | Balanced or AMD Ryzen Balanced; in Adrenalin leave the GPU at default | Ryzen boosts best on Balanced; High performance gains nothing on Zen 3 |
| Background apps | Close the browser, Discord overlay, RGB tools, game launchers | Every GB and every core counts here |
| Run from | A normal (not administrator) terminal | An admin run keeps the driver's shader cache elsewhere, so `kalaga prepare`'s warm-up is missed |

## RAM in the BIOS

Turn on **XMP/EXPO** for the RAM's rated speed. Zen 3 CPU work (the
runtime's submit thread, which bounds the frame here) runs noticeably faster
with 3200-3600 MT/s RAM than at the 2133-2400 MT/s default.
