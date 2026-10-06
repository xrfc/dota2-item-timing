"""Clean a derived copy, retaining source row references and every exclusion."""

import copy
import re
from typing import Any

from ..sources.gem_observations import number
from .contracts import ECONOMY, SLOTS, Coverage, PreparationConfig


def clean_match(raw: Any, config: PreparationConfig) -> tuple[dict, dict]:
    if not isinstance(raw, dict):
        raise ValueError("Expected a normalized match object, not raw Gem JSON")
    if raw.get("schema_version") not in (
        None,
        "gem-adapter/2.0",
        "gem-adapter/2.1",
        "gem-adapter/2.2",
    ):
        raise ValueError("Unsupported normalized input schema; raw Gem exports need the adapter")
    for name in ("match_id", "duration"):
        value = raw.get(name)
        if type(value) is not int or value < (1 if name == "match_id" else 0):
            raise ValueError(f"{name} must be an integer in range")
    if raw["duration"] > config.max_duration_seconds:
        raise ValueError("duration exceeds preparation resource limit")
    players = raw.get("players")
    if not isinstance(players, list) or not 1 <= len(players) <= 10:
        raise ValueError("players must contain 1 to 10 players")
    cleaned = copy.deepcopy(raw)
    quality = {
        "schema_version": "coach-cleaning/1",
        "issues": [],
        "channels": {},
        "adapter_issues": raw.get("adapter_issues", []),
        "source_cleaning_audit": raw.get("cleaning_audit"),
    }
    slots = set()

    def issue(ref, reason, action="quarantine"):
        if config.invalid_policy == "reject" and action == "quarantine":
            raise ValueError(f"{ref}: {reason}")
        quality["issues"].append({"source_ref": ref, "reason": reason, "action": action})

    for index, player in enumerate(cleaned["players"]):
        if not isinstance(player, dict):
            raise ValueError("Player must be an object")
        slot, hero = player.get("player_slot"), player.get("hero_id")
        if type(slot) is not int or slot not in SLOTS or slot in slots:
            raise ValueError("Invalid or duplicate player_slot")
        if type(hero) is not int or hero <= 0:
            raise ValueError("hero_id must be a positive integer")
        slots.add(slot)
        stats = {}
        for channel in ("purchase_log", "position_log", "economy_log"):
            rows = player.get(channel)
            base = f"players[{index}].{channel}"
            available = rows is not None
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                raise ValueError(f"{base} must be an array or absent")
            if len(rows) > config.max_rows_per_channel:
                raise ValueError(f"{base} exceeds row limit")
            retained = []
            invalid = 0
            for ordinal, row in enumerate(rows):
                ref = f"{base}[{ordinal}]"
                if not isinstance(row, dict):
                    issue(ref, "row is not an object")
                    invalid += 1
                    continue
                time = row.get("time")
                minimum = -3600 if channel == "purchase_log" else 0
                if not number(time) or not minimum <= time <= raw["duration"]:
                    issue(ref, "invalid/out-of-range time")
                    invalid += 1
                    continue
                row["input_ref"] = ref
                if channel == "purchase_log":
                    if not isinstance(row.get("key"), str) or not re.fullmatch(
                        r"[a-z][a-z0-9_]{0,99}", row["key"]
                    ):
                        issue(ref, "invalid canonical item key")
                        invalid += 1
                        continue
                    # Match OpenDota's purchase projection. Combined wards are not a shop buy;
                    # preserve actual free observer wards and repeated purchases.
                    if row["key"] == "ward_dispenser" or row["key"].startswith("recipe_"):
                        issue(ref, "non-purchase recipe/combined-ward record", "exclude")
                        continue
                elif channel == "position_log":
                    if not all(number(row.get(k)) for k in ("x", "y")):
                        issue(ref, "non-finite position")
                        invalid += 1
                        continue
                else:
                    for key in ECONOMY:
                        value = row.get(key)
                        if value is not None and (not number(value) or value < 0):
                            issue(f"{ref}.{key}", "invalid economy value; replaced with null")
                            row[key] = None
                retained.append(row)
            if retained != sorted(retained, key=lambda row: row["time"]):
                issue(base, "stable sort by game time", "sort")
            retained.sort(key=lambda row: row["time"])
            # Purchases with the same time/key can be genuine repeated buys; preserve them.
            # Sampled states must be unambiguous. Conflicting same-time rows all disappear.
            if channel != "purchase_log":
                fields = ("x", "y") if channel == "position_log" else ECONOMY
                groups = {}
                for row in retained:
                    groups.setdefault(row["time"], []).append(row)
                retained = []
                for group in groups.values():
                    same = all(
                        [r.get(k) for k in fields] == [group[0].get(k) for k in fields]
                        for r in group
                    )
                    if same:
                        retained.append(group[0])
                        for row in group[1:]:
                            issue(row["input_ref"], "duplicate sampled state", "deduplicate")
                    else:
                        for row in group:
                            issue(row["input_ref"], "conflicting sampled states at same time")
                            invalid += 1
            player[channel] = retained if available or channel != "purchase_log" else None
            stats[channel] = {
                "input_rows": len(rows),
                "retained_rows": len(retained),
                "available": available,
                "invalid_rows": invalid,
            }
        coverage = player.get("purchase_coverage")
        if coverage is not None:
            coverage = Coverage.model_validate(coverage).model_dump()
            if not coverage["start_seconds"] <= coverage["end_seconds"] <= raw["duration"]:
                raise ValueError("purchase_coverage is outside match duration")
        # Any lost purchase event invalidates absence/next-event supervision for this player.
        if stats["purchase_log"]["invalid_rows"] or not stats["purchase_log"]["available"]:
            coverage = None
        player["purchase_coverage"] = coverage
        quality["channels"][str(slot)] = stats
    quality["quarantined"] = sum(x["action"] == "quarantine" for x in quality["issues"])
    return cleaned, quality
