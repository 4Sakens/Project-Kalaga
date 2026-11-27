# First night at the PC: checklist

Everything below is one double-click: **`Start-Kalaga.bat`** in the Kalaga folder.
It stops at the first problem and says what it was; run it again after fixing
that and it carries on (finished steps are skipped or quick).

## Before you start (once)

- [ ] Python 3.11+ installed, with "Add python.exe to PATH" ticked
- [ ] Git for Windows installed
- [ ] Rust 1.98.1 GNU toolchain and mingw-w64 (already set up for the old fork)
- [ ] `git pull` in the Kalaga folder (or download it fresh from GitHub)
- [ ] AMD driver set up as in [amd-settings.md](amd-settings.md): ReBAR on,
      Anti-Lag on, HYPR-RX **off**, AFMF **off for now** (it skews the test numbers)
- [ ] Close the browser and anything heavy: the test measures memory too

## What the batch file does (about 45-60 minutes)

1. **Updates Kalaga** (`git pull`).
2. **Clones VIctory-RDNA** into its own folder (default `D:\VIctory-RDNA`; your
   old `D:\VIctory` is not touched).
3. **Applies the patch series** on a branch called `kalaga-prs`. When a later
   pull of Kalaga brings new patches, the next run patches again by itself.
4. **Builds `victory.exe`** (10-20 minutes the first time).
5. **First run, 12 minutes.** Load your save and walk and drive around. It is
   slow on purpose: every pipeline is built as the game asks for it, so later
   runs are smooth. Expect stutter.
6. **Prepares shaders** for each test preset (a few minutes each).
7. **Test session**: four presets, 4 minutes each in the world. For each one,
   load the same save and stand still in the same spot for the first ~20 seconds
   (that is when the screenshot for the side-by-side is taken), then play
   normally. When it finishes, the best preset is written to `kalaga.toml`.

## After it finishes

- [ ] Open `logs\session-<time>\summary.md`: fps, memory and the screenshots of
      each preset side by side. Fuzzy on one and sharp on another tells us the
      cause.
- [ ] Turn AFMF on (per-game profile) if you want the smoother feel.
- [ ] Play with `py -3 -m kalaga launch`, or `Start-Kalaga.bat` again.
- [ ] Send `logs\session-<time>.zip` for tuning.

## Something looks wrong (black textures, blur, crash)

Double-click **`Report-Bug.bat`** right after it happens. It zips the latest
logs, the preset and its switches, the runtime build and patch series, and the
last frame stats into `logs\bug-<time>.zip`. Add one line on what you saw
and where.
