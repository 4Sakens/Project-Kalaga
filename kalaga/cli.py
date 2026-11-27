"""Command line interface: ``python -m kalaga <command>``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import config, doctor, gamefs, launch, plan, presets, session, upstream, util

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
            print(f"no game found under {cfg.game.root} (set game.dir in kalaga.toml)")
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
    if args.preset:
        cfg.launch.preset = args.preset
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
    try:
        code = launch.execute(launch_plan, timeout=args.timeout or cfg.launch.timeout)
    except KeyboardInterrupt:
        print("\nstopped (Ctrl+C); the title was ended")
        code = 130
    except OSError as exc:
        print(f"could not start {launch_plan.argv[0]}: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_FAILED
    print(launch.summary(launch_plan, code, cfg))
    return EXIT_OK if code == 0 else EXIT_RUNTIME_FAILED


DEFAULT_SESSION = {
    "rdna": ["rx7600-rdna", "rx7600-rdna-6core", "rx7600-rdna-balanced", "rx7600-rdna-quality"],
    "belobug": ["rx7600-belobug", "rx7600-belobug-6core", "rx7600-belobug-fast"],
    "fork": ["rx7600-fork"],
}


def cmd_session(args) -> int:
    """Run several presets back to back and write one comparison table."""

    import time
    import zipfile

    cfg = _cfg(args)
    if args.presets:
        names = [n.strip() for n in args.presets.split(",") if n.strip()]
    else:
        names = DEFAULT_SESSION[args.checkout]
    for name in names:
        presets.get(name)  # unknown names fail before anything starts
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
    assessment = plan.assess("victory", env, scan, cfg)
    if not assessment.can_run:
        print("victory is not ready:", file=sys.stderr)
        for blocker in assessment.blockers:
            print(f"  - {blocker.message}", file=sys.stderr)
        return EXIT_NOT_READY
    launch.stage_dependencies(assessment, cfg)
    wrong = [n for n in names if presets.get(n).checkout != args.checkout]
    if wrong:
        print(f"note    : {', '.join(wrong)} are for another checkout than --checkout {args.checkout}; "
              "their switches may do nothing here")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = cfg.logs_dir / f"session-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_seconds = int(args.minutes * 60) + args.load_seconds
    print(f"session : {len(names)} runs of ~{run_seconds // 60} min each "
          f"({args.minutes:g} min in the world + {args.load_seconds} s to load); results in {out_dir}")
    print("          Play the same stretch every run (same save, same route), so the runs compare.")
    results: list[session.Result] = []
    shots: dict[int, str | None] = {}
    queue = [(name, False) for name in names]
    i = 0
    while queue:
        name, is_retry = queue.pop(0)
        if not is_retry:
            i += 1
        cfg.launch.preset = name
        launch_plan = launch.compose(assessment, scan, cfg)
        if not args.no_pause:
            try:
                input(f"\n[{i}/{len(names)}] {name}: press Enter to start (Ctrl+C to stop the session) ")
            except (EOFError, KeyboardInterrupt):
                print("\nstopped")
                break
        print(f"[{i}/{len(names)}] {name}: running {run_seconds} s, log {launch_plan.log_path}")
        sampler = session.MemorySampler()
        shot_name = f"{i:02d}-{name}{'-retry' if is_retry else ''}.png"
        shooter = session.ScreenShooter(out_dir / shot_name, after=args.shot_after)
        if args.shot_after > 0:
            print(f"          stand still in your spot from loading in: the screenshot is taken "
                  f"{args.shot_after} s into the world")
        stop_session = False
        try:
            code = launch.execute(launch_plan, timeout=run_seconds, on_spawn=sampler.start, echo=False,
                                  on_line=shooter.feed if args.shot_after > 0 else None)
        except KeyboardInterrupt:
            print("\n          stopped (Ctrl+C): this run is kept, the rest are skipped")
            code, stop_session = 130, True
        except OSError as exc:
            print(f"          could not start {launch_plan.argv[0]}: {exc}", file=sys.stderr)
            code = f"did not start ({exc.__class__.__name__})"
        ram, vram = sampler.stop()
        shots[len(results)] = shot_name if args.shot_after > 0 and shooter.finish() else None
        try:
            text = launch_plan.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        result = session.Result(name, session.parse(text), ram, vram,
                                session.exit_label(code, text), str(launch_plan.log_path))
        results.append(result)
        st = result.stats()
        if st.get("world_s"):
            print(f"          {st['fps_median']:.1f} fps median over {st['world_s']} s in the world, "
                  f"{result.bound()}-bound, {st['hitches']} hitches")
        else:
            print(f"          never reached the world (exit {result.exit_code}); see the log")
        if stop_session:
            break
        crashed = result.exit_code not in ("time up", 0)
        if crashed and not is_retry and not args.no_retry:
            safe = presets.safe_variant(presets.get(name))
            if safe is not None:
                print(f"          crashed: retrying once as {safe.name} (the newer fast ways left out)")
                queue.insert(0, (safe.name, True))
    if not results:
        return EXIT_RUNTIME_FAILED

    summary = out_dir / "summary.md"
    lines = [f"# Kalaga session {stamp}", "", session.table(results), "",
             "fps from the runtime's once-a-second frame line, seconds with over 1,000 draws only. "
             "Bound: which of preparing (CPU) and waiting on the GPU is 20 % longer. "
             "Peak RAM: the game's private bytes; peak VRAM: its dedicated GPU memory "
             "(sampled every 20 s, Windows only).", ""]
    for r in results:
        lines.append(f"- `{r.preset}`: {presets.get(r.preset).summary} — log `{r.log}`")
    taken = [(r, shots.get(n)) for n, r in enumerate(results) if shots.get(n)]
    if taken:
        lines += ["", "## Side by side", "",
                  f"The screen {args.shot_after} s into the world in each run (same spot, standing "
                  "still). Fuzzy on one and sharp on another: that preset's render scale or console "
                  "is the cause; black patches on all of them: the runtime.", ""]
        for r, shot in taken:
            lines += [f"### {r.preset}", "", f"![{r.preset}]({shot})", ""]
    elif args.shot_after > 0 and sys.platform == "win32":
        lines += ["", "No screenshots were saved (no run reached "
                  f"{args.shot_after} s in the world, or the screen copy failed).", ""]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bundle = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(summary, f"session-{stamp}/summary.md")
        for r in results:
            if Path(r.log).is_file():
                z.write(r.log, f"session-{stamp}/{Path(r.log).name}")
        for _, shot in taken:
            z.write(out_dir / shot, f"session-{stamp}/{shot}")
        crashes = launch.crash_log(env, cfg)
        if crashes.is_file():
            z.writestr(f"session-{stamp}/crashes-tail.log", launch.tail(crashes, 200))
    ranks = {r.preset: session.picture_rank(presets.environment(presets.get(r.preset)),
                                            presets.get(r.preset).console)
             for r in results}
    pick = session.choose(results, ranks)
    pick_lines = ["", "## Pick", "", f"**{pick.preset or 'none'}**: {pick.why}"]
    pick_lines += [f"- dropped `{name}`: {reason}" for name, reason in pick.dropped]
    with summary.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(pick_lines) + "\n")
    print()
    print(session.table(results))
    print(f"\npick    : {pick.preset or 'none'} ({pick.why})")
    for name, reason in pick.dropped:
        print(f"dropped : {name}: {reason}")
    if pick.preset and args.apply:
        if cfg.path and Path(cfg.path).is_file():
            path = Path(cfg.path)
            path.write_text(session.set_preset_in_config(path.read_text(encoding="utf-8"), pick.preset),
                            encoding="utf-8")
            print(f"applied : [launch] preset = '{pick.preset}' in {path}")
        else:
            print("applied : no kalaga.toml to write to; set [launch] preset by hand")
    elif pick.preset:
        print(f"          to use it: python -m kalaga session --apply next time, or set "
              f"[launch] preset = '{pick.preset}'")
    print(f"\nsummary : {summary}\nsend    : {bundle}")
    return EXIT_OK


def cmd_bug(args) -> int:
    """Zip what a bug needs: logs, preset and switches, runtime build, frame stats."""

    import time
    import zipfile

    cfg = _cfg(args)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    bundle = Path(args.out) if args.out else cfg.logs_dir / f"bug-{stamp}.zip"
    root = f"bug-{stamp}"
    notes: list[str] = [f"# Kalaga bug report {stamp}", ""]
    if args.what:
        notes += ["## What happened", "", args.what, ""]

    # The runs: newest runtime logs, the one the bug is in first.
    logs = sorted(
        (p for p in cfg.logs_dir.glob("*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )[: max(1, args.logs)]
    preset_name = cfg.launch.preset or ""
    notes += ["## Setup", "", f"- preset: `{preset_name or '(none)'}`"]
    if preset_name:
        try:
            preset = presets.get(preset_name)
            notes.append(f"- checkout: {preset.checkout}, console: {preset.console}")
            notes += ["", "Switches:", "", "```"]
            notes += [f"{k}={v}" for k, v in sorted(presets.environment(preset).items())]
            notes += ["```"]
        except KeyError:
            notes.append("- (that preset is not known to this Kalaga)")
    victory_dir = Path(cfg.runtime.victory_dir) if cfg.runtime.victory_dir else None
    if victory_dir and (victory_dir / ".git").is_dir():
        _, head, _ = util.run(["git", "-C", str(victory_dir), "log", "-1", "--format=%H %cd %s", "--date=iso"])
        _, branch, _ = util.run(["git", "-C", str(victory_dir), "rev-parse", "--abbrev-ref", "HEAD"])
        _, origin, _ = util.run(["git", "-C", str(victory_dir), "remote", "get-url", "origin"])
        _, dirty, _ = util.run(["git", "-C", str(victory_dir), "status", "--porcelain", "--untracked-files=no"])
        notes += ["", f"- runtime: {origin.strip()} on `{branch.strip()}`", f"- HEAD: {head.strip()}",
                  f"- local changes: {'yes' if dirty.strip() else 'none'}"]
        applied = upstream.applied_fingerprint(victory_dir)
        for name in upstream.runtimes():
            series = upstream.load(name)
            if series.repo.lower().rstrip("/").removesuffix(".git") in origin.lower():
                current = upstream.fingerprint(series)
                state = ("this Kalaga's series" if applied == current
                         else "an older series (run Start-Kalaga.bat to patch again)" if applied
                         else "unknown (not patched by kalaga home)")
                notes.append(f"- patches: {len(series.patches)} in `{name}`; checkout has {state}")
    else:
        notes.append(f"- runtime folder: {victory_dir or '(not set)'}")
    _, kal, _ = util.run(["git", "-C", str(config.REPO_ROOT), "log", "-1", "--format=%h %cd", "--date=iso"])
    notes.append(f"- Kalaga: {kal.strip() or '?'}")

    env = doctor.detect(
        victory_dir=cfg.runtime.victory_dir,
        xcl_dir=cfg.runtime.xcl_dir,
        dxc_dir=cfg.runtime.dxc_dir,
        toolchain_bin=cfg.runtime.toolchain_bin,
    )
    notes += [f"- OS: {env.os_caption} {env.os_version} (build {env.os_build})",
              f"- GPU: {env.gpu or '?'} driver {env.gpu_driver or '?'}", f"- RAM: {env.ram_gib} GiB", ""]

    # The last minute of frame lines of the newest run: what it was doing.
    if logs:
        text = logs[0].read_text(encoding="utf-8", errors="replace")
        result = session.Result(logs[0].stem, session.parse(text))
        st = result.stats()
        last = result.seconds[-60:]
        notes += ["## Newest run", "", f"- log: `{logs[0].name}`, exit: {session.exit_label(None, text)}"]
        if st.get("world_s"):
            notes.append(f"- {st['world_s']} s in the world, median {st['fps_median']:.1f} fps, "
                         f"{st['hitches']} hitches, {result.bound()}-bound")
        if last:
            fps = [s.fps for s in last]
            notes.append(f"- last {len(last)} s: {min(fps):.1f}-{max(fps):.1f} fps, "
                         f"{last[-1].draws} draws/frame, {last[-1].dropped} dropped without a pipeline "
                         f"({last[-1].making} being made)")
        errors = [ln for ln in text.splitlines() if " ERROR " in ln or " WARN " in ln][-40:]
        if errors:
            notes += ["", "Last warnings and errors:", "", "```", *errors, "```"]
        notes.append("")

    crashes = launch.crash_log(env, cfg)
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{root}/report.md", "\n".join(notes) + "\n")
        for log in logs:
            z.write(log, f"{root}/{log.name}")
        if crashes.is_file():
            z.writestr(f"{root}/crashes-tail.log", launch.tail(crashes, 300))
        prepared = cfg.logs_dir / launch.PREPARED_FILE
        if prepared.is_file():
            z.write(prepared, f"{root}/{prepared.name}")
        sessions = sorted(cfg.logs_dir.glob("session-*/summary.md"), key=lambda p: p.stat().st_mtime)
        if sessions:
            z.write(sessions[-1], f"{root}/last-session-summary.md")
        if cfg.path and Path(cfg.path).is_file():
            z.write(cfg.path, f"{root}/kalaga.toml")
    print("\n".join(notes))
    print(f"report  : {bundle}")
    return EXIT_OK


def _fresh_cache_warm_failure(output: str) -> bool:
    """`victory warm` failing only because <cache>\\pipelines does not exist yet."""

    text = output.lower()
    return ("os error 3" in text or "cannot find the path" in text) and (
        "pipelines" in text or "warm-done" in text
    )


def cmd_prepare(args) -> int:
    """Translate every shader and build every recorded pipeline ahead of a run.

    Both are once-per-build costs the runtime otherwise pays mid-game as
    multi-second stalls (upstream: 270-660 s of a session). Neither changes
    the picture.
    """

    cfg = _cfg(args)
    if args.preset:
        cfg.launch.preset = args.preset
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
    assessment = plan.assess("victory", env, scan, cfg)
    if assessment.executable is None:
        print("victory is not built; run `kalaga build` first", file=sys.stderr)
        return EXIT_NOT_READY
    launch.stage_dependencies(assessment, cfg)
    # The same switches as the launch: translations are cached per switch
    # set (VICTORY_PORT_CBV, VICTORY_SHADER_LOOP_LIMIT, ...), so warming
    # with other switches would fill a cache the run never reads.
    preset = presets.get(cfg.launch.preset) if cfg.launch.preset else None
    run_env, notes = launch.victory_env(cfg, preset)
    for note in notes:
        print(f"note    : {note}")
    if not preset:
        print("note    : no preset: the cache matches only launches without one too")
    cwd = str(assessment.executable.parent)
    runtime_toml = Path(cfg.runtime.victory_dir) / "victory.toml"
    if runtime_toml.is_file():
        run_env.setdefault("VICTORY_CONFIG", str(runtime_toml))
        cwd = cfg.runtime.victory_dir
    if scan.directory:
        run_env.setdefault("VICTORY_GAME_DIR", str(scan.directory))
    exe = str(assessment.executable)
    # The files that hold the title's shaders, as every launcher of this code
    # family passes them. With no paths `victory shaders` walks the whole
    # game folder (200+ GiB of archives).
    shader_sources: list[str] = []
    if scan.directory:
        game = Path(scan.directory)
        for name in ("shaders.rpf", None, "XboxBvhBuilder.dll", "amd_fidelityfx_upscaler_xbox.dll"):
            if name is None:
                if scan.entry_points:
                    shader_sources.append(str(scan.entry_points[0]))
                continue
            if (game / name).is_file():
                shader_sources.append(str(game / name))
    steps = []
    if not args.skip_shaders:
        if shader_sources:
            steps.append(("shaders", [exe, "shaders", *shader_sources]))
        else:
            print("note    : no shader sources found in the game folder; skipping `shaders`")
    if not args.skip_warm:
        steps.append(("warm", [exe, "warm"]))
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    for name, argv in steps:
        print(f"$ {' '.join(argv)}  (cwd {cwd})")
        if args.dry_run:
            continue
        rc, out, err = util.run(argv, cwd=cwd, timeout=7200, env=run_env)
        (cfg.logs_dir / f"prepare-{name}.log").write_text(out + err, encoding="utf-8", errors="replace")
        print("\n".join((out + err).splitlines()[-10:]))
        if rc != 0 and name == "warm" and _fresh_cache_warm_failure(out + err):
            # An unpatched runtime's warm fails on a cache no run has written
            # yet: its pipelines folder does not exist (fixed by Belobug #456,
            # patches/*/...-pr456-*). Nothing has been recorded either, so
            # there is nothing to warm.
            print("note    : no pipelines recorded yet (fresh cache); play once, then run prepare again")
            continue
        if rc != 0:
            print(f"{name} failed with exit code {rc}; log at {cfg.logs_dir / f'prepare-{name}.log'}",
                  file=sys.stderr)
            return EXIT_RUNTIME_FAILED
    if args.dry_run:
        print("dry run: nothing started")
    else:
        launch.record_prepared(cfg, assessment.executable, cfg.launch.preset)
        print("prepare OK. `warm` only knows pipelines from runs with VICTORY_PIPELINE_BOOK=1\n"
              "(every rx7600-rdna and rx7600-belobug preset sets it): rerun prepare after\n"
              "the first play session.")
    return EXIT_OK


def cmd_home(args) -> int:
    """Everything for a first evening at the PC, in order; stops at the first failure."""

    import re
    import subprocess

    cfg = _cfg(args)
    checkout = args.checkout
    series = upstream.load(checkout)
    runtime_dir = Path(args.runtime_dir or cfg.runtime.victory_dir or "")
    config_path = Path(cfg.path) if cfg.path else None

    def step(title: str) -> None:
        print(f"\n=== {title}")

    def run(argv: list[str], *, check: bool = True, cwd: str | None = None) -> int:
        print("$ " + " ".join(argv))
        if args.dry_run:
            return 0
        rc = subprocess.call(argv, cwd=cwd)
        if check and rc != 0:
            raise SystemExit(f"\nstopped: `{' '.join(argv)}` failed (exit {rc}). Fix that, then run "
                             "`python -m kalaga home` again: finished steps are skipped or quick.")
        return rc

    def kalaga(*more: str, check: bool = True) -> int:
        argv = [sys.executable, "-m", "kalaga", *more]
        if config_path:
            argv += ["--config", str(config_path)]
        return run(argv, check=check, cwd=str(config.REPO_ROOT))

    if not config_path or not config_path.is_file():
        print("no kalaga.toml: copy kalaga.example.toml to kalaga.toml and set [game] dir first",
              file=sys.stderr)
        return EXIT_NOT_READY
    if not str(runtime_dir).strip() or str(runtime_dir) == ".":
        print("give --runtime-dir (where VIctory-RDNA goes, e.g. D:\\VIctory-RDNA)", file=sys.stderr)
        return EXIT_NOT_READY

    try:
        step("1. Kalaga up to date")
        if not args.no_pull:
            run(["git", "-C", str(config.REPO_ROOT), "pull", "--ff-only"], check=False)

        step(f"2. {checkout} checkout at {runtime_dir}")
        if not (runtime_dir / ".git").is_dir():
            run(["git", "clone", series.repo, str(runtime_dir)])
        else:
            rc, out, _ = util.run(["git", "-C", str(runtime_dir), "remote", "get-url", "origin"])
            if rc == 0 and series.repo.lower().rstrip("/").removesuffix(".git") not in out.lower():
                raise SystemExit(f"\nstopped: {runtime_dir} is a clone of {out.strip()}, not {series.repo}. "
                                 "Give --runtime-dir a new folder.")
        if args.runtime_dir and Path(args.runtime_dir) != Path(cfg.runtime.victory_dir or ""):
            text = config_path.read_text(encoding="utf-8")
            line = f"victory_dir = '{runtime_dir}'"
            if re.search(r"(?m)^\s*victory_dir\s*=", text):
                text = re.sub(r"(?m)^\s*victory_dir\s*=.*$", line.replace("\\", "\\\\"), text, count=1)
            elif "[runtime]" in text:
                text = text.replace("[runtime]", "[runtime]\n" + line, 1)
            else:
                text += f"\n[runtime]\n{line}\n"
            print(f"set [runtime] {line} in {config_path}")
            if not args.dry_run:
                config_path.write_text(text, encoding="utf-8")

        step(f"3. picked upstream fixes ({len(series.patches)} patches) on branch kalaga-prs")
        rc, branch, _ = util.run(["git", "-C", str(runtime_dir), "rev-parse", "--abbrev-ref", "HEAD"])
        current = branch.strip() == "kalaga-prs" and (
            upstream.applied_fingerprint(runtime_dir) == upstream.fingerprint(series)
        )
        if current and not args.repatch:
            print("already on kalaga-prs with this series")
        else:
            if branch.strip() == "kalaga-prs" and not args.repatch:
                print("the patches changed since this checkout was patched: patching it again")
            run(["git", "-C", str(runtime_dir), "fetch", "origin", series.commit], check=False)
            run(["git", "-C", str(runtime_dir), "checkout", "-B", "kalaga-prs", series.commit])
            kalaga("patches", "--runtime", checkout, "--dir", str(runtime_dir), "--strict")
            if not args.dry_run:
                upstream.write_fingerprint(runtime_dir, series)

        step("4. build victory.exe")
        kalaga("build")

        first = f"rx7600-{checkout}-firstrun"
        session_presets = DEFAULT_SESSION[checkout]
        if not args.skip_first_run and first in presets.PRESETS:
            step(f"5. first run ({first}): every pipeline built as the title makes it")
            kalaga("prepare", "--preset", first)
            print(f"   Play {args.first_run_minutes:g} minutes: load your save, walk and drive around. "
                  "It is slower than later runs; that is the point.")
            if not args.dry_run and not args.yes:
                input("   Press Enter to start ")
            kalaga("launch", "--preset", first, "--timeout", str(int(args.first_run_minutes * 60)), check=False)

        step("6. prepare every session preset (translations are cached per switch set)")
        for name in session_presets:
            kalaga("prepare", "--preset", name)

        step(f"7. session: {', '.join(session_presets)}")
        session_args = ["session", "--checkout", checkout, "--apply", "--minutes", f"{args.minutes:g}"]
        if args.yes:
            session_args.append("--no-pause")
        kalaga(*session_args)
    except SystemExit as stop:
        print(stop.code if isinstance(stop.code, str) else "stopped", file=sys.stderr)
        return EXIT_RUNTIME_FAILED
    except KeyboardInterrupt:
        print("\nstopped (Ctrl+C). Run `python -m kalaga home` again to carry on.")
        return EXIT_RUNTIME_FAILED
    print("\nDone. Turn AFMF on now if you want it (docs/amd-settings.md), then play with:\n"
          "    python -m kalaga launch\n"
          "Send logs\\session-<time>.zip for tuning.")
    return EXIT_OK


def cmd_patches(args) -> int:
    """Apply a picked upstream-PR series (patches/<runtime>/) to a checkout."""

    if not args.runtime:
        for name in upstream.runtimes():
            u = upstream.load(name)
            print(f"{name:10} {len(u.patches):3} patches  base {u.repo} {u.branch} @ {u.commit[:12]}")
        print("\nApply one: kalaga patches --runtime NAME [--dir CHECKOUT]")
        return EXIT_OK
    series = upstream.load(args.runtime)
    directory = args.dir or _cfg(args).runtime.victory_dir
    if not directory:
        print("give --dir or set [runtime] victory_dir", file=sys.stderr)
        return EXIT_NOT_READY
    try:
        report = upstream.apply(series, Path(directory))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NOT_READY
    text = report.markdown()
    print(text)
    if not report.base.startswith(series.commit[:12]):
        print(f"\nnote: picked against {series.commit[:12]}; this checkout was at {report.base[:12]}")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n\n")
    if report.failed and args.strict:
        return EXIT_RUNTIME_FAILED
    return EXIT_OK


def cmd_presets(args) -> int:
    if args.json:
        payload = [
            {
                "name": p.name,
                "summary": p.summary,
                "checkout": p.checkout,
                "console": p.console,
                "env": presets.environment(p),
            }
            for p in presets.PRESETS.values()
        ]
        print(json.dumps(payload, indent=2))
        return EXIT_OK
    for p in presets.PRESETS.values():
        print(f"{p.name:22} [{p.checkout}, {p.console}] {p.summary}")
    print("\nUse one with `kalaga launch --preset NAME` or [launch] preset = 'NAME'.")
    print("See docs/hardware-pick.md for why.")
    return EXIT_OK


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
    common.add_argument("--config", help="path to kalaga.toml")
    common.add_argument("--json", action="store_true", help="machine-readable output")

    parser = argparse.ArgumentParser(
        prog="kalaga",
        description="Locate, validate, plan, build and launch the GTA VI console build on Windows.",
    )
    parser.add_argument("--config", dest="global_config", help="path to kalaga.toml")
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
    p.add_argument("--preset", choices=sorted(presets.PRESETS), help="named console + switch set")
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("prepare", parents=[common],
                       help="translate shaders and build recorded pipelines ahead of a run")
    p.add_argument("--preset", choices=sorted(presets.PRESETS),
                   help="the preset you will launch with (default: [launch] preset)")
    p.add_argument("--skip-shaders", action="store_true")
    p.add_argument("--skip-warm", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("patches", parents=[common],
                       help="list or apply the picked upstream-PR series (patches/rdna, patches/belobug)")
    p.add_argument("--runtime", choices=upstream.runtimes() or None)
    p.add_argument("--dir", help="the runtime checkout (default: [runtime] victory_dir)")
    p.add_argument("--strict", action="store_true", help="exit non-zero if any patch did not apply")
    p.add_argument("--summary", help="append the markdown report to this file (CI job summary)")
    p.set_defaults(func=cmd_patches)

    p = sub.add_parser("session", parents=[common],
                       help="run several presets back to back and compare them in one table")
    p.add_argument("--checkout", choices=sorted(DEFAULT_SESSION), default="rdna",
                   help="which runtime [runtime] victory_dir holds (picks the default presets)")
    p.add_argument("--presets", help="comma-separated presets (default: the checkout's three)")
    p.add_argument("--minutes", type=float, default=4.0, help="minutes in the world per run")
    p.add_argument("--load-seconds", type=int, default=150, help="added per run for loading (default 150)")
    p.add_argument("--no-pause", action="store_true", help="do not wait for Enter between runs")
    p.add_argument("--shot-after", type=int, default=20,
                   help="seconds in the world before each run's screenshot (0: none; default 20)")
    p.add_argument("--no-retry", action="store_true",
                   help="do not retry a crashed run with the safe set")
    p.add_argument("--apply", action="store_true",
                   help="write the picked preset into kalaga.toml ([launch] preset)")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("bug", parents=[common],
                       help="zip logs, preset, runtime build and frame stats for a bug report")
    p.add_argument("what", nargs="?", default="", help="one line on what you saw and where")
    p.add_argument("--logs", type=int, default=3, help="newest runtime logs to include (default 3)")
    p.add_argument("--out", help="zip path (default logs/bug-<time>.zip)")
    p.set_defaults(func=cmd_bug)

    p = sub.add_parser("home", parents=[common],
                       help="first evening at the PC: clone, patch, build, prepare, first run, session")
    p.add_argument("--checkout", choices=["rdna", "belobug"], default="rdna")
    p.add_argument("--runtime-dir", help="where the runtime is or goes (default: [runtime] victory_dir)")
    p.add_argument("--minutes", type=float, default=4.0, help="minutes in the world per session run")
    p.add_argument("--first-run-minutes", type=float, default=12.0)
    p.add_argument("--skip-first-run", action="store_true")
    p.add_argument("--repatch", action="store_true", help="rebuild the kalaga-prs branch from the pinned base")
    p.add_argument("--no-pull", action="store_true")
    p.add_argument("--yes", action="store_true", help="no Enter prompts")
    p.add_argument("--dry-run", action="store_true", help="print the steps only")
    p.set_defaults(func=cmd_home)

    p = sub.add_parser("presets", parents=[common], help="list the launch presets")
    p.set_defaults(func=cmd_presets)

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
