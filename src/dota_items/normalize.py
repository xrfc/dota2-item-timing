"""OpenDota fields are interpreted only in this module."""

import hashlib
import json
import math
from typing import Any

from .domain import ItemEvent, PlayerTimeline


def normalize_match(
    raw: dict[str, Any], player_slot: int, *, source: str, fingerprint: str
) -> PlayerTimeline:
    players = raw.get("players")
    if not isinstance(players, list):
        raise ValueError("Match data has no valid players array")
    candidates = [p for p in players if isinstance(p, dict) and p.get("player_slot") == player_slot]
    if len(candidates) != 1:
        raise ValueError(f"Expected one player for slot {player_slot}; found {len(candidates)}")
    player = candidates[0]
    player_index = players.index(player)
    flags: list[str] = []
    if isinstance(raw.get("_fixture"), str):
        flags.append("synthetic_fixture: 合成示例数据，不是真实比赛或出装建议")
    log = player.get("purchase_log")
    status = "present"
    if log is None:
        status, log = "missing", []
        flags.append("purchase_log_missing: absence is not evidence of no purchases")
    elif not isinstance(log, list):
        status, log = "invalid", []
        flags.append("purchase_log_invalid: expected an array")
    elif not log:
        flags.append("purchase_log_empty: completeness has not been verified")

    events: list[ItemEvent] = []
    duration = raw.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
        raise ValueError("Match duration must be a non-negative integer in seconds")
    for index, entry in enumerate(log):
        reference = f"players[{player_index}].purchase_log[{index}]"
        if not isinstance(entry, dict):
            flags.append(f"invalid_event:{reference}")
            continue
        key, time = entry.get("key"), entry.get("time")
        if (
            not isinstance(key, str)
            or not key.strip()
            or isinstance(time, bool)
            or not isinstance(time, (int, float))
            or not math.isfinite(time)
            or time > duration
        ):
            flags.append(f"invalid_event:{reference}")
            continue
        events.append(ItemEvent(item_key=key, time_seconds=time, source_event_ref=reference))
    events.sort(key=lambda event: event.time_seconds)
    return PlayerTimeline(
        match_id=raw["match_id"],
        player_slot=player_slot,
        hero_id=player["hero_id"],
        patch_id=raw.get("patch"),
        game_mode=raw.get("game_mode"),
        duration_seconds=duration,
        purchase_log_status=status,
        events=events,
        quality_flags=flags,
        source=source,
        source_fingerprint=fingerprint,
    )


def load_timeline(path: Any, player_slot: int) -> PlayerTimeline:
    from pathlib import Path

    file_path = Path(path)
    contents = file_path.read_bytes()
    raw = json.loads(contents)
    if not isinstance(raw, dict):
        raise ValueError("Match JSON must be an object")
    return normalize_match(
        raw,
        player_slot,
        source=file_path.name,
        fingerprint="sha256:" + hashlib.sha256(contents).hexdigest(),
    )
