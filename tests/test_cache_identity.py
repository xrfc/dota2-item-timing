"""Regression cases for cache integrity and raw player identity boundaries."""

import bz2
import json
from pathlib import Path

import pytest
from test_replay_ingestion import DEMO, fake_match, install_fake_gem

from dota_items.sources.gem_replay import canonicalize_match, ingest_demo
from dota_items.storage import file_hash, read_json, write_json
from dota_items.workflow.validation import validate_match
from dota_items.workflow.workspace import Workspace


@pytest.fixture
def imported(tmp_path, monkeypatch):
    source = tmp_path / "match.dem.bz2"
    source.write_bytes(bz2.compress(DEMO))
    calls = []
    install_fake_gem(monkeypatch, calls)
    result = ingest_demo(source, tmp_path / "cache")
    return source, calls, result


@pytest.mark.parametrize("damage", ["normalized", "missing_manifest", "legacy_manifest", "raw"])
def test_damaged_cache_is_reparsed(imported, damage):
    source, calls, result = imported
    normalized = Path(result["normalized_json"])
    manifest_path = Path(result["manifest"])
    manifest = read_json(manifest_path)
    if damage == "normalized":
        payload = read_json(normalized)
        payload["players"][0]["hero_id"] = 1
        write_json(normalized, payload)
    elif damage == "missing_manifest":
        manifest_path.unlink()
    elif damage == "legacy_manifest":
        manifest.pop("normalized_json_sha256", None)
        write_json(manifest_path, manifest)
    else:
        Path(manifest["raw_json"]).write_text("{}")
    assert ingest_demo(source, source.parent / "cache")["status"] == "imported"
    assert len(calls) == 2
    assert read_json(normalized)["players"][0]["hero_id"] == 44
    validate_match(normalized)


def test_cache_hit_preserves_provenance_for_new_catalog(imported):
    source, calls, first = imported
    cached = ingest_demo(source, source.parent / "cache")
    assert cached == {**first, "status": "cached"}
    assert cached["source_sha256"] != cached["demo_sha256"]
    workspace = Workspace(source.parent / "new-workspace")
    workspace.init()
    workspace.import_json(Path(cached["normalized_json"]), demo_sha256=cached["demo_sha256"])
    assert workspace.catalog()["matches"]["42"]["demo_sha256"] == first["demo_sha256"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("demo_sha256", None),
        ("demo_sha256", "invalid"),
        ("source_sha256", "0" * 64),
        ("parser_version", "old"),
        ("capture_version", "old"),
        ("issues", None),
    ],
)
def test_incomplete_or_stale_cache_provenance_is_reparsed(imported, field, value):
    source, calls, result = imported
    path = Path(result["manifest"])
    manifest = read_json(path)
    manifest[field] = value
    write_json(path, manifest)
    assert ingest_demo(source, source.parent / "cache")["status"] == "imported"
    assert len(calls) == 2


@pytest.mark.parametrize("damage", ["hero", "slot", "purchase", "position", "economy"])
def test_normalized_identity_cannot_be_reassigned(imported, damage):
    _, _, result = imported
    path = Path(result["normalized_json"])
    payload = read_json(path)
    player = payload["players"][0]
    raw_path = path.parent / payload["evidence_source"]
    raw = read_json(raw_path)
    if damage == "hero":
        player["hero_id"] = 1
    elif damage == "slot":
        player["player_slot"] = 1
    elif damage == "purchase":
        raw["players"][1]["purchase_log"] = raw["players"][0]["purchase_log"]
        player["purchase_log"][0]["source_ref"] = "players[1].purchase_log[0]"
    elif damage == "position":
        raw["players"][1]["position_log"] = [[30, 1, 2]]
        player["position_log"] = [
            {
                "time": 1,
                "x": 1,
                "y": 2,
                "source_tick": 30,
                "source_ref": "players[1].position_log[0]",
            }
        ]
    else:
        raw["players"][1]["gold"] = [100]
        player["economy_log"] = [
            {"time": 1, "gold": 100, "source_refs": {"gold": "players[1].gold[0]"}}
        ]
    write_json(raw_path, raw)
    payload["evidence_sha256"] = file_hash(raw_path)
    write_json(path, payload)
    with pytest.raises(ValueError, match="identity|player"):
        validate_match(path)


@pytest.mark.parametrize("forged", [False, True])
def test_alias_identity_is_resolved_from_raw_player_not_array_order(tmp_path, forged):
    pytest.importorskip("gem.catalog.heroes")
    match = fake_match()
    match.players.reverse()
    match.players[1].hero_id = 0
    match.players[1].hero_name = "npc_dota_hero_anti_mage"
    normalized, _ = canonicalize_match(match)
    # Normalized order need not equal raw order.
    normalized["players"].reverse()
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(
        json.dumps({"match_id": 42, "players": [vars(p) for p in match.players]}, default=vars)
    )
    normalized["evidence_source"] = raw_path.name
    normalized["evidence_sha256"] = file_hash(raw_path)
    if forged:
        normalized["players"][0]["hero_id"] = 44
    path = tmp_path / "normalized.json"
    write_json(path, normalized)
    if forged:
        with pytest.raises(ValueError, match="identity"):
            validate_match(path)
    else:
        validate_match(path)
