"""Versioned replay context, kept separate from observer-safe model inputs."""

from ..sources.gem_observations import number

CONTEXT_SCHEMA = "coach-context/1"
CHANNELS = (
    "hero_visibility_events",
    "entity_visibility_events",
    "combat_log",
    "wards",
    "smoke_events",
    "vision_modifiers",
    "coach_state_snapshots",
)
COMBAT_TYPES = {
    "DAMAGE",
    "HEAL",
    "DEATH",
    "ABILITY",
    "ITEM",
    "MODIFIER_ADD",
    "MODIFIER_REMOVE",
    "BUYBACK",
}
VISIBILITY = {"visible", "hidden", "unknown"}
VISIBILITY_CHANNELS = {"hero_visibility_events", "entity_visibility_events"}


def export_context(raw, clock, duration):
    """Retain exact raw payloads/references; absent channels remain None, not empty."""
    context = {"schema_version": CONTEXT_SCHEMA, "channels": {}, "excluded": {}}
    for channel in CHANNELS:
        source = raw.get(channel)
        if source is None or clock is None:
            context["channels"][channel] = None
            continue
        if not isinstance(source, list):
            raise ValueError(f"Raw {channel} must be a list")
        rows, excluded = [], 0
        for i, payload in enumerate(source):
            if not isinstance(payload, dict):
                raise ValueError(f"Raw {channel}[{i}] must be an object")
            if channel == "combat_log" and payload.get("log_type") not in COMBAT_TYPES:
                excluded += 1
                continue
            tick = payload.get("tick")
            if type(tick) is not int:
                raise ValueError(f"Raw {channel}[{i}] has no integer tick")
            time = clock.game_seconds_at(tick)
            minimum = -3600 if channel in VISIBILITY_CHANNELS else 0
            if not number(time) or not minimum <= time <= duration:
                excluded += 1
                continue
            rows.append(
                {
                    "time": time,
                    "source_tick": tick,
                    "source_ref": f"{channel}[{i}]",
                    "payload": payload,
                }
            )
        context["channels"][channel] = sorted(
            rows, key=lambda row: (row["time"], row["source_tick"])
        )
        context["excluded"][channel] = excluded
    return context


def check_payload(channel, payload):
    if not isinstance(payload, dict) or type(payload.get("tick")) is not int:
        raise ValueError("payload requires an integer tick")
    if channel in ("hero_visibility_events", "entity_visibility_events"):
        if any(payload.get(k) not in VISIBILITY for k in ("radiant_state", "dire_state")):
            raise ValueError("invalid visibility state")
        if any(type(payload.get(k)) is not int for k in ("entity_index", "entity_serial")):
            raise ValueError("visibility requires entity identity")
    if channel in ("hero_visibility_events", "coach_state_snapshots"):
        if type(payload.get("player_id")) is not int or payload["player_id"] not in range(10):
            raise ValueError("invalid context player_id")
    if channel == "combat_log":
        if payload.get("log_type") not in COMBAT_TYPES:
            raise ValueError("unsupported context combat type")
        for key in ("visible_radiant", "visible_dire"):
            if payload.get(key) is not None and type(payload[key]) is not bool:
                raise ValueError("event visibility must be bool or null")
        for key in ("value", "location_x", "location_y", "stun_duration"):
            if payload.get(key) is not None and not number(payload[key]):
                raise ValueError(f"invalid combat {key}")
    if channel == "coach_state_snapshots":
        for key in ("hp", "max_hp", "mana", "max_mana", "level"):
            value = payload.get(key)
            if value is not None and (not number(value) or value < 0):
                raise ValueError(f"invalid state {key}")
        if payload.get("life_state") is not None and (
            type(payload["life_state"]) is not int or payload["life_state"] not in (0, 1, 2)
        ):
            raise ValueError("invalid life_state")
        if not isinstance(payload.get("items"), dict) or any(
            str(k) not in {str(i) for i in range(17)} or not isinstance(v, str) or not v
            for k, v in payload["items"].items()
        ):
            raise ValueError("invalid inventory slots/items")
        unknown = payload.get("inventory_unknown_slots")
        if not isinstance(unknown, list) or any(
            type(x) is not int or x not in range(17) for x in unknown
        ):
            raise ValueError("invalid inventory missingness")
        if type(payload.get("inventory_complete")) is not bool or payload["inventory_complete"] != (
            not unknown
        ):
            raise ValueError("inconsistent inventory completeness")
        if not isinstance(payload.get("ability_levels"), dict) or any(
            not isinstance(k, str) or type(v) is not int or v < 0
            for k, v in payload["ability_levels"].items()
        ):
            raise ValueError("invalid ability levels")
        handles = payload.get("inventory_handles")
        if handles is not None:
            if (
                not isinstance(handles, dict)
                or set(handles) != {str(i) for i in range(17)}
                or any(v is not None and (type(v) is not int or v < 0) for v in handles.values())
                or type(payload.get("inventory_empty_handle")) is not int
            ):
                raise ValueError("invalid inventory handle evidence")
            expected = [
                i
                for i in range(17)
                if handles[str(i)] is None
                or (
                    handles[str(i)] != payload["inventory_empty_handle"]
                    and str(i) not in payload["items"]
                )
            ]
            if unknown != expected:
                raise ValueError("inventory missingness disagrees with handle evidence")


def check_channel(channel, rows, duration, max_rows=500000):
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > max_rows:
        raise ValueError("context channel must be a bounded list or null")
    previous = (-float("inf"), -float("inf"))
    refs = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "time",
            "source_tick",
            "source_ref",
            "payload",
        }:
            raise ValueError("invalid context row structure")
        minimum = -3600 if channel in VISIBILITY_CHANNELS else 0
        if not number(row["time"]) or not minimum <= row["time"] <= duration:
            raise ValueError("invalid context time")
        tick = row["source_tick"]
        if type(tick) is not int or (row["time"], tick) < previous:
            raise ValueError("context rows must be ordered by time/tick")
        previous = (row["time"], tick)
        ref = row["source_ref"]
        if not isinstance(ref, str) or not ref.startswith(channel + "[") or ref in refs:
            raise ValueError("invalid/duplicate context reference")
        refs.add(ref)
        check_payload(channel, row["payload"])
        if row["payload"]["tick"] != tick:
            raise ValueError("context tick mismatch")


def context_header(context):
    if not isinstance(context, dict) or context.get("schema_version") != CONTEXT_SCHEMA:
        raise ValueError("Unsupported replay context")
    if not isinstance(context.get("channels"), dict) or set(context["channels"]) != set(CHANNELS):
        raise ValueError("Context channels must explicitly declare missing channels")


def clean_context(match, config, issue):
    context = match.get("context")
    if context is None:
        return {}
    context_header(context)
    stats = {}
    for channel, rows in context["channels"].items():
        try:
            check_channel(channel, rows, match["duration"], config.max_rows_per_channel)
        except ValueError as error:
            # Losing a visibility transition makes later state unsafe. Disable the
            # whole channel, retain the input evidence, and never claim completeness.
            issue(f"context.channels.{channel}", str(error))
            context["channels"][channel] = None
        retained = context["channels"][channel]
        stats[channel] = {"available": retained is not None, "rows": len(retained or [])}
    return stats


def validate_context(match, evidence, external, resolve_ref):
    context = match.get("context")
    if context is None:
        return
    context_header(context)
    clock = None
    if external and any(context["channels"].values()):
        import gem

        clock = gem.from_dict({"game_clock": evidence.get("game_clock")}).game_clock
    for channel, rows in context["channels"].items():
        check_channel(channel, rows, match["duration"])
        for row in rows or []:
            if external:
                source = resolve_ref(evidence, row["source_ref"])
                if source != row["payload"]:
                    raise ValueError("Context evidence payload mismatch")
                if clock is None or clock.game_seconds_at(row["source_tick"]) != row["time"]:
                    raise ValueError("Context evidence time mismatch")
