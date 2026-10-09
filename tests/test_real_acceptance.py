import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from dota_items.data.acceptance import AcceptanceConfig, cohort_reasons, compare_evidence
from dota_items.data.cleaning import clean_match
from dota_items.data.contracts import PreparationConfig


def test_purchase_projection_excludes_combined_wards_preserving_free_and_repeated_buys():
    with pytest.raises(ValueError):
        PreparationConfig(candidate_items=["ward_dispenser"])
    raw = {
        "match_id": 42,
        "duration": 100,
        "players": [
            {
                "player_slot": 0,
                "hero_id": 1,
                "purchase_log": [
                    {"time": 1, "key": "ward_observer"},
                    {"time": 1, "key": "ward_sentry"},
                    {"time": 1, "key": "ward_sentry"},
                    {"time": 1, "key": "ward_dispenser"},
                    {"time": 2, "key": "recipe_force_staff"},
                ],
            }
        ],
    }
    cleaned, quality = clean_match(raw, PreparationConfig())
    assert [r["key"] for r in cleaned["players"][0]["purchase_log"]] == [
        "ward_observer",
        "ward_sentry",
        "ward_sentry",
    ]
    assert len(raw["players"][0]["purchase_log"]) == 5
    assert quality["quarantined"] == 0
    assert [i["action"] for i in quality["issues"]] == ["exclude", "exclude"]
    assert cleaned["players"][0]["purchase_coverage"] is None


def test_cohort_requires_letter_patch_and_sufficient_rank_evidence():
    config = AcceptanceConfig(patch="7.41f").model_dump()
    row = {
        "match_id": 42,
        "avg_rank_tier": 75,
        "num_rank_tier": 8,
        "game_mode": 22,
        "lobby_type": 7,
        "start_time": 10000,
        "duration": 1800,
        "patch": 60,
    }
    assert cohort_reasons(row, config, 10000, 12000) == []
    assert "outside_letter_patch_time_interval" in cohort_reasons(row, config, 11000, 12000)
    assert "outside_letter_patch_time_interval" in cohort_reasons(row, config, 9000, 11800)
    row["num_rank_tier"] = 1
    assert "insufficient_num_rank_tier_evidence" in cohort_reasons(row, config, 10000, 12000)
    row["duration"] = None
    assert "duration_outside_cohort" in cohort_reasons(row, config, 10000, 12000)


def test_cohort_config_rejects_unbounded_downloads_and_impossible_average_rank():
    with pytest.raises(ValueError):
        AcceptanceConfig(patch="7.41f", minimum_average_rank_tier=80)
    with pytest.raises(ValueError):
        AcceptanceConfig(patch="7.41f", target_downloads=0)


def test_strict_collection_reports_unavailable_source_without_fake_acceptance(
    tmp_path, monkeypatch
):
    command = runpy.run_path(str(Path(__file__).parents[1] / "scripts/accept_replays.py"))
    config = tmp_path / "config.json"
    config.write_text(AcceptanceConfig(patch="7.41f").model_dump_json())
    output = tmp_path / "run"
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(command["main"].__globals__["time"], "sleep", lambda seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["accept_replays.py", "--config", str(config), "--output", str(output), "--strict"],
    )
    assert command["main"]() == 1
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "incomplete"
    assert report["audit_passed"] == report["downloaded"] == 0
    assert "503" in report["blocking_error"]
    with pytest.raises(ValueError, match="choose a new --output"):
        command["main"]()


def test_audit_rejects_time_tampering_even_when_raw_tick_and_value_match():
    players = [
        {"player_slot": slot, "hero_id": i + 1}
        for i, slot in enumerate([*range(5), *range(128, 133)])
    ]
    players[0]["position_log"] = [{"time": 90, "source_tick": 30, "x": 100, "y": 200}]
    match = {"match_id": 42, "duration": 120, "players": players}
    raw = {"match_id": 42, "duration": 120, "post_game_tick": 3600}
    api = {**match}
    clock = SimpleNamespace(game_seconds_at=lambda tick: tick // 30)
    audit = compare_evidence(match, raw, api, clock)
    assert audit["reasons"] == ["source_time_mismatch"]
    assert audit["checked_timestamps"] == audit["mismatched_timestamps"] == 1
    players[0]["position_log"][0]["time"] = 1
    assert compare_evidence(match, raw, api, clock)["reasons"] == []


def test_audit_holds_missing_clock_end_and_inconsistent_api():
    match = {"match_id": 42, "duration": 120, "players": []}
    raw = {"match_id": 42, "duration": 120}
    api = {"match_id": 43, "duration": 121, "players": []}
    assert set(compare_evidence(match, raw, api, None)["reasons"]) == {
        "match_id_mismatch",
        "duration_mismatch",
        "ten_player_identity_mismatch",
        "post_game_transition_missing",
        "game_clock_missing",
    }
