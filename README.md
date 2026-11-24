
**One repository for running Xbox Series X|S game files on Windows — natively, without CPU emulation.**

Project Z-GTA consolidates the ongoing work on running console (GDK) games — currently **Grand Theft
Auto VI** — natively on a Windows PC, from a copy of the game the owner already has.

It unifies four efforts:

1. **XCL** (local: `D:\xcl`) — general console runtime in Rust: kernelx, XGameRuntime, D3D12.X,
   XAudio2, VFS, memory, TLS, PE loader, RDNA2 → HLSL → DXIL shader recompilation; plus the GTA VI
   bring-up. Retail titles playable; GTA VI reached world loading.
2. **VIctory** (local: `D:\VIctory`) — GTA VI–specific layer in Rust: formats, hooks, build
   identities, CLI. Early stage: boot / menus / loading work done, world rendering incomplete.
3. **FiveStar Recomp** (GitHub: `ThatRecompDev/five-star-recomp`) — GTA VI port in C# / .NET:
   formats, shader translation, loader, graphics, asset extraction, CLI (`fivestar`,
   `fivestar-loader`). Boots → memory setup → archive opening → graphics device setup → presents →
   first-run → story load → reached story intro title card, then stops.
4. **Xbox2Windows** (GitHub: `R0Y00/Xbox2Windows`) — static recompilation research in C++ / CMake and
   Python: source-built CPU/GPU tests, offline PE / shader tooling; cites XCL as behavioural
   reference. Full-game startup unverified.

## Status

Being assembled. No single combined build yet.

- **XCL**: retail games playable (Minecraft Preview, Unicorn Overlord fully; Fortnite, XDefiant
  online-limited); GTA VI bring-up in progress (world loading reached; open GTA issues re: GPU
  watchdog, black window / BCPack refusals, 0xC0000005).
- **VIctory**: not playable yet; boot/menus/loading work done; world rendering incomplete; no known
  builds registered.
- **FiveStar**: not running yet; deepest single-game progress (boot → present → story card).
- **Xbox2Windows**: full-game startup unverified; source-built fixture tests green; GPU checks
  runnable.

## Proposed structure

```
ZZ-box/
├── README.md
├── Cargo.toml            # Rust workspace: XCL runtime crates + VIctory game layer
├── crates/               # Rust crates (platform runtime + GTA VI game layer)
├── dotnet/               # FiveStar Recomp source
├── research/             # Xbox2Windows source (C++, Python, tests)
└── docs/                 # integration notes / decisions
```

## Open decisions

- **Licensing**: XCL GPL-2.0-only; FiveStar & VIctory GPL-3.0; Xbox2Windows MIT — mixing needs a
  policy decision.
- **Architecture**: how the Rust runtime, C# GTA port and C++ research combine into one build.
- **Scope**: which capabilities from each effort become canonical going forward.

## Next steps

1. Decide the integration architecture.
2. Port / graft the chosen pieces.
3. Build on Windows (Rust `stable-x86_64-pc-windows-msvc`; VS 2022; DXC; D3D12 SM 6.6).
4. Run GTA VI (1.0.2.1, title `7952987A`) from the combined build against `D:\GTA 6\…`.

## Related

- Local: `D:\VIctory`, `D:\xcl`, `D:\GTA 6\GTA6.Xbox.v1.0.2.1-CYBERLEEK`
- GitHub: `ThatRecompDev/five-star-recomp`, `R0Y00/Xbox2Windows`
