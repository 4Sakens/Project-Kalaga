"""Command line interface: ``python -m projectz <command>``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import config, doctor, gamefs, launch, plan, util

EXIT_OK = 0
EXIT_INVALID_GAME = 2
EXIT_NOT_READY = 3
EXIT_RUNTIME_FAILED = 4


def _cfg(args) -> config.Config:
    return config.load(args.config)


def _ensure_game_dir(cfg: config.Config) -> Path | None:
    if cfg.game_dir and cfg.game_dir.is_dir():
        return cfg.game_dir
    found = gamefs.find_games(cfg.game.root)
    if len(found) == 1:
        return found[0]
    if found:
        # Prefer the one whose identity matches the expected title/version.
        for candidate in found:
            ident = gamefs.read_identity(candidate)
            if ident.title_id.upper() == cfg.game.expected_title_id.upper():
                return candidate
        return found[0]
    return cfg.game_dir


def cmd_locate(args) -> int:
    cfg = _cfg(args)
    candidates = gamefs.find_games(cfg.game.root)
    if not candidates and cfg.game_dir:
        candidates = [cfg.game_dir]
    payload = []
    for candidate in candidates:
        ident = gamefs.read_identity(candidate)
        payload.append(
            {
                "directory": str(candidate),
                "title_id": ident.title_id,
                "version": ident.version,
                "name": ident.name,
                "executable": ident.executable,
                "matches_expected": ident.title_id.upper() == cfg.game.expected_title_id.upper(),
            }
        )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not payload:
            print(f"no game found under {cfg.game.root} (set game.dir in projectz.toml)")
            return EXIT_INVALID_GAME
        print(util.format_table(
            ["directory", "title", "version", "name"],
            [[p["directory"], p["title_id"], p["version"], p["name"]] for p in payload],
        ))
    return EXIT_OK


def cmd_validate(args) -> int:
    cfg = _cfg(args)
    directory = Path(args.game) if args.game else _ensure_game_dir(cfg)
    scan = gamefs.scan(
        directory,
        expected_title_id=cfg.game.expected_title_id,
        expected_version=cfg.game.expected_version,
    )
    manifest_report = None
    manifest = Path(args.manifest) if args.manifest else cfg.manifest_path()
    if scan.directory and manifest and Path(manifest).is_file():
        manifest_report = gamefs.verify_manifest(scan.directory, manifest)

    if args.json:
        payload = scan.to_dict()
        if manifest_report:
            payload["manifest"] = manifest_report.to_dict()
        print(json.dumps(payload, indent=2, default=str))
    else:
        ident = scan.identity
        print(f"game dir   : {scan.directory}")
        print(f"title      : {ident.name or '?'}  id={ident.title_id or '?'}  version={ident.version or '?'}")
        print(f"publisher  : {ident.publisher or '?'}")
        print(f"executable : {ident.executable or '?'}")
        print(f"files      : {scan.file_count}  ({util.human_bytes(scan.total_bytes)})")
        print(f"archives   : {len(scan.rpf_paths)} RPF9, {len(scan.bad_archives)} unrecognised")
        if manifest_report:
            print(
                f"manifest   : {manifest_report.present}/{manifest_report.expected_files} files, "
                f"{len(manifest_report.missing)} missing, {len(manifest_report.wrong_size)} wrong size, "
                f"{len(manifest_report.extra)} extra"
            )
        for issue in scan.issues:
            print(f"  {issue}")
        if manifest_report:
            for rel, _length in manifest_report.missing[:10]:
                print(f"  [error] missing: {rel}")
            for rel, want, got in manifest_report.wrong_size[:10]:
                print(f"  [error] wrong size: {rel} (want {want}, got {got})")
            for extra in manifest_report.extra[:10]:
                print(f"  [warn] not in manifest: {extra}")
        print("result     :", "OK" if scan.ok else "INVALID")

    if not scan.ok:
        return EXIT_INVALID_GAME
    if manifest_report and not manifest_report.exact:
        return EXIT_INVALID_GAME
    return EXIT_OK


def cmd_doctor(args) -> int:
    cfg = _cfg(args)
    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    free = doctor.disk_free_gib(cfg.game.root)
    if args.json:
        payload = env.to_dict()
        payload["disk_free_gib"] = free
        print(json.dumps(payload, indent=2))
        return EXIT_OK
    print(f"os        : {env.os_caption} {env.os_version} (build {env.os_build})")
    print(f"gpu       : {env.gpu or '?'} driver {env.gpu_driver or '?'}")
    print(f"ram       : {env.ram_gib} GiB")
    print(f"disk free : {free} GiB at {cfg.game.root}")
    print()
    rows = []
    for name in ("cargo", "rustc", "rustup", "link", "dxcompiler", "dotnet", "cmake"):
        tool = env.tool(name)
        rows.append([name, "yes" if tool.present else "NO", tool.version or tool.path or "-"])
    print(util.format_table(["tool", "found", "version/path"], rows))
    if env.vs_install:
        print(f"\nvisual studio: {env.vs_install}")
    if env.dxcompiler:
        print(f"dxcompiler   : {env.dxcompiler}")
    missing = [name for name in ("cargo", "link", "dxcompiler") if not env.tool(name).present]
    if missing:
        print(f"\nmissing required for a GTA run: {', '.join(missing)}")
    return EXIT_OK


def cmd_plan(args) -> int:
    cfg = _cfg(args)
    directory = _ensure_game_dir(cfg)
    scan = gamefs.scan(
        directory,
        expected_title_id=cfg.game.expected_title_id,
        expected_version=cfg.game.expected_version,
    )
    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    assessments = plan.assess_all(env, scan, cfg)
    chosen = plan.pick(assessments, cfg.runtime.preferred)
    if args.json:
        print(json.dumps(
            {"chosen": chosen.runtime, "assessments": [a.to_dict() for a in assessments]},
            indent=2,
        ))
        return EXIT_OK
    for assessment in assessments:
        print(f"[{assessment.runtime}] build={assessment.can_build} run={assessment.can_run}")
        for note in assessment.notes:
            print(f"    note: {note}")
        for blocker in assessment.blockers:
            print(f"    {blocker.severity}: {blocker.message}")
            if blocker.fix:
                print(f"           fix: {blocker.fix}")
    print(f"\nselected runtime: {chosen.runtime}")
    return EXIT_OK if chosen.can_run else EXIT_NOT_READY


def cmd_build(args) -> int:
    cfg = _cfg(args)
    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    runtime = args.runtime or cfg.runtime.preferred
    source = Path(cfg.runtime.victory_dir if runtime == "victory" else cfg.runtime.xcl_dir)
    cargo = env.tool("cargo")
    if not cargo.present:
        print("cargo is not installed; install Rust from https://rustup.rs", file=sys.stderr)
        return EXIT_NOT_READY
    gnu = "gnu" in cfg.runtime.target.lower()
    if gnu:
        if not (env.tool("gcc").present or env.tool("link").present):
            print(
                "no linker for the GNU target: gcc was not found. Install mingw-w64 and\n"
                "set runtime.toolchain_bin to its bin folder.",
                file=sys.stderr,
            )
            return EXIT_NOT_READY
    elif not env.tool("link").present:
        print(
            "the MSVC linker (link.exe) is missing. Install Visual Studio 2022 Build Tools\n"
            "with 'Desktop development with C++' and rerun, or switch to a *-windows-gnu\n"
            "target with runtime.toolchain_bin set to a mingw-w64 bin folder.",
            file=sys.stderr,
        )
        return EXIT_NOT_READY
    if not (source / "Cargo.toml").is_file():
        print(f"no Cargo.toml in {source}", file=sys.stderr)
        return EXIT_NOT_READY

    profile = ["--profile", "diag"] if args.diag else ["--release"]
    package = "victory" if runtime == "victory" else "xcl"
    argv = [cargo.path]
    if cfg.runtime.toolchain:
        argv.append(f"+{cfg.runtime.toolchain}")
    argv += ["build", *profile, "-p", package]
    if args.diag:
        argv += ["--features", "diagnostics"]
    if cfg.runtime.target:
        argv += ["--target", cfg.runtime.target]
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = cfg.logs_dir / f"build-{runtime}.log"
    print(f"$ {' '.join(argv)}  (cwd {source})")
    print(f"log: {log_path}")
    if args.dry_run:
        return EXIT_OK
    build_env = dict(os.environ)
    if cfg.runtime.toolchain_bin:
        build_env["PATH"] = cfg.runtime.toolchain_bin + os.pathsep + build_env.get("PATH", "")
    rc, out, err = util.run(argv, cwd=str(source), timeout=3600, env=build_env)
    log_path.write_text(out + err, encoding="utf-8", errors="replace")
    tail = "\n".join((out + err).splitlines()[-25:])
    print(tail)
    if rc != 0:
        print(f"build failed with exit code {rc}; full log at {log_path}", file=sys.stderr)
        return EXIT_RUNTIME_FAILED
    print("build OK")
    return EXIT_OK


def cmd_launch(args) -> int:
    cfg = _cfg(args)
    if args.warp:
        cfg.launch.warp = True
    directory = _ensure_game_dir(cfg)
    scan = gamefs.scan(
        directory,
        expected_title_id=cfg.game.expected_title_id,
        expected_version=cfg.game.expected_version,
    )
    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    runtime = args.runtime or cfg.runtime.preferred
    assessment = plan.assess(runtime, env, scan, cfg)
    if args.json:
        print(json.dumps(assessment.to_dict(), indent=2))
        return EXIT_OK if assessment.can_run else EXIT_NOT_READY
    if not assessment.can_run:
        print(f"{runtime} is not ready:", file=sys.stderr)
        for blocker in assessment.blockers:
            print(f"  - {blocker.message}", file=sys.stderr)
            if blocker.fix:
                print(f"    fix: {blocker.fix}", file=sys.stderr)
        return EXIT_NOT_READY

    staged = launch.stage_dependencies(assessment, cfg)
    launch_plan = launch.compose(assessment, scan, cfg)
    print(f"runtime : {launch_plan.runtime}")
    print(f"command : {launch_plan.display()}")
    print(f"log     : {launch_plan.log_path}")
    for staged_file in staged:
        print(f"staged  : {staged_file}")
    for note in launch_plan.notes:
        print(f"note    : {note}")
    if args.dry_run:
        print("dry run: not starting the title")
        return EXIT_OK
    code = launch.execute(launch_plan, timeout=args.timeout or cfg.launch.timeout)
    print(launch.summary(launch_plan, code, cfg))
    return EXIT_OK if code == 0 else EXIT_RUNTIME_FAILED


def cmd_report(args) -> int:
    cfg = _cfg(args)
    directory = _ensure_game_dir(cfg)
    scan = gamefs.scan(
        directory,
        expected_title_id=cfg.game.expected_title_id,
        expected_version=cfg.game.expected_version,
    )
    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    assessments = plan.assess_all(env, scan, cfg)
    manifest_report = None
    manifest = cfg.manifest_path()
    if scan.directory and manifest and Path(manifest).is_file():
        manifest_report = gamefs.verify_manifest(scan.directory, manifest)
    payload = {
        "config": str(cfg.path) if cfg.path else None,
        "environment": env.to_dict(),
        "disk_free_gib": doctor.disk_free_gib(cfg.game.root),
        "game": scan.to_dict(),
        "manifest": manifest_report.to_dict() if manifest_report else None,
        "runtimes": [a.to_dict() for a in assessments],
        "selected": plan.pick(assessments, cfg.runtime.preferred).runtime,
    }
    out = Path(args.out) if args.out else cfg.logs_dir / "report.json"
    util.write_json(str(out), payload)
    print(json.dumps(payload, indent=2) if not args.quiet else f"report written to {out}")
    if args.out:
        print(f"report written to {out}")
    return EXIT_OK if scan.ok else EXIT_INVALID_GAME


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to projectz.toml")
    common.add_argument("--json", action="store_true", help="machine-readable output")

    parser = argparse.ArgumentParser(
        prog="projectz",
        description="Locate, validate, plan, build and launch the GTA VI console build on Windows.",
    )
    parser.add_argument("--config", dest="global_config", help="path to projectz.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("locate", parents=[common], help="find game dumps under the configured root")
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser("validate", parents=[common], help="validate identity, archives and manifest")
    p.add_argument("--game", help="game directory (defaults to the configured one)")
    p.add_argument("--manifest", help=".torrent file to verify against")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("doctor", parents=[common], help="report hardware and toolchain readiness")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("plan", parents=[common], help="show which runtime can run and what blocks it")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("build", parents=[common], help="build the selected runtime")
    p.add_argument("--runtime", choices=plan.RUNTIMES)
    p.add_argument("--diag", action="store_true", help="diagnostics profile")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("launch", parents=[common], help="start the title through the selected runtime")
    p.add_argument("--runtime", choices=plan.RUNTIMES)
    p.add_argument("--warp", action="store_true", help="software D3D12 adapter (safe diagnostics)")
    p.add_argument("--timeout", type=int, default=0, help="stop the title after N seconds")
    p.add_argument("--dry-run", action="store_true", help="print the command without starting it")
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("report", parents=[common], help="write one JSON report of everything")
    p.add_argument("--out", help="output path")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "config", None) is None and getattr(args, "global_config", None):
        args.config = args.global_config
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_NOT_READY
