"""Validate imported evidence before it is frozen into a dataset."""

import re
from pathlib import Path
from typing import Any

from ..normalize import normalize_match
from ..sources.gem_observations import number
from ..storage import file_hash, inside, read_json


def resolve_ref(value: Any, reference: str) -> Any:
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\[\d+\]|\.[A-Za-z_]\w*)*", reference):
        raise ValueError(f"Invalid evidence reference: {reference}")
    try:
        for name, index in re.findall(r"([A-Za-z_]\w*)|\[(\d+)\]", reference):
            value = value[name] if name else value[int(index)]
        return value
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"Unresolved evidence reference: {reference}") from error


def validate_match(path: Path) -> dict[str, Any]:
    raw = read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("players"), list):
        raise ValueError("Expected a match object with players")
    match_id = raw.get("match_id")
    if isinstance(match_id, bool) or not isinstance(match_id, int) or match_id <= 0:
        raise ValueError("match_id must be a positive integer")
    if not raw["players"]:
        raise ValueError("Match has no players")
    external = raw.get("evidence_source")
    evidence = raw
    evidence_path = None
    if external:
        evidence_path = inside(path.parent, external)
        if file_hash(evidence_path) != raw.get("evidence_sha256"):
            raise ValueError("Raw evidence fingerprint mismatch")
        evidence = read_json(evidence_path)
        if evidence.get("match_id") != match_id:
            raise ValueError("Raw evidence belongs to another match")
    warnings = []
    slots = set()
    channels = {}
    for index, player in enumerate(raw["players"]):
        if not isinstance(player, dict):
            raise ValueError("Player must be an object")
        slot = player.get("player_slot")
        if isinstance(slot, bool) or slot not in {*range(5), *range(128, 133)} or slot in slots:
            raise ValueError(f"Invalid or duplicate player slot: {slot}")
        if (
            type(slot) is not int
            or type(player.get("hero_id")) is not int
            or player["hero_id"] <= 0
        ):
            raise ValueError("Player slot and hero_id must be valid integers")
        slots.add(slot)
        timeline = normalize_match(raw, slot, source=path.name, fingerprint=file_hash(path))
        if timeline.purchase_log_status == "invalid" or any(
            flag.startswith("invalid_event:") for flag in timeline.quality_flags
        ):
            raise ValueError(f"Invalid purchase log for player {slot}")
        warnings.extend(timeline.quality_flags)
        for ordinal, event in enumerate(player.get("purchase_log") or []):
            ref = event.get("source_ref", f"players[{index}].purchase_log[{ordinal}]")
            original = resolve_ref(evidence, ref)
            if not isinstance(original, dict):
                raise ValueError(f"Purchase evidence is not an object: {ref}")
            key = original.get("value_name", original.get("key", ""))
            if not isinstance(key, str) or key.removeprefix("item_") != event["key"]:
                raise ValueError(f"Purchase evidence item mismatch: {ref}")
            original_time = original.get("game_time_s", original.get("time"))
            if original_time is not None and original_time != event["time"]:
                raise ValueError(f"Purchase evidence time mismatch: {ref}")
            if external and original.get("tick") != event.get("source_tick"):
                raise ValueError(f"Purchase evidence tick mismatch: {ref}")
        for channel in ("position_log", "economy_log"):
            entries = player.get(channel, [])
            if not isinstance(entries, list):
                raise ValueError(f"{channel} must be an array")
            previous = 0
            for row in entries:
                if not isinstance(row, dict):
                    raise ValueError(f"Invalid {channel} sample")
                time = row.get("time")
                if not number(time) or not previous <= time <= timeline.duration_seconds:
                    raise ValueError(f"Unordered or invalid {channel} time")
                previous = time
                if channel == "position_log":
                    if not number(row.get("x")) or not number(row.get("y")):
                        raise ValueError("Position coordinates must be finite")
                    if external:
                        source = resolve_ref(evidence, row["source_ref"])
                        if list(source) != [row.get("source_tick"), row["x"], row["y"]]:
                            raise ValueError("Position evidence mismatch")
                else:
                    for name in ("gold", "net_worth", "last_hits", "denies", "xp_progress"):
                        value = row.get(name)
                        if value is not None and (not number(value) or value < 0):
                            raise ValueError(f"Invalid economy value: {name}")
                        if external and value is not None:
                            if (
                                resolve_ref(evidence, row.get("source_refs", {}).get(name, ""))
                                != value
                            ):
                                raise ValueError(f"Economy evidence mismatch: {name}")
            if not entries:
                warnings.append(f"player {slot}: {channel} unavailable")
        channels[str(slot)] = {
            "purchases": timeline.purchase_log_status,
            "positions": len(player.get("position_log", [])),
            "economy": sum(
                any(
                    row.get(name) is not None
                    for name in ("gold", "net_worth", "last_hits", "denies", "xp_progress")
                )
                for row in player.get("economy_log", [])
            ),
        }
    return {
        "match_id": match_id,
        "synthetic": bool(raw.get("_fixture")),
        "evidence_path": evidence_path,
        "warnings": sorted(set(warnings)),
        "channels": channels,
    }
