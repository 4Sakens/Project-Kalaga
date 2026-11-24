# Integration plan — Z-GTA

How the consolidated repository combines the four efforts into one build.

## Sources

1. **XCL** (`D:\xcl`) — general console runtime, Rust: kernelx, XGameRuntime, D3D12.X, XAudio2, VFS,
   memory, TLS, PE loader, RDNA2 → HLSL → DXIL recompilation; plus the GTA VI bring-up.
2. **VIctory** (`D:\VIctory`) — GTA VI–specific layer, Rust: formats, hooks, build identities, CLI.
3. **FiveStar Recomp** (`ThatRecompDev/five-star-recomp`) — GTA VI port, C# / .NET: formats, shaders,
   loader, graphics, assets, CLI.
4. **Xbox2Windows** (`R0Y00/Xbox2Windows`) — static recomp research, C++ / CMake + Python: source-built
   CPU/GPU tests, offline tooling; cites XCL as behavioural reference.

## Target architecture

One repository, one build, one game-facing runtime:

- **Platform layer**: XCL's Rust runtime (console APIs answered on PC, D3D12.X, recompilation,
  VFS, memory, TLS, PE loader).
- **Game layer**: VIctory's GTA VI specifics (formats, hooks, build identities) merged with
  FiveStar's GTA VI pipeline work (shaders → DXIL, assets, loader, graphics).
- **Research layer**: Xbox2Windows' source-built tests and offline tooling (kept as tests/tools).

## Phases

1. **Rust platform + game layers** merged into a single Cargo workspace (`crates/`).
2. **GTA VI pipeline** from FiveStar grafted onto the merged Rust runtime (shaders → HLSL → DXIL,
   textures, archives, loader, graphics).
3. **Research tooling** from Xbox2Windows wired in (source-built fixtures, GPU checks).
4. **Unified CLI** (`xcl` / `victory` / `fivestar` front ends) over the single runtime.

## Open decisions

- Licensing: GPL-2.0 (XCL) / GPL-3.0 (FiveStar, VIctory) / MIT (Xbox2Windows) — policy needed.
- Language boundary for the GTA VI game layer (Rust vs C#) and how the C++/Python research half runs.
- Canonical ownership of recompilation, graphics, assets per game.

## Verification

- Rust: `cargo test --workspace -- --test-threads=4` (Windows, Rust `stable-x86_64-pc-windows-msvc`).
- FiveStar: `dotnet test`.
- Xbox2Windows: `ctest` / `tools/*` offline checks.
- End to end: GTA VI 1.0.2.1 (title `7952987A`) from the combined build against the owner's dump.

See `README.md` for the status summary.
