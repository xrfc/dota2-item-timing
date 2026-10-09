"""Conservative per-team observations, never hidden enemy coordinates or future outcomes."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict

OBSERVER_SCHEMA = "coach-observer/1"


def player_id(slot):
    return slot if slot < 5 else slot - 128 + 5


class Timeline:
    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda r: (r["time"], r.get("source_tick", -1)))
        self.times = [r["time"] for r in self.rows]
        self.keys = [(r["time"], r.get("source_tick", -1)) for r in self.rows]

    def before(self, cutoff):
        # Gem game_seconds_at is integer-valued. Use only completed seconds,
        # excluding the cutoff bucket so later ticks in that second cannot leak.
        index = bisect_left(self.times, cutoff) - 1
        return self.rows[index] if index >= 0 else None

    def at_tick(self, time, tick):
        index = bisect_right(self.keys, (time, tick)) - 1
        return self.rows[index] if index >= 0 else None

    def window(self, start, end):
        return self.rows[bisect_left(self.times, start) : bisect_left(self.times, end)]


class ObserverIndex:
    def __init__(self, match):
        self.match_id = match["match_id"]
        self.players = match["players"]
        context = match.get("context") or {}
        self.channels = context.get("channels", {})
        self.available = {key: value is not None for key, value in self.channels.items()}
        grouped = defaultdict(list)
        for row in self.channels.get("hero_visibility_events") or []:
            grouped[row["payload"]["player_id"]].append(row)
        self.visibility = {pid: Timeline(rows) for pid, rows in grouped.items()}
        self.seen = {}
        self.hidden = {}
        for team in ("radiant", "dire"):
            for player in self.players:
                pid = player_id(player["player_slot"])
                vis = self.visibility.get(pid, Timeline([]))
                seen, hidden = [], []
                previous = None
                since = None
                for event in vis.rows:
                    state = event["payload"][team + "_state"]
                    identity = self.identity(event)
                    if state == "hidden" and previous and self.identity(previous) == identity:
                        prior_state = previous["payload"][team + "_state"]
                        if prior_state == "visible":
                            since = event["time"]
                        elif prior_state != "hidden":
                            since = None
                    else:
                        since = None
                    hidden.append({**event, "hidden_since": since})
                    previous = event
                for pos in player.get("position_log", []):
                    tick = pos.get("source_tick")
                    if type(tick) is not int:
                        continue
                    event = vis.at_tick(pos["time"], tick)
                    if event and event["payload"][team + "_state"] == "visible":
                        seen.append(
                            {
                                **pos,
                                "identity": self.identity(event),
                                "visibility_ref": event["source_ref"],
                            }
                        )
                self.seen[team, pid] = Timeline(seen)
                self.hidden[team, pid] = Timeline(hidden)
        states = defaultdict(lambda: defaultdict(list))
        for row in self.channels.get("coach_state_snapshots") or []:
            states[row["payload"]["player_id"]][row["time"]].append(row)
        self.states = {}
        for pid, seconds in states.items():
            safe = []
            for time, rows in seconds.items():
                payloads = [{k: v for k, v in r["payload"].items() if k != "tick"} for r in rows]
                safe.append(
                    rows[-1]
                    if all(p == payloads[0] for p in payloads)
                    else {
                        "time": time,
                        "source_tick": rows[-1]["source_tick"],
                        "conflict": True,
                    }
                )
            self.states[pid] = Timeline(safe)
        self.events = {}
        for team in ("radiant", "dire"):
            self.events[team] = Timeline(
                [
                    row
                    for row in self.channels.get("combat_log") or []
                    if row["payload"].get("visible_" + team) is True
                ]
            )

    @staticmethod
    def identity(row):
        payload = row["payload"]
        return payload["entity_index"], payload["entity_serial"]

    def sample(self, slot, cutoff, max_age=30, history=120):
        team = "radiant" if slot < 5 else "dire"
        enemies = []
        for player in self.players:
            other = player["player_slot"]
            if (other < 5) == (slot < 5):
                continue
            pid = player_id(other)
            event = self.hidden[team, pid].before(cutoff)
            last = self.seen[team, pid].before(cutoff)
            if not event or (last and last["identity"] != self.identity(event)):
                last = None
            state = event["payload"][team + "_state"] if event else "unknown"
            since = event["hidden_since"] if event else None
            enemies.append(
                {
                    "player_slot": other,
                    "hero_id": player["hero_id"],
                    "visibility": state,
                    "visibility_ref": event["source_ref"] if event else None,
                    "hidden_since": since,
                    "hidden_for_seconds": cutoff - since if since is not None else None,
                    "last_seen": {
                        "time": last["time"],
                        "x": last["x"],
                        "y": last["y"],
                        "age_seconds": cutoff - last["time"],
                        "source_ref": last.get("source_ref"),
                        "visibility_ref": last["visibility_ref"],
                    }
                    if last
                    else None,
                }
            )
        own = self.states.get(player_id(slot), Timeline([])).before(cutoff)
        status = "unavailable"
        if own:
            status = (
                "conflicting"
                if own.get("conflict")
                else "stale"
                if cutoff - own["time"] > max_age
                else "sampled"
            )
        events = self.events[team].window(max(0, cutoff - history), cutoff)
        counts = dict(Counter(row["payload"]["log_type"] for row in events))
        # Event projections have a bounded display size; total counts retain all
        # explicitly visible events in the window. Never copy whole-match summaries.
        projected = [
            {
                "time": row["time"],
                "source_ref": row["source_ref"],
                **{
                    key: row["payload"].get(key)
                    for key in (
                        "log_type",
                        "attacker_name",
                        "target_name",
                        "inflictor_name",
                        "value",
                        "damage_type",
                    )
                },
            }
            for row in events[-50:]
        ]
        return {
            "schema_version": OBSERVER_SCHEMA,
            "sample_id": f"{self.match_id}:{slot}:{cutoff}",
            "observer_slot": slot,
            "observer_team": team,
            "cutoff_seconds": cutoff,
            "cutoff_policy": "strictly_before_completed_game_second",
            "availability": self.available,
            "self_state_status": status,
            "self_state": {"time": own["time"], "source_ref": own["source_ref"], **own["payload"]}
            if status == "sampled"
            else None,
            "enemies": enemies,
            "observed_combat_counts": counts
            if self.channels.get("combat_log") is not None
            else None,
            "observed_events": projected,
            "events_truncated": len(events) > 50,
            "admission": "semantic_review_required",
        }


def observer_samples(match, config, slots=None):
    if match.get("context") is None:
        return []
    index = ObserverIndex(match)
    return [
        index.sample(
            p["player_slot"], time, config.max_observation_age_seconds, config.history_seconds
        )
        for p in match["players"]
        if slots is None or p["player_slot"] in slots
        for time in range(0, match["duration"] + 1, config.step_seconds)
    ]
