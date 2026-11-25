# Project Kalaga tooling (`kalaga`)

`kalaga` is the glue layer of Project Kalaga. It does not reimplement the
runtime: it locates and validates the local console dump, checks what the
machine can actually build and run, builds the Rust runtime with the correct
toolchain, stages the shader compiler, starts the title through it, and writes
logs and a machine-readable report when something fails.

It is plain Python 3.11+ with no third-party dependencies, so it runs on a fresh
Windows install before anything else is set up.

## Why a separate layer

The repository already contains three implementations of the hard parts
(XCL's platform runtime, VIctory's GTA VI layer, FiveStar's C# port). The
missing piece was never another runtime — it was a repeatable way to answer
"are my files good, can this machine build it, and what exactly ran?".
That is what this layer does, and it is the piece that a launcher needs.

## Install

Nothing to install; run it from the repository root:

```powershell
python -m kalaga --help
python -m unittest discover -s tests -v      # 33 tests
```

Optionally install the console entry point:

```powershell
pip install -e .
kalaga doctor
```

## Configuration

Copy `kalaga.example.toml` to `kalaga.toml` (git-ignored) and set the paths.
Resolution order: `--config`, `KALAGA_CONFIG`, `kalaga.toml`, defaults.

| Key | Meaning |
|---|---|
| `game.dir` | the dump to run |
| `game.root` | where `locate` searches when `dir` is empty |
| `game.expected_title_id` / `expected_version` | refuse anything else |
| `game.manifest` | `.torrent` used as a file/size manifest |
| `runtime.preferred` | `victory` or `xcl` |
| `runtime.victory_dir` / `xcl_dir` | checkouts of the runtimes |
| `runtime.target` | Rust target triple; empty = host default |
| `runtime.toolchain` | rustup toolchain to use, e.g. `1.98.1-x86_64-pc-windows-gnu` |
| `runtime.toolchain_bin` | folder prepended to PATH for builds (mingw-w64 `bin`) |
| `runtime.profile` | `release` (default) or `diag` (diagnostics aids) |
| `runtime.dxc_dir` | folder with `dxcompiler.dll` + `dxil.dll` |
| `launch.console` | `series-x` or `series-s` |
| `launch.warp` | software D3D12 adapter (safe diagnostics) |
| `launch.log` | runtime log filter |
| `launch.extra_env` / `extra_args` | escape hatches |

## Commands

| Command | What it does |
|---|---|
| `locate` | finds dumps under `game.root`, prints title id / version / name |
| `validate` | identity, executable, RPF9 headers, and manifest file/size check |
| `doctor` | OS, GPU, driver, RAM, free disk, cargo/rustc/link/dxcompiler/dotnet |
| `plan` | per-runtime readiness with the exact fix for every blocker |
| `build` | builds the selected runtime with the configured target |
| `launch` | stages DXC, composes the command, runs it, tees the log |
| `report` | one JSON document with all of the above |

Exit codes: `0` ok, `2` invalid/unsupported dump, `3` prerequisites missing,
`4` the runtime failed.

### validate

```text
game dir   : D:\GTA 6\GTA6.Xbox.v1.0.2.1
title      : Grand Theft Auto VI  id=7952987A  version=1.0.2.1
publisher  : Rockstar Games
executable : game_scarlett_master.exe
files      : 109  (208.6 GiB)
archives   : 22 RPF9, 0 unrecognised
manifest   : 108/108 files, 0 missing, 0 wrong size, 1 extra
  [warn] not in manifest: game_scarlett_master.exe
result     : OK
```

Validation is deliberately cheap: it reads `MicrosoftGame.Config`, stats every
file and reads four bytes per archive, so a 200 GiB dump validates in seconds.
Piece hashes are not checked (that would read everything); exact sizes catch
the realistic failure, truncation.

### doctor

Reports hardware and toolchain, and names what is missing for a run. On the
development machine it correctly reported the absent MSVC linker and shader
compiler while finding cargo/rustc/rustup/dotnet.

### plan

Every blocker carries its fix, e.g.:

```text
[victory] build=True run=True
    note: VIctory boots the title and runs its menus at the title's own 30 fps; ...
    note: On a real GPU the world can hang the display driver; use `kalaga launch --warp` ...
[xcl] build=True run=False
    warn: xcl is not built yet
             fix: run `kalaga build`
```

### launch

```powershell
python -m kalaga launch --dry-run     # print the exact command and env
python -m kalaga launch --warp        # software adapter, safest diagnostic run
python -m kalaga launch
```

`launch` copies `dxcompiler.dll`/`dxil.dll` next to the runtime executable when
`runtime.dxc_dir` is set, exports `VICTORY_DXC_DIR`/`XCL_DXC_DIR`, sets
`VICTORY_LOG`, runs from the runtime checkout with `VICTORY_CONFIG` pointed at
its `victory.toml`, honours `--warp` and `--timeout`, and tees output to
`logs/<runtime>-<stamp>.log`. On exit it prints the code in hex, the last lines
of the runtime's `crashes.log`, and a hint for the common Windows/D3D12 failure
codes.

Measured on the development machine: steady 30.0 fps in the title's first-boot
screen, 21 draws/frame, 0 dropped pipelines, audio APU/DSP connected — see
[status.md](status.md).

## Tests

`python -m unittest discover -s tests` covers identity parsing (including the
UTF-8 BOM in `MicrosoftGame.Config`), archive magic and truncation detection,
manifest comparison, config layering, planner decisions (missing linker,
missing DXC, unbuilt runtime, invalid dump), target-triple layout, command
composition, DXC staging and CLI exit codes.

Set `KALAGA_REAL_GAME` to a real dump to add the integration check:

```powershell
$env:KALAGA_REAL_GAME = 'D:\GTA 6\GTA6.Xbox.v1.0.2.1'
python -m unittest tests.test_kalaga.RealDumpTests -v
```

## Limits

The tooling never modifies game files, never downloads game content, and never
runs anything with elevated rights. It cannot make a runtime finish rendering a
scene it does not yet support; it makes that state visible and diagnosable.
