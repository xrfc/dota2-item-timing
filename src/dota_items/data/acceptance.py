"""Real replay audits; acquisition and parser success do not establish label validity."""

import json
from collections import Counter
from pathlib import Path

from ..storage import inside, read_json, verify_files
from ..workflow.validation import resolve_ref, validate_match
from .contracts import ECONOMY, SLOTS


def observation_metrics(match, features, labels):
    """Report measured coverage without inventing event completeness or coordinate limits."""
    if not features or len(features) != len(labels):
        raise ValueError("Feature/label row count mismatch or empty samples")
    ids = [r["sample_id"] for r in features]
    if len(set(ids)) != len(ids) or ids != [r["sample_id"] for r in labels]:
        raise ValueError("Feature/label identities are not unique and aligned")
    rows = []
    for player in match["players"]:
        slot = player["player_slot"]
        prefix = f"{match['match_id']}:{slot}:"
        indices = [i for i, sample_id in enumerate(ids) if sample_id.startswith(prefix)]
        if not indices:
            raise ValueError(f"No samples for player {slot}")
        selected = [features[i] for i in indices]
        targets = [labels[i] for i in indices]
        positions = player["position_log"]
        rows.append(
            {
                "player_slot": slot,
                "hero_id": player["hero_id"],
                "samples": len(indices),
                "position_rows": len(positions),
                "economy_rows": len(player["economy_log"]),
                "purchase_rows": len(player.get("purchase_log") or []),
                "position_coverage": sum(r["x"] is not None for r in selected) / len(indices),
                "economy_coverage": {
                    k: sum(r[k] is not None for r in selected) / len(indices) for k in ECONOMY
                },
                "coordinate_range": {
                    k: [min(r[k] for r in positions), max(r[k] for r in positions)]
                    if positions
                    else None
                    for k in ("x", "y")
                },
                "max_position_gap_seconds": max(
                    (b["time"] - a["time"] for a, b in zip(positions, positions[1:], strict=False)),
                    default=None,
                ),
                "item_labels": sum(r["item_mask"] for r in targets),
                "route_labels": sum(r["route_mask"] for r in targets),
                "item_reasons": dict(Counter(r["item_reason"] for r in targets)),
                "route_reasons": dict(Counter(r["route_reason"] for r in targets)),
                "purchase_coverage_asserted": player.get("purchase_coverage") is not None,
            }
        )
    return rows


def compare_evidence(match, raw, api, clock):
    """Cross-check identity and tick conversion without enriching Gem from the API."""
    reasons = []
    if not match["match_id"] == raw.get("match_id") == api.get("match_id"):
        reasons.append("match_id_mismatch")
    if not match["duration"] == raw.get("duration") == api.get("duration"):
        reasons.append("duration_mismatch")
    heroes = {p["player_slot"]: p["hero_id"] for p in match["players"]}
    expected = {p["player_slot"]: p["hero_id"] for p in api.get("players", [])}
    if set(heroes) != SLOTS or heroes != expected or len(api.get("players", [])) != 10:
        reasons.append("ten_player_identity_mismatch")
    if raw.get("post_game_tick") is None:
        reasons.append("post_game_transition_missing")
    if clock is None:
        reasons.append("game_clock_missing")
    checked, mismatched = 0, 0
    for player in match["players"]:
        for channel in ("purchase_log", "position_log", "economy_log"):
            for row in player.get(channel) or []:
                if channel == "purchase_log":
                    original = resolve_ref(raw, row["source_ref"])
                    second = original.get("game_time_s")
                    if second is None and clock is not None:
                        second = clock.game_seconds_at(row["source_tick"])
                else:
                    second = clock.game_seconds_at(row["source_tick"]) if clock else None
                checked += 1
                mismatched += second is None or second != row["time"]
    if mismatched:
        reasons.append("source_time_mismatch")
    return {
        "reasons": reasons,
        "checked_timestamps": checked,
        "mismatched_timestamps": mismatched,
        "duration_delta_seconds": match["duration"] - api.get("duration", 0),
    }


def audit_prepared(folder: Path, api: dict):
    import gem

    manifest = read_json(folder / "manifest.json")
    verify_files(folder, manifest["files"])
    validate_match(folder / "cleaned.json")
    match = read_json(folder / "cleaned.json")
    raw = read_json(inside(folder, match["evidence_source"]))
    # Reuse Gem's public deserializer and pause-aware clock, not a local approximation.
    clock = gem.from_dict({"game_clock": raw.get("game_clock")}).game_clock
    comparison = compare_evidence(match, raw, api, clock)

    def read_rows(name):
        with (folder / f"{name}.jsonl").open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream]

    players = observation_metrics(match, read_rows("features"), read_rows("labels"))
    quality = read_json(folder / "quality.json")
    reasons = list(comparison["reasons"])
    if quality["quarantined"]:
        reasons.append("quarantined_values_require_review")
    if any(p.get("leaver_status") != 0 for p in api.get("players", [])):
        reasons.append("leaver_or_unknown_connection_status")
    if any(p["position_rows"] == 0 or p["economy_rows"] == 0 for p in players):
        reasons.append("missing_observation_channel")
    return {
        "schema_version": "real-replay-audit/1",
        "match_id": match["match_id"],
        "pipeline_status": "passed" if not reasons else "held",
        "hold_reasons": reasons,
        "comparison": comparison,
        "players": players,
        "cleaning_quarantined": quality["quarantined"],
        "adapter_issue_count": len(quality["adapter_issues"]),
        "adapter_issue_examples": quality["adapter_issues"][:10],
        "decision_quality_supervision": "unavailable",
        "limitations": [
            "API identity agreement does not independently validate every position or purchase.",
            "Observed purchases do not establish complete inventory or negative purchase labels.",
            "Endpoint displacement is not path selection or decision correctness.",
            "Coverage thresholds require cohort measurements and task-specific review.",
        ],
    }
