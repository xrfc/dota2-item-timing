"""Export self-observable time series without choosing model features or labels."""

import math
from typing import Any


def number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def observations(player: Any, index: int, match: Any) -> dict[str, Any]:
    clock = getattr(match, "game_clock", None)
    result: dict[str, Any] = {"position_log": [], "economy_log": []}
    if clock is None:
        return result

    def second(tick):
        if not isinstance(tick, int) or isinstance(tick, bool):
            return None
        value = clock.game_seconds_at(tick)
        return value if number(value) and 0 <= value <= match.duration else None

    for ordinal, position in enumerate(getattr(player, "position_log", [])):
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            continue
        tick, x, y = position
        time = second(tick)
        if time is None or not number(x) or not number(y):
            continue
        result["position_log"].append(
            {
                "time": time,
                "x": x,
                "y": y,
                "source_tick": tick,
                "source_ref": f"players[{index}].position_log[{ordinal}]",
            }
        )
    fields = {
        "gold": "gold_t",
        "net_worth": "net_worth_t",
        "last_hits": "lh_t",
        "denies": "dn_t",
        "xp_progress": "xp_t",
    }
    for ordinal, tick in enumerate(getattr(player, "times", [])):
        time = second(tick)
        if time is None:
            continue
        entry = {"time": time, "source_tick": tick, "source_refs": {}}
        for name, upstream in fields.items():
            values = getattr(player, upstream, [])
            value = values[ordinal] if ordinal < len(values) else None
            entry[name] = value if number(value) and value >= 0 else None
            if entry[name] is not None:
                entry["source_refs"][name] = f"players[{index}].{upstream}[{ordinal}]"
        result["economy_log"].append(entry)
    for entries in result.values():
        entries.sort(key=lambda row: row["time"])
    return result
