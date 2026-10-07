import bz2
import hashlib
import json
import sqlite3
import sys
import types
import zipfile
from pathlib import Path

import pytest

from dota_items.cli import main
from dota_items.normalize import load_timeline
from dota_items.sources.gem_replay import canonicalize_match, ingest_demo, prepared_demo

DEMO = b"PBDEMS2\x00" + b"synthetic-test-replay-bytes"


def fake_match():
    clock = types.SimpleNamespace(game_seconds_at=lambda tick: tick // 30)
    player0 = types.SimpleNamespace(
        player_id=0,
        hero_id=44,
        purchase_log=[
            types.SimpleNamespace(value_name="item_power_treads", game_time_s=420, tick=12600),
            types.SimpleNamespace(value_name="item_tpscroll", game_time_s=None, tick=45000),
            types.SimpleNamespace(value_name="dota_unknown", game_time_s=600, tick=18000),
        ],
    )
    player5 = types.SimpleNamespace(player_id=5, hero_id=2, purchase_log=[])
    return types.SimpleNamespace(
        match_id=42,
        duration=2100,
        game_mode=22,
        players=[player0, player5],
        game_clock=clock,
        post_game_tick=60000,
    )


def install_fake_gem(monkeypatch, calls):
    def parse(path):
        assert Path(path).read_bytes() == DEMO
        calls.append(path)
        return fake_match()

    monkeypatch.setitem(
        sys.modules,
        "gem",
        types.SimpleNamespace(
            parse=parse,
            to_json=lambda match: json.dumps(
                {"match_id": match.match_id, "players": [vars(p) for p in match.players]},
                default=vars,
            ),
        ),
    )
    monkeypatch.setattr(
        "dota_items.sources.gem_capture.parse_with_state", lambda path: (parse(path), [])
    )


@pytest.mark.parametrize(
    "suffix,compress",
    [
        (".dem", lambda payload: payload),
        (".dem.bz2", bz2.compress),
    ],
)
def test_replay_ingestion_initializes_json_sqlite_and_report(
    tmp_path, monkeypatch, suffix, compress
):
    source = tmp_path / f"match{suffix}"
    source.write_bytes(compress(DEMO))
    calls = []
    install_fake_gem(monkeypatch, calls)
    data_dir = tmp_path / "data"
    result = ingest_demo(source, data_dir)
    assert result["status"] == "imported"
    assert result["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["demo_sha256"] == hashlib.sha256(DEMO).hexdigest()
    assert result["players"] == 2
    assert result["item_events"] == 2
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert manifest["parser"] == "gem-dota"
    assert Path(manifest["raw_json"]).is_file()
    normalized = json.loads(Path(result["normalized_json"]).read_text(encoding="utf-8"))
    assert [player["player_slot"] for player in normalized["players"]] == [0, 128]
    assert normalized["players"][0]["purchase_log"][1]["time"] == 1500
    assert normalized["players"][0]["purchase_log"][0]["source_ref"] == (
        "players[0].purchase_log[0]"
    )
    timeline = load_timeline(result["normalized_json"], 0)
    assert timeline.events[0].item_key == "power_treads"
    assert timeline.source == "raw-gem.json"
    with sqlite3.connect(data_dir / "index.sqlite") as index:
        assert index.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
        assert index.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 2
        assert index.execute("SELECT COUNT(*) FROM item_events").fetchone()[0] == 2
    config = tmp_path / "config.json"
    config.write_text('{"candidate_items":["power_treads"]}', encoding="utf-8")
    report_dir = tmp_path / "report"
    assert (
        main(
            [
                "report",
                result["normalized_json"],
                "--player-slot",
                "0",
                "--config",
                str(config),
                "--output",
                str(report_dir),
            ]
        )
        == 0
    )
    assert "07:00" in (report_dir / "report.html").read_text(encoding="utf-8")
    assert ingest_demo(source, data_dir)["status"] == "cached"
    assert len(calls) == 1
    assert ingest_demo(source, data_dir, force=True)["status"] == "imported"
    assert len(calls) == 2
    with sqlite3.connect(data_dir / "index.sqlite") as index:
        assert index.execute("SELECT COUNT(*) FROM item_events").fetchone()[0] == 2


def test_zip_uses_single_demo_without_extracting_member_path(tmp_path):
    archive = tmp_path / "match.dem.zip"
    with zipfile.ZipFile(archive, "w") as zipper:
        zipper.writestr("../../evil.dem", DEMO)
    with prepared_demo(archive, tmp_path / "scratch") as replay:
        assert replay.read_bytes() == DEMO
        assert replay.parent.parent.name == "scratch"
    assert not (tmp_path / "evil.dem").exists()


def test_rejects_bad_header_and_ambiguous_zip(tmp_path):
    source = tmp_path / "bad.dem"
    source.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="PBDEMS2"):
        with prepared_demo(source, tmp_path / "scratch"):
            pass
    archive = tmp_path / "many.dem.zip"
    with zipfile.ZipFile(archive, "w") as zipper:
        zipper.writestr("a.dem", DEMO)
        zipper.writestr("b.dem", DEMO)
    with pytest.raises(ValueError, match="exactly one"):
        with prepared_demo(archive, tmp_path / "scratch"):
            pass


def test_canonicalizer_preserves_game_clock_and_reports_missing_tick():
    match = fake_match()
    match.players[0].purchase_log.append(
        types.SimpleNamespace(
            value_name="item_blink",
            game_time_s=None,
            tick=999,
        )
    )
    match.game_clock = types.SimpleNamespace(
        game_seconds_at=lambda tick: None if tick == 999 else tick // 30,
    )
    normalized, issues = canonicalize_match(match)
    assert [entry["key"] for entry in normalized["players"][0]["purchase_log"]] == [
        "power_treads",
        "tpscroll",
    ]
    assert any("purchase time unavailable" in issue for issue in issues)


def test_cli_batch_continues_after_corrupt_replay(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.dem").write_bytes(DEMO)
    (tmp_path / "b.dem").write_bytes(b"not a demo")
    calls = []
    install_fake_gem(monkeypatch, calls)
    assert main(["ingest-demo", str(tmp_path), "--data-dir", str(tmp_path / "data")]) == 1
    output = capsys.readouterr()
    assert '"status": "imported"' in output.out
    assert '"status": "error"' in output.err
    assert len(calls) == 1


def test_data_status_reads_initialized_index(tmp_path, monkeypatch, capsys):
    source = tmp_path / "one.dem"
    source.write_bytes(DEMO)
    install_fake_gem(monkeypatch, [])
    data_dir = tmp_path / "data"
    ingest_demo(source, data_dir)
    assert main(["data-status", "--data-dir", str(data_dir)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status == {"matches": 1, "players": 2, "item_events": 2, "match_ids": [42]}


def test_zstd_archive_detected_by_magic_even_with_bz2_extension(tmp_path):
    zstandard = pytest.importorskip("zstandard")
    source = tmp_path / "match.dem.bz2"
    source.write_bytes(zstandard.ZstdCompressor().compress(DEMO))
    with prepared_demo(source, tmp_path / "scratch") as replay:
        assert replay.read_bytes() == DEMO


@pytest.mark.parametrize(
    "name,hero_id",
    [("queen_of_pain", 39), ("anti_mage", 1), ("vengeful_spirit", 20)],
)
def test_real_gem_catalog_recovers_known_hero_aliases(name, hero_id):
    pytest.importorskip("gem.catalog.heroes")
    match = fake_match()
    match.players[0].hero_id = 0
    match.players[0].hero_name = "npc_dota_hero_" + name
    canonical, _ = canonicalize_match(match)
    player = canonical["players"][0]
    assert player["hero_id"] == hero_id
    assert player["hero_identity"]["source_ref"] == "players[0].hero_name"
    assert match.players[0].hero_id == 0
