"""Visibility leakage, missingness, provenance and state-capture boundary tests."""

import copy
from types import SimpleNamespace

import pytest

from dota_items.data.cleaning import clean_match
from dota_items.data.context import CHANNELS, clean_context, export_context, validate_context
from dota_items.data.contracts import PreparationConfig
from dota_items.data.observer import ObserverIndex
from dota_items.data.pipeline import prepare_one
from dota_items.sources.gem_capture import snapshot_evidence
from dota_items.storage import read_json, write_json
from dota_items.workflow.validation import resolve_ref
from dota_items.workflow.workspace import Workspace


def wrap(channel, payload, ordinal=0):
    return {
        "time": payload["tick"] // 30,
        "source_tick": payload["tick"],
        "source_ref": f"{channel}[{ordinal}]",
        "payload": payload,
    }


def state(time=0, hp=500, pid=0):
    return wrap(
        "coach_state_snapshots",
        {
            "tick": time * 30,
            "player_id": pid,
            "entity_index": pid + 10,
            "entity_serial": 1,
            "level": 5,
            "hp": hp,
            "max_hp": 1000,
            "mana": None,
            "max_mana": 500,
            "life_state": 0,
            "items": {"0": "item_boots"},
            "inventory_slots": list(range(17)),
            "inventory_unknown_slots": [16],
            "inventory_complete": False,
            "ability_levels": {"axe_berserkers_call": 2},
        },
    )


def fixture():
    channels = {name: None for name in CHANNELS}
    channels["hero_visibility_events"] = [
        wrap(
            "hero_visibility_events",
            {
                "tick": time * 30,
                "player_id": 5,
                "entity_index": 15,
                "entity_serial": 1,
                "radiant_state": visibility,
                "dire_state": "visible",
            },
            i,
        )
        for i, (time, visibility) in enumerate([(0, "visible"), (10, "hidden"), (30, "visible")])
    ]
    channels["combat_log"] = [
        wrap(
            "combat_log",
            {
                "tick": 360,
                "log_type": "ABILITY",
                "inflictor_name": "test",
                "visible_radiant": visible,
                "visible_dire": True,
            },
            i,
        )
        for i, visible in enumerate([True, False, None])
    ]
    channels["coach_state_snapshots"] = [state()]
    return {
        "_fixture": "Synthetic context regression; not real gameplay evidence",
        "match_id": 42,
        "duration": 60,
        "context": {"schema_version": "coach-context/1", "channels": channels, "excluded": {}},
        "players": [
            {
                "player_slot": slot,
                "hero_id": hero,
                "purchase_log": [],
                "economy_log": [],
                "position_log": [
                    {
                        "time": t,
                        "source_tick": t * 30,
                        "x": t,
                        "y": t + 1,
                        "source_ref": f"players[{i}].position_log[{t}]",
                    }
                    for t in range(61)
                ],
            }
            for i, (slot, hero) in enumerate([(0, 2), (128, 3)])
        ],
    }


def test_hidden_and_future_truth_cannot_change_observer_features():
    before = fixture()
    after = copy.deepcopy(before)
    for pos in after["players"][1]["position_log"]:
        if 10 <= pos["time"] < 30 or pos["time"] >= 40:
            pos.update(x=999999, y=-999999)
    # Enemy inventory is deliberately not copied into the player's observation.
    after["context"]["channels"]["coach_state_snapshots"].append(state(15, hp=1, pid=5))
    assert ObserverIndex(before).sample(0, 20) == ObserverIndex(after).sample(0, 20)
    row = ObserverIndex(before).sample(0, 20)
    assert row["enemies"][0]["last_seen"]["time"] == 9
    assert row["enemies"][0]["hidden_for_seconds"] == 10
    assert row["observed_combat_counts"] == {"ABILITY": 1}
    assert len(row["observed_events"]) == 1


def test_cutoff_bucket_excluded_and_unknown_not_hidden():
    match = fixture()
    assert ObserverIndex(match).sample(0, 10)["enemies"][0]["visibility"] == "visible"
    match["context"]["channels"]["hero_visibility_events"][1]["payload"]["radiant_state"] = (
        "unknown"
    )
    enemy = ObserverIndex(match).sample(0, 20)["enemies"][0]
    assert enemy["visibility"] == "unknown"
    assert enemy["hidden_since"] is None
    assert enemy["last_seen"]["time"] == 9


def test_entity_reuse_clears_old_location_and_initial_hidden_has_no_duration():
    match = fixture()
    events = match["context"]["channels"]["hero_visibility_events"]
    events[1]["payload"]["entity_serial"] = 2
    enemy = ObserverIndex(match).sample(0, 20)["enemies"][0]
    assert enemy["last_seen"] is None
    assert enemy["hidden_for_seconds"] is None
    match["context"]["channels"]["hero_visibility_events"] = events[1:]
    assert ObserverIndex(match).sample(0, 20)["enemies"][0]["hidden_since"] is None


def test_missing_stale_and_conflicting_state_are_not_zero_health():
    match = fixture()
    assert ObserverIndex(match).sample(0, 20)["self_state"]["mana"] is None
    assert ObserverIndex(match).sample(0, 40)["self_state_status"] == "stale"
    conflict = state(hp=100)
    conflict["source_ref"] = "coach_state_snapshots[1]"
    match["context"]["channels"]["coach_state_snapshots"].append(conflict)
    row = ObserverIndex(match).sample(0, 20)
    assert row["self_state_status"] == "conflicting" and row["self_state"] is None
    match["context"]["channels"]["coach_state_snapshots"] = None
    assert ObserverIndex(match).sample(0, 20)["self_state_status"] == "unavailable"


def test_invalid_transition_disables_channel_instead_of_leaking_stale_visibility():
    match = fixture()
    match["context"]["channels"]["hero_visibility_events"][1]["payload"]["radiant_state"] = "bad"
    cleaned, quality = clean_match(match, PreparationConfig())
    assert quality["quarantined"] == 1
    assert not quality["context_channels"]["hero_visibility_events"]["available"]
    row = ObserverIndex(cleaned).sample(0, 20)
    assert row["enemies"][0]["visibility"] == "unknown"
    assert row["enemies"][0]["last_seen"] is None
    with pytest.raises(ValueError):
        clean_match(match, PreparationConfig(invalid_policy="reject"))


def test_external_payload_and_time_are_revalidated():
    gem = pytest.importorskip("gem")
    match = fixture()
    clock = gem.GameClock(game_start_tick=0)
    evidence = {"game_clock": gem.to_dict(clock)}
    for channel, rows in match["context"]["channels"].items():
        evidence[channel] = [r["payload"] for r in rows] if rows is not None else None
    validate_context(match, evidence, True, resolve_ref)
    changed = copy.deepcopy(match)
    changed["context"]["channels"]["combat_log"][0]["payload"]["value"] = 1234
    with pytest.raises(ValueError, match="payload mismatch"):
        validate_context(changed, evidence, True, resolve_ref)
    changed = copy.deepcopy(match)
    changed["context"]["channels"]["combat_log"][0]["time"] = 11
    with pytest.raises(ValueError, match="time mismatch"):
        validate_context(changed, evidence, True, resolve_ref)


def test_export_preserves_absence_and_excludes_pregame_and_noncombat():
    raw = {
        "combat_log": [
            {"tick": -30, "log_type": "DAMAGE"},
            {"tick": 30, "log_type": "GOLD"},
            {"tick": 60, "log_type": "DAMAGE", "visible_radiant": None},
        ]
    }
    context = export_context(raw, SimpleNamespace(game_seconds_at=lambda t: t // 30), 10)
    assert context["channels"]["hero_visibility_events"] is None
    assert context["excluded"]["combat_log"] == 2
    assert context["channels"]["combat_log"][0]["source_ref"] == "combat_log[2]"


def test_capture_preserves_real_zero_and_unresolved_inventory():
    hero = SimpleNamespace(
        get_int32=lambda key: 0 if key == "m_iHealth" else None,
        get_float32=lambda key: None,
        get_uint32=lambda key: 123 if key.endswith("0000") else 0xFFFFFF,
        get_index=lambda: 12,
        get_serial=lambda: 2,
    )
    ext = SimpleNamespace(_canonical_hero_entity=lambda pid: hero)
    snap = SimpleNamespace(player_id=0, tick=30, level=0, ability_levels={}, items={})
    row = snapshot_evidence(ext, snap, 0xFFFFFF)
    assert row["hp"] == 0 and row["mana"] is None and row["level"] is None
    assert row["inventory_unknown_slots"] == [0] and not row["inventory_complete"]
    assert row["inventory_handles"]["1"] == 0xFFFFFF


def test_prepare_publishes_observer_table_and_hashes(tmp_path):
    match = fixture()
    # Self-contained synthetic imports do not claim external provenance.
    for p in match["players"]:
        for row in p["position_log"]:
            row.pop("source_ref")
    path = tmp_path / "input.json"
    write_json(path, match)
    workspace = Workspace(tmp_path / "ws")
    workspace.init()
    result = prepare_one(workspace, path, PreparationConfig())
    manifest, folder = workspace.preparation(result["preparation_id"])
    assert result["observer_samples"] == 6
    assert "observer.jsonl" in manifest["files"]
    assert manifest["observer_schema"] == "coach-observer/1"
    assert read_json(folder / "quality.json")["context_channels"]["combat_log"]["rows"] == 3


def test_context_header_does_not_allow_silently_missing_channels():
    match = fixture()
    del match["context"]["channels"]["combat_log"]
    with pytest.raises(ValueError, match="explicitly"):
        clean_context(match, PreparationConfig(), lambda *args: None)


def test_pregame_visibility_initializes_observation_without_inventing_position():
    raw = {
        "hero_visibility_events": [
            {
                "tick": -30,
                "player_id": 5,
                "entity_index": 15,
                "entity_serial": 1,
                "radiant_state": "hidden",
                "dire_state": "visible",
            }
        ]
    }
    match = fixture()
    match["context"] = export_context(raw, SimpleNamespace(game_seconds_at=lambda t: t // 30), 60)
    cleaned, quality = clean_match(match, PreparationConfig())
    assert quality["quarantined"] == 0
    enemy = ObserverIndex(cleaned).sample(0, 1)["enemies"][0]
    assert enemy["visibility"] == "hidden"
    assert enemy["hidden_since"] is None and enemy["last_seen"] is None


def test_observer_tables_follow_dataset_splits_and_cli_bounds(tmp_path, capsys):
    import json

    from dota_items.data.pipeline import build_samples
    from dota_items.workflow.cli import main
    from dota_items.workflow.contracts import Labels
    from dota_items.workflow.datasets import build_dataset

    workspace = Workspace(tmp_path / "ws")
    workspace.init()
    for mid in (100, 101, 102):
        match = fixture()
        match["match_id"] = mid
        path = tmp_path / f"{mid}.json"
        write_json(path, match)
        result = prepare_one(workspace, path, PreparationConfig())
        workspace.annotate(
            mid,
            Labels(
                tier="synthetic",
                patch="test",
                role=1,
                player_slots=[0],
                label_source="synthetic test",
            ),
        )
    dataset = build_dataset(workspace, patch="test", role=1, allow_synthetic=True)
    samples = build_samples(workspace, dataset["dataset_id"], PreparationConfig())
    manifest, folder = workspace.dataset(samples["dataset_id"])
    assert manifest["observer_schema"] == "coach-observer/1"
    for split in ("train", "validation", "test"):
        observations = [
            json.loads(s) for s in (folder / f"{split}.observer.jsonl").read_text().splitlines()
        ]
        features = [
            json.loads(s) for s in (folder / f"{split}.features.jsonl").read_text().splitlines()
        ]
        assert [r["sample_id"] for r in observations] == [r["sample_id"] for r in features]
        assert len(observations) == 3
    args = ["--workspace", str(workspace.root), "observe", result["preparation_id"]]
    assert main([*args, "--player-slot", "0", "--time", "20"]) == 0
    assert json.loads(capsys.readouterr().out)["enemies"][0]["visibility"] == "hidden"
    assert main([*args, "--player-slot", "9", "--time", "20"]) == 1
    assert main([*args, "--player-slot", "0", "--time", "61"]) == 1
