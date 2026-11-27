"""Tests for the Project Kalaga tooling.

Run from the repository root:

    python -m unittest discover -s tests -v

A real 200 GiB dump is validated only when KALAGA_REAL_GAME points at it.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from kalaga import cli, config, doctor, gamefs, launch, plan

GAME_CONFIG = """\ufeff<?xml version="1.0" encoding="utf-8"?>
<Game configVersion="1">
  <MSAAppId>000000004060F900</MSAAppId>
  <TitleId>7952987A</TitleId>
  <StoreId>9NL3WWNZLZZN</StoreId>
  <Identity Name="RockstarGamesInc.28872443D20A7" Version="1.0.2.1" />
  <ShellVisuals DefaultDisplayName="Grand Theft Auto VI" PublisherDisplayName="Rockstar Games" />
  <ExecutableList>
    <Executable Name="game_scarlett_master.exe" Id="GTAO" TargetDeviceFamily="Scarlett" />
  </ExecutableList>
</Game>
"""


def bencode(value) -> bytes:
    if isinstance(value, bool):
        raise TypeError("bool is not a bencode type")
    if isinstance(value, int):
        return b"i%de" % value
    if isinstance(value, str):
        value = value.encode()
    if isinstance(value, bytes):
        return b"%d:%s" % (len(value), value)
    if isinstance(value, list):
        return b"l" + b"".join(bencode(v) for v in value) + b"e"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0] if isinstance(kv[0], bytes) else str(kv[0]).encode())
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise TypeError(type(value))


def make_game(root: Path, *, magic: bytes = gamefs.RPF9_MAGIC, version: str = "1.0.2.1") -> Path:
    game = root / "GTA6.Xbox.v1.0.2.1"
    (game / "data" / "ttdb").mkdir(parents=True)
    (game / "pack" / "story000").mkdir(parents=True)
    cfg = GAME_CONFIG.replace('Version="1.0.2.1"', f'Version="{version}"')
    (game / "MicrosoftGame.Config").write_text(cfg, encoding="utf-8")
    (game / "game_scarlett_master.exe").write_bytes(b"MZ" + b"\0" * 62)
    (game / "common.rpf").write_bytes(magic + b"payload")
    (game / "pack" / "story000" / "story000.rpf").write_bytes(magic + b"more")
    (game / "data" / "ttdb" / "x.ttpf").write_bytes(b"data")
    return game


def make_environment(*, cargo=True, link=True, dxc=True) -> doctor.Environment:
    env = doctor.Environment(gpu="test gpu", ram_gib=32.0)
    env.tools = {
        "cargo": doctor.ToolInfo("cargo", "cargo" if cargo else None, "1.98.1"),
        "rustc": doctor.ToolInfo("rustc", "rustc" if cargo else None, "1.98.1"),
        "link": doctor.ToolInfo("link", "link" if link else None, "14.0"),
        "dxcompiler": doctor.ToolInfo("dxcompiler", "dxcompiler.dll" if dxc else None),
    }
    env.dxcompiler = "dxcompiler.dll" if dxc else ""
    return env


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class IdentityTests(TempCase):
    def test_reads_identity_with_bom(self) -> None:
        game = make_game(self.root)
        ident = gamefs.read_identity(game)
        self.assertEqual(ident.title_id, "7952987A")
        self.assertEqual(ident.version, "1.0.2.1")
        self.assertEqual(ident.name, "Grand Theft Auto VI")
        self.assertEqual(ident.publisher, "Rockstar Games")
        self.assertEqual(ident.executable, "game_scarlett_master.exe")
        self.assertTrue(ident.complete)

    def test_missing_config_is_empty_not_exception(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        ident = gamefs.read_identity(empty)
        self.assertFalse(ident.complete)


class ScanTests(TempCase):
    def test_valid_dump(self) -> None:
        game = make_game(self.root)
        scan = gamefs.scan(game, expected_title_id="7952987A", expected_version="1.0.2.1")
        self.assertTrue(scan.ok, [str(i) for i in scan.issues])
        self.assertEqual(len(scan.rpf_paths), 2)
        self.assertEqual(len(scan.entry_points), 1)
        self.assertEqual(scan.file_count, 5)
        self.assertGreater(scan.total_bytes, 0)
        self.assertFalse(scan.bad_archives)

    def test_bad_archive_magic_is_an_error(self) -> None:
        game = make_game(self.root, magic=b"PK\x03\x04")
        scan = gamefs.scan(game)
        codes = {issue.code for issue in scan.errors}
        self.assertIn("bad-archive", codes)
        self.assertFalse(scan.ok)

    def test_version_mismatch_is_an_error(self) -> None:
        game = make_game(self.root, version="1.0.0.0")
        scan = gamefs.scan(game, expected_version="1.0.2.1")
        self.assertIn("version-mismatch", {i.code for i in scan.errors})

    def test_missing_exe_is_an_error(self) -> None:
        game = make_game(self.root)
        (game / "game_scarlett_master.exe").unlink()
        scan = gamefs.scan(game)
        self.assertIn("exe-missing", {i.code for i in scan.errors})

    def test_missing_directory_is_a_warning(self) -> None:
        game = make_game(self.root)
        shutil.rmtree(game / "pack")
        scan = gamefs.scan(game)
        self.assertIn("missing-dir", {i.code for i in scan.warnings})
        self.assertTrue(scan.ok)

    def test_find_games_walks_into_subdirectories(self) -> None:
        make_game(self.root / "nested")
        found = gamefs.find_games(self.root)
        self.assertEqual(len(found), 1)
        self.assertTrue((found[0] / "MicrosoftGame.Config").is_file())


class ManifestTests(TempCase):
    def test_report_compares_names_and_sizes(self) -> None:
        game = make_game(self.root)
        torrent = self.root / "release.torrent"
        info = {
            b"name": b"GTA6.Xbox.v1.0.2.1",
            b"files": [
                {b"path": [b"common.rpf"], b"length": 11},
                {b"path": [b"pack", b"story000", b"story000.rpf"], b"length": 8},
                {b"path": [b"missing.rpf"], b"length": 5},
                {b"path": [b"data", b"ttdb", b"x.ttpf"], b"length": 999},
            ],
        }
        torrent.write_bytes(bencode({b"info": info}))
        report = gamefs.verify_manifest(game, torrent)
        self.assertEqual(report.expected_files, 4)
        self.assertEqual(report.present, 3)
        self.assertEqual([m[0] for m in report.missing], ["missing.rpf"])
        self.assertEqual(len(report.wrong_size), 1)
        self.assertFalse(report.exact)
        self.assertIn("game_scarlett_master.exe", report.extra)

    def test_exact_manifest(self) -> None:
        game = make_game(self.root)
        torrent = self.root / "release.torrent"
        entries = []
        for current, _dirs, files in os.walk(game):
            for filename in files:
                path = Path(current) / filename
                parts = list(path.relative_to(game).parts)
                entries.append(
                    {b"path": [p.encode() for p in parts], b"length": path.stat().st_size}
                )
        info = {b"name": b"GTA6.Xbox.v1.0.2.1", b"files": entries}
        torrent.write_bytes(bencode({b"info": info}))
        report = gamefs.verify_manifest(game, torrent)
        self.assertTrue(report.exact, report.to_dict())
        self.assertEqual(report.extra, [])
        self.assertEqual(report.expected_bytes, report.actual_bytes)

    def test_unreadable_manifest_does_not_raise(self) -> None:
        game = make_game(self.root)
        torrent = self.root / "broken.torrent"
        torrent.write_bytes(b"not bencode")
        report = gamefs.verify_manifest(game, torrent)
        self.assertEqual(report.present, 0)
        self.assertIn("unreadable", report.release)


class ConfigTests(TempCase):
    def test_loads_values_and_defaults(self) -> None:
        path = self.root / "kalaga.toml"
        path.write_text(
            "[game]\n"
            f"dir = '{self.root / 'game'}'\n"
            "expected_version = '1.0.2.1'\n"
            "[runtime]\n"
            "preferred = 'XCL'\n"
            "[launch]\n"
            "warp = true\n"
            "extra_env = { VICTORY_LOG = 'trace' }\n",
            encoding="utf-8",
        )
        cfg = config.load(path)
        self.assertEqual(cfg.game.expected_title_id, "7952987A")
        self.assertEqual(cfg.runtime.preferred, "xcl")
        self.assertEqual(cfg.runtime.xcl_dir, config.DEFAULT_XCL_DIR)
        self.assertTrue(cfg.launch.warp)
        self.assertEqual(cfg.launch.extra_env["VICTORY_LOG"], "trace")

    def test_missing_file_falls_back_to_defaults(self) -> None:
        cfg = config.load(self.root / "absent.toml")
        self.assertIsNone(cfg.path)
        self.assertEqual(cfg.runtime.preferred, "victory")


class PlanTests(TempCase):
    def _runtime(self, name: str) -> Path:
        runtime = self.root / name
        (runtime / "target" / "release").mkdir(parents=True)
        (runtime / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        (runtime / "target" / "release" / "victory.exe").write_bytes(b"MZ")
        return runtime

    def _cfg(self, runtime: Path) -> config.Config:
        cfg = config.Config()
        cfg.runtime.victory_dir = str(runtime)
        cfg.runtime.xcl_dir = str(runtime)
        cfg.logs_dir = self.root / "logs"
        return cfg

    def test_victory_ready_when_everything_present(self) -> None:
        runtime = self._runtime("victory")
        game = make_game(self.root)
        scan = gamefs.scan(game)
        cfg = self._cfg(runtime)
        result = plan.assess("victory", make_environment(), scan, cfg)
        self.assertTrue(result.can_build, result.blockers)
        self.assertTrue(result.can_run, result.blockers)
        self.assertTrue(result.notes)

    def test_missing_linker_blocks_build(self) -> None:
        runtime = self._runtime("victory")
        game = make_game(self.root)
        cfg = self._cfg(runtime)
        result = plan.assess("victory", make_environment(link=False), gamefs.scan(game), cfg)
        self.assertFalse(result.can_build)
        self.assertIn("no-linker", {b.code for b in result.blockers})
        self.assertFalse(result.can_run)

    def test_missing_dxcompiler_blocks_run(self) -> None:
        runtime = self._runtime("victory")
        game = make_game(self.root)
        cfg = self._cfg(runtime)
        result = plan.assess("victory", make_environment(dxc=False), gamefs.scan(game), cfg)
        self.assertIn("no-dxcompiler", {b.code for b in result.blockers})
        self.assertFalse(result.can_run)

    def test_unbuilt_runtime_is_only_a_warning(self) -> None:
        runtime = self._runtime("victory")
        (runtime / "target" / "release" / "victory.exe").unlink()
        game = make_game(self.root)
        cfg = self._cfg(runtime)
        result = plan.assess("victory", make_environment(), gamefs.scan(game), cfg)
        self.assertTrue(result.can_build)
        self.assertIn("not-built", {b.code for b in result.warnings})

    def test_invalid_game_blocks_every_runtime(self) -> None:
        runtime = self._runtime("victory")
        game = make_game(self.root, magic=b"XXXX")
        cfg = self._cfg(runtime)
        result = plan.assess("victory", make_environment(), gamefs.scan(game), cfg)
        self.assertIn("game", {b.code for b in result.blockers})
        self.assertFalse(result.can_run)

    def test_target_triple_layout_is_found(self) -> None:
        runtime = self._runtime("victory")
        target_exe = runtime / "target" / "x86_64-pc-windows-gnullvm" / "release" / "victory.exe"
        target_exe.parent.mkdir(parents=True)
        target_exe.write_bytes(b"MZ")
        (runtime / "target" / "release" / "victory.exe").unlink()
        cfg = self._cfg(runtime)
        cfg.runtime.target = "x86_64-pc-windows-gnullvm"
        cfg.runtime.toolchain = "1.98.1-x86_64-pc-windows-gnu"
        result = plan.assess("victory", make_environment(), gamefs.scan(make_game(self.root)), cfg)
        self.assertEqual(result.executable, target_exe)
        self.assertIn("--target", result.build_command)
        self.assertIn("x86_64-pc-windows-gnullvm", result.build_command)
        self.assertIn("+1.98.1-x86_64-pc-windows-gnu", result.build_command)

    def test_pick_prefers_configured_runtime(self) -> None:
        runtime = self._runtime("victory")
        game = make_game(self.root)
        cfg = self._cfg(runtime)
        assessments = plan.assess_all(make_environment(), gamefs.scan(game), cfg)
        chosen = plan.pick(assessments, "victory")
        self.assertEqual(chosen.runtime, "victory")
        self.assertTrue(chosen.can_run)


class LaunchTests(TempCase):
    def _setup(self):
        runtime = self.root / "victory"
        (runtime / "target" / "release").mkdir(parents=True)
        (runtime / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        exe = runtime / "target" / "release" / "victory.exe"
        exe.write_bytes(b"MZ")
        game = make_game(self.root)
        cfg = config.Config()
        cfg.runtime.victory_dir = str(runtime)
        cfg.logs_dir = self.root / "logs"
        scan = gamefs.scan(game)
        assessment = plan.assess("victory", make_environment(), scan, cfg)
        self.assertTrue(assessment.can_run, assessment.blockers)
        return cfg, scan, assessment

    def test_command_shape(self) -> None:
        cfg, scan, assessment = self._setup()
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.argv[1:3], ["run", str(scan.entry_points[0])])
        self.assertIn("--execute", result.argv)
        self.assertEqual(result.argv[result.argv.index("--console") + 1], "series-x")
        self.assertEqual(result.env["VICTORY_LOG"], "info")
        self.assertNotIn("VICTORY_D3D12_WARP", result.env)
        self.assertTrue(result.log_path.parent.is_dir())

    def test_warp_flag_sets_env(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.warp = True
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.env["VICTORY_D3D12_WARP"], "1")

    def test_extra_env_and_args_are_appended(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.extra_env = {"VICTORY_GPU_TIMING": "1"}
        cfg.launch.extra_args = ["--strict"]
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.env["VICTORY_GPU_TIMING"], "1")
        self.assertEqual(result.argv[-1], "--strict")

    def test_preset_sets_console_and_switches(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-belobug-fast"
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.argv[result.argv.index("--console") + 1], "series-s")
        self.assertEqual(result.env["VICTORY_PORT_DESCRIPTORS"], "1")
        self.assertNotIn("VICTORY_TEXTURE_ROOM_PERCENT", result.env)
        self.assertTrue(any("rx7600-belobug-fast" in note for note in result.notes))

    def test_explicit_console_and_extra_env_beat_the_preset(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-belobug"
        cfg.launch.console = "series-x"
        cfg.launch.extra_env = {"VICTORY_WINDOW_BUDGET_MB": "1024", "VICTORY_LOG": "trace"}
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.argv[result.argv.index("--console") + 1], "series-x")
        self.assertEqual(result.env["VICTORY_WINDOW_BUDGET_MB"], "1024")
        self.assertEqual(result.env["VICTORY_LOG"], "trace")

    def test_preset_drops_inherited_switches_but_keeps_paths(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-belobug"
        saved = dict(os.environ)
        os.environ["VICTORY_SKIP_PIPELINES"] = "072f5fe96efd27e1"
        os.environ["VICTORY_DATA_DIR"] = "D:\\victory-data"
        try:
            result = launch.compose(assessment, scan, cfg)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.assertNotIn("VICTORY_SKIP_PIPELINES", result.env)
        self.assertEqual(result.env["VICTORY_DATA_DIR"], "D:\\victory-data")
        self.assertTrue(any("VICTORY_SKIP_PIPELINES" in note for note in result.notes))

    def test_no_preset_keeps_inherited_switches(self) -> None:
        cfg, scan, assessment = self._setup()
        saved = dict(os.environ)
        os.environ["VICTORY_SKIP_PIPELINES"] = "072f5fe96efd27e1"
        try:
            result = launch.compose(assessment, scan, cfg)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.assertEqual(result.env["VICTORY_SKIP_PIPELINES"], "072f5fe96efd27e1")

    def test_fork_preset_is_the_measured_config(self) -> None:
        from kalaga import presets
        preset = presets.get("rx7600-fork")
        self.assertEqual(preset.console, "series-x")
        self.assertNotIn("VICTORY_TEXTURE_NO_WAIT", preset.env)

    def test_fork_preset_carries_the_amd_skips(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-fork"
        result = launch.compose(assessment, scan, cfg)
        skips = result.env["VICTORY_SKIP_PIPELINES"].split(",")
        self.assertEqual(len(skips), 43)
        self.assertNotIn("VICTORY_PORT_CBV", result.env)

    def test_quality_preset_is_series_x_at_1080p(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-belobug-quality"
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.argv[result.argv.index("--console") + 1], "series-x")
        self.assertEqual(result.env["VICTORY_OUTPUT"], "1920x1080")
        self.assertEqual(result.env["VICTORY_RENDER_SCALE"], "1.0")
        self.assertEqual(result.env["VICTORY_PIPELINE_BOOK"], "1")
        self.assertEqual(result.env["VICTORY_WINDOW_BUDGET_MB"], "1536")

    def test_only_the_six_core_preset_sizes_pools(self) -> None:
        from kalaga import presets
        for name, preset in presets.PRESETS.items():
            env = presets.environment(preset)
            self.assertEqual("VICTORY_THIN_THREADS" in env, name == "rx7600-belobug-6core", name)
            self.assertNotIn("VICTORY_PIPELINE_WORKERS", env, name)
            self.assertNotIn("VICTORY_VIEW_THREADS", env, name)

    def test_8gb_presets_cap_textures_but_not_card_buffers(self) -> None:
        from kalaga import presets
        for name, preset in presets.PRESETS.items():
            env = presets.environment(preset)
            if preset.checkout in ("rdna", "belobug"):
                # The family already defaults card buffers to 512 MiB on 8 GB.
                self.assertNotIn("VICTORY_CARD_BUFFERS_MB", env, name)
                want = "4608" if preset.console == "series-x" else "5120"
                self.assertEqual(env.get("VICTORY_TEXTURE_BUDGET_MB"), want, name)

    def test_rdna_preset_carries_its_fast_set(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx7600-rdna"
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.argv[result.argv.index("--console") + 1], "series-s")
        self.assertEqual(result.env["VICTORY_PORT_BUFFERS"], "1")
        self.assertEqual(result.env["VICTORY_INPLACE"], "2")

    def test_unknown_preset_is_an_error(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.launch.preset = "rx9999"
        with self.assertRaises(RuntimeError):
            launch.compose(assessment, scan, cfg)

    def test_preset_is_read_from_config(self) -> None:
        path = self.root / "kalaga.toml"
        path.write_text("[launch]\npreset = 'rx7600-belobug'\n", encoding="utf-8")
        cfg = config.load(path)
        self.assertEqual(cfg.launch.preset, "rx7600-belobug")
        self.assertEqual(cfg.launch.console, "")

    def test_stage_dependencies_copies_dxc_once(self) -> None:
        cfg, scan, assessment = self._setup()
        dxc = self.root / "dxc"
        dxc.mkdir()
        (dxc / "dxcompiler.dll").write_bytes(b"x" * 16)
        (dxc / "dxil.dll").write_bytes(b"y" * 8)
        cfg.runtime.dxc_dir = str(dxc)
        staged = launch.stage_dependencies(assessment, cfg)
        self.assertEqual(len(staged), 2)
        self.assertTrue((assessment.executable.parent / "dxcompiler.dll").is_file())
        self.assertEqual(launch.stage_dependencies(assessment, cfg), [])

    def test_runs_from_source_checkout_with_explicit_config(self) -> None:
        cfg, scan, assessment = self._setup()
        runtime_toml = Path(cfg.runtime.victory_dir) / "victory.toml"
        runtime_toml.write_text("[paths]\n", encoding="utf-8")
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.cwd, str(Path(cfg.runtime.victory_dir)))
        self.assertEqual(result.env["VICTORY_CONFIG"], str(runtime_toml))

    def test_dxc_dir_is_exported(self) -> None:
        cfg, scan, assessment = self._setup()
        cfg.runtime.dxc_dir = r"D:\projectz-deps\dxc"
        result = launch.compose(assessment, scan, cfg)
        self.assertEqual(result.env["VICTORY_DXC_DIR"], cfg.runtime.dxc_dir)
        self.assertEqual(result.env["XCL_DXC_DIR"], cfg.runtime.dxc_dir)

    def test_compose_without_binary_raises(self) -> None:
        cfg, scan, assessment = self._setup()
        assessment.executable = None
        with self.assertRaises(RuntimeError):
            launch.compose(assessment, scan, cfg)


class CliTests(TempCase):
    def _config(self, game: Path) -> Path:
        path = self.root / "kalaga.toml"
        path.write_text(
            f"[game]\ndir = '{game}'\nmanifest = ''\n[runtime]\nvictory_dir = '{self.root / 'nope'}'\n",
            encoding="utf-8",
        )
        return path

    def _run(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_validate_ok(self) -> None:
        game = make_game(self.root)
        cfg = self._config(game)
        code, out = self._run(["validate", "--config", str(cfg), "--game", str(game)])
        self.assertEqual(code, 0, out)
        self.assertIn("result     : OK", out)

    def test_validate_fails_on_bad_dump(self) -> None:
        game = make_game(self.root, magic=b"ZZZZ")
        cfg = self._config(game)
        code, out = self._run(["validate", "--config", str(cfg), "--game", str(game)])
        self.assertEqual(code, cli.EXIT_INVALID_GAME, out)
        self.assertIn("INVALID", out)

    def test_locate_json(self) -> None:
        game = make_game(self.root / "root")
        cfg_path = self.root / "locate.toml"
        cfg_path.write_text(
            f"[game]\nroot = '{self.root / 'root'}'\n", encoding="utf-8"
        )
        code, out = self._run(["locate", "--config", str(cfg_path), "--json"])
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title_id"], "7952987A")
        self.assertTrue(payload[0]["matches_expected"])

    def test_launch_without_build_reports_blockers(self) -> None:
        game = make_game(self.root)
        cfg = self._config(game)
        code, out = self._run(["launch", "--config", str(cfg), "--runtime", "victory", "--dry-run"])
        self.assertEqual(code, cli.EXIT_NOT_READY, out)
        self.assertIn("not ready", out)

    def test_report_writes_json(self) -> None:
        game = make_game(self.root)
        cfg = self._config(game)
        out_path = self.root / "report.json"
        code, out = self._run(["report", "--config", str(cfg), "--out", str(out_path), "--quiet"])
        self.assertEqual(code, 0, out)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["game"]["identity"]["title_id"], "7952987A")
        self.assertTrue(payload["game"]["ok"])
        self.assertEqual(len(payload["runtimes"]), 2)


@unittest.skipUnless(
    os.environ.get("KALAGA_REAL_GAME"),
    "set KALAGA_REAL_GAME to a real dump to run the integration check",
)
class RealDumpTests(unittest.TestCase):
    def test_real_dump_validates(self) -> None:
        scan = gamefs.scan(
            os.environ["KALAGA_REAL_GAME"],
            expected_title_id="7952987A",
            expected_version="1.0.2.1",
        )
        self.assertTrue(scan.ok, [str(i) for i in scan.issues])
        self.assertGreaterEqual(len(scan.rpf_paths), 20)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
