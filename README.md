# Project Z-GTA

**One repository for running Xbox Series X|S game files on Windows — natively,
without CPU emulation.** The title's own x86-64 code runs in our process; the
console APIs it expects (`kernelx`, XGameRuntime, D3D12.X, XAudio2, …) are
answered by a compatibility runtime, and its RDNA2 shaders are recompiled to
DXIL on the PC GPU.

The project consolidates four efforts:

| Effort | Where | What it is |
|---|---|---|
| **XCL** | `D:\xcl` (upstream `ivall/xcl`) | General console runtime in Rust: kernelx, XGameRuntime, D3D12.X, XAudio2, VFS, memory, TLS, PE loader, RDNA2 → HLSL → DXIL. Retail titles playable. |
| **VIctory** | `D:\VIctory` (upstream `Marvisak/VIctory`) | GTA VI–specific layer in Rust: formats, hooks, build identities, shader pipeline, CLI. |
| **FiveStar Recomp** | `fivestar/` (submodule) | GTA VI port in C#/.NET: formats, shader translation, loader, graphics, asset extraction. |
| **Xbox2Windows** | `xbox2windows/` (submodule) | Static-recompilation research in C++/CMake and Python; source-built CPU/GPU fixtures. |
| **Project-Z tooling** | `projectz/` (this repo) | Discovery, validation, readiness, build, dependency staging, launch and diagnostics — the glue that turns the four layers into a repeatable pipeline. |

## Status (2026-11-24, measured on this machine)

Verified today on Windows 11 26300, Ryzen 5 5600X, 32 GiB, RX 7600:

| Stage | State |
|---|---|
| Game dump validation | ✅ 108/108 manifest files, 22 RPF9 archives, 208.6 GiB, title `7952987A` v1.0.2.1 |
| Build without Visual Studio | ✅ `victory.exe` (45 MB) via Rust 1.98.1 GNU + mingw-w64, 1m00s |
| Runtime boot | ✅ title mapped, virtual drive `G:` → dump, offline user, Series X mode |
| Rendering | ✅ steady **30.0 fps**, 21 draws/frame, 0 dropped pipelines, 11 shaders translated |
| UI | ✅ first-boot screen confirmed by frame capture: "ACCOUNT PICKER / SCREEN NARRATION / PLAYER" |
| Audio | ✅ APU + DSP connected (256 streams), `audio.rpf` opened via DirectStorage |
| Input | ✅ GameInput devices enumerated |
| Menus | ✅ (upstream state) menus run at the title's 30 fps |
| World | ❌ reached but renders incompletely (0.5–1.8 s frames upstream); can hang the display driver |
| Gameplay | ❌ not reached |

The runtime is not playable yet. What *is* working end to end is the pipeline:
validate the dump → detect the machine → build the runtime → stage DXC → launch
the original executable → capture evidence and a diagnostic report.

## Quick start

```powershell
copy projectz.example.toml projectz.toml     # set your paths
python -m projectz doctor                    # hardware + toolchain
python -m projectz validate                  # dump identity, archives, manifest
python -m projectz plan                      # what can run, and what blocks it
python -m projectz build                     # builds the selected runtime
python -m projectz launch --dry-run          # exact command + env
python -m projectz launch                    # run the title
python -m projectz report --out report.json  # one JSON with everything
```

No Visual Studio? Set a GNU toolchain and a mingw-w64 `bin` folder:

```toml
[runtime]
target = 'x86_64-pc-windows-gnu'
toolchain = '1.98.1-x86_64-pc-windows-gnu'
toolchain_bin = 'D:\projectz-deps\mingw64\bin'
dxc_dir = 'D:\projectz-deps\dxc'
```

See [docs/launcher.md](docs/launcher.md) for every command, config key and exit
code, [docs/architecture.md](docs/architecture.md) for how the layers fit, and
[docs/status.md](docs/status.md) for the full measurement log and next steps.

## Repository layout

```text
ZZ-box/                       (github.com/4Sakens/Project-Z-GTA)
├── projectz/                 integration toolkit (Python, stdlib only)
├── tests/                    33 unit tests; PROJECTZ_REAL_GAME adds the real-dump check
├── docs/
│   ├── launcher.md           commands, configuration, troubleshooting
│   ├── architecture.md       how the pipeline composes the runtimes
│   ├── status.md             measured status, evidence, remaining work
│   └── integration.md        the four-effort merge plan
├── fivestar/                 FiveStar Recomp (submodule)
├── xbox2windows/             Xbox2Windows (submodule)
├── pyproject.toml            projectz packaging
├── projectz.example.toml     configuration template
└── Cargo.toml                Rust workspace stub for the grafted crates
```

The Rust sources of XCL and VIctory stay in their own checkouts for now; the
root `Cargo.toml` declares them as path dependencies so a combined build can be
added without moving code. `projectz.toml` (machine paths) and `logs/` are
git-ignored.

## Requirements

- Windows 10/11 x64, a D3D12 GPU with shader model 6.6 (mesh shaders for the
  world), AVX2 CPU, ≥ 32 GiB RAM for GTA VI.
- Rust (the runtime pins its toolchain), and either Visual Studio Build Tools
  or a mingw-w64 toolchain for the GNU target.
- `dxcompiler.dll` + `dxil.dll` (Windows SDK, or Microsoft's standalone
  [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler)
  release) — `projectz launch` stages them next to the executable.
- Your own copy of the game files. Nothing proprietary is stored here.

## Licensing

XCL is GPL-2.0-only; FiveStar and VIctory are GPL-3.0; Xbox2Windows is MIT; the
Project-Z tooling is GPL-2.0-or-later. Combining them into one distributed build
needs a licence decision — see "Open decisions" in
[docs/integration.md](docs/integration.md).

## Legal

The tools work only with game files the user already has, keep them outside the
repository, and never bypass DRM, licence checks or access controls. No game
archive, executable or copyrighted asset is stored or distributed by this
repository.
