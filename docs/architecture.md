# Architecture of the Project-Z pipeline

Project Z-GTA has three hard layers that already exist as separate efforts, and
one glue layer that did not. This document describes the glue and how it composes
with the rest.

```text
 local game dump (never in git)
        |
        v
 [locate] -> [validate] -> [doctor] -> [plan] -> [build] -> [stage] -> [launch] -> [report]
                                              |
                                    +---------+----------+
                                    |                    |
                             VIctory (GTA VI layer)   XCL (platform runtime)
                                    |                    |
                                    +---------+----------+
                                              |
                                    D3D12 / XAudio2 / XInput
```

## Layer boundaries

| Layer | Owner | Responsibility |
|---|---|---|
| Platform runtime | XCL (`D:\xcl`) | kernelx, XGameRuntime, D3D12.X, VFS, PE loader, RDNA2 → DXIL |
| Game layer | VIctory (`D:\VIctory`) | GTA VI formats, hooks, build identities, shader pipeline, CLI |
| Alternate port | FiveStar (`fivestar/`) | C#/.NET GTA VI pipeline, independent implementation |
| Research | Xbox2Windows (`xbox2windows/`) | static-recompilation fixtures and tooling |
| **Glue** | `projectz/` here | discovery, validation, readiness, build, staging, launch, diagnostics |

The glue layer deliberately contains no game logic. It never parses an archive
beyond its four-byte header, never writes into the dump, and never decides what
a runtime should render.

## Pipeline stages

1. **Command-line entry point**: `python -m projectz <command>`; global config discovery (`--config`, `PROJECTZ_CONFIG`, `projectz.toml`, defaults).
2. **Config**: `projectz/config.py` resolves `game.dir` and how each runtime is expected to be laid out.
3. **Locate**: `gamefs.find_games()` walks the configured root, reading `MicrosoftGame.Config` to identify candidates.
4. **Validate**: `gamefs.scan()` reads `TitleId`, `Version`, publisher, executable names, counts files and rejects non-RPF9 archives; `gamefs.verify_manifest()` compares names and sizes against the release `.torrent`. Two exit-code paths are distinguished: I/O problems versus a genuinely unsupported dump.
5. **Doctor**: `doctor.detect()` resolves what the machine can do (GPU, driver, RAM, disk free, Rust toolchain, MSVC linker, DXC, .NET). PATH is not trusted, and toolchain discovery also looks in `%USERPROFILE%\.cargo\bin`.
6. **Plan**: `plan.assess()` turns the previous two stages into a list of blockers, each with a concrete fix. It is deterministic and fully unit-tested; this is what makes a failed launch explicable instead of mysterious.
7. **Build**: `projectz build` runs `cargo build` with the configured target. On machines without Visual Studio the `x86_64-pc-windows-gnu`/`gnullvm` triple is the usable path; the runtime's own `rust-toolchain.toml` still pins its supported toolchain, so the whole thing is reproducible.
8. **Stage**: `launch.stage_dependencies()` copies `dxcompiler.dll` and `dxil.dll` next to the runtime executable so the process can translate console shaders without a Windows SDK on PATH.
9. **Launch**: the runtime CLI is composed per runtime (`victory run <exe> --execute --console ...`, `xcl run <game dir>`), `VICTORY_LOG`/`VICTORY_D3D12_WARP`/`XCL_DXC_DIR` are set from config, and stdout is teed into `logs/`.
10. **Report**: `projectz report` emits one JSON file with environment, scan result, manifest comparison, per-runtime blockers and the selected runtime, which is what a bug report needs.

## Runtime selection

`plan.pick()` prefers `runtime.preferred`, then any runtime that can actually
run. A runtime is "ready to run" only when the dump validates, the executable
exists, and no hard blocker remains. VIctory is preferred for GTA VI because it
implements the GTA VI game layer directly; XCL is the broader platform runtime
and is selectable when the game layer is not built.

## Fidelity and legal boundaries

- Game data stays where the user put it; the repository only stores paths in a
  git-ignored `projectz.toml`.
- No game file is copied, packaged or redistributed by these tools.
- No DRM, licence or access-control mechanism is touched; the tools orchestrate
  a runtime that executes the title from the user's own dump.
- Downloads are limited to public build tooling (Rust, mingw-w64, Microsoft's
  open-source DirectX Shader Compiler, Python packages).
