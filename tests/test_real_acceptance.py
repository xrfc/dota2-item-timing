from types import SimpleNamespace

from dota_items.data.acceptance import compare_evidence


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
