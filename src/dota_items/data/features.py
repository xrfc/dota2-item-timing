"""Backward-only state alignment; future outcomes live in a separate table."""

from bisect import bisect_right

import pandas as pd

from .contracts import ECONOMY, NUMERIC, PreparationConfig


def aligned(times, rows, fields, tolerance):
    left = pd.DataFrame({"time": [float(t) for t in times]})
    if not rows:
        return [{**{k: None for k in fields}, "age": None, "ref": None} for _ in times]
    right = pd.DataFrame([
        {"observed_time": float(r["time"]), "ref": r["input_ref"],
         **{k: r.get(k) for k in fields}} for r in rows
    ])
    merged = pd.merge_asof(
        left, right, left_on="time", right_on="observed_time",
        direction="backward", tolerance=float(tolerance),
    )
    result = []
    for row in merged.to_dict("records"):
        result.append({
            **{k: None if pd.isna(row[k]) else float(row[k]) for k in fields},
            "age": None if pd.isna(row["observed_time"]) else row["time"] - row["observed_time"],
            "ref": None if pd.isna(row["ref"]) else row["ref"],
        })
    return result


def extract_samples(match: dict, quality: dict, config: PreparationConfig, slots=None):
    """Return X, y and trace rows keyed by sample_id; no target fields enter X."""
    features, labels, traces = [], [], []
    players = [p for p in match["players"] if slots is None or p["player_slot"] in slots]
    if slots is not None and set(slots) != {p["player_slot"] for p in players}:
        raise ValueError("Requested player slot absent from match")
    times = list(range(0, match["duration"] + 1, config.step_seconds))
    if len(times) * len(players) > config.max_samples_per_match:
        raise ValueError("Sample count exceeds preparation resource limit")
    for player in players:
        slot = player["player_slot"]
        positions = aligned(times, player["position_log"], ("x", "y"),
                            config.max_observation_age_seconds)
        economy = aligned(times, player["economy_log"], ECONOMY,
                          config.max_observation_age_seconds)
        # Endpoint is sampled at or before t+H, never beyond that label horizon.
        endpoints = aligned([t + config.horizon_seconds for t in times],
                            player["position_log"], ("x", "y"),
                            config.route_tolerance_seconds)
        purchases = player["purchase_log"] or []
        purchase_times = [r["time"] for r in purchases]
        coverage = player["purchase_coverage"]
        for i, time in enumerate(times):
            sample_id = f"{match['match_id']}:{slot}:{time}"
            end = time + config.horizon_seconds
            pos, econ, endpoint = positions[i], economy[i], endpoints[i]
            start_index = bisect_right(purchase_times, time - config.history_seconds)
            stop_index = bisect_right(purchase_times, time)
            recent = purchases[start_index:stop_index]
            # Counts describe observed records, not inventory nor exhaustive event history.
            observed = quality["channels"][str(slot)]["purchase_log"]["available"]
            row = {
                "sample_id": sample_id, "hero_id": player["hero_id"], "time_seconds": time,
                "x": pos["x"], "y": pos["y"], "position_age": pos["age"],
                **{k: econ[k] for k in ECONOMY}, "economy_age": econ["age"],
                "recent_purchase_count": len(recent) if observed else None,
            }
            for item in config.candidate_items:
                row[f"recent_{item}_count"] = sum(r["key"] == item for r in recent) if observed else None
            for key in (*NUMERIC, *(f"recent_{item}_count" for item in config.candidate_items)):
                row[f"{key}_missing"] = int(row[key] is None)
            features.append(row)
            target = {
                "sample_id": sample_id, "item_action": None, "item_mask": False,
                "item_reason": "coverage_unknown", "route_dx": None, "route_dy": None,
                "route_mask": False, "route_reason": "position_unavailable",
            }
            future = purchases[stop_index:bisect_right(purchase_times, end)]
            item_refs = []
            if end > match["duration"]:
                target["item_reason"] = target["route_reason"] = "right_censored"
            else:
                covered = coverage and coverage["start_seconds"] <= time and end <= coverage["end_seconds"]
                if future or covered:
                    # Multiple different items bought at the first timestamp have no known order.
                    first = [r for r in future if r["time"] == future[0]["time"]] if future else []
                    keys = {r["key"] for r in first}
                    if len(keys) > 1:
                        target["item_reason"] = "simultaneous_purchases"
                    else:
                        key = first[0]["key"] if first else None
                        target.update(
                            item_action=(key if key in config.candidate_items else "other")
                            if first else "no_purchase",
                            item_mask=True, item_reason="next_observed_purchase" if first else "covered_no_purchase",
                        )
                        item_refs = [r["input_ref"] for r in first]
                endpoint_time = end - endpoint["age"] if endpoint["age"] is not None else None
                if pos["x"] is not None and endpoint_time is not None and endpoint_time > time:
                    target.update(route_dx=endpoint["x"] - pos["x"],
                                  route_dy=endpoint["y"] - pos["y"], route_mask=True,
                                  route_reason="observed_endpoint")
            labels.append(target)
            traces.append({
                "sample_id": sample_id, "match_id": match["match_id"], "player_slot": slot,
                "cutoff_seconds": time, "horizon_end_seconds": end,
                "feature_refs": [ref for ref in [pos["ref"], econ["ref"]] if ref]
                + [r["input_ref"] for r in recent],
                "label_refs": item_refs + ([endpoint["ref"]] if target["route_mask"] else []),
                "purchase_coverage": coverage,
                "route_endpoint_seconds": end - endpoint["age"] if target["route_mask"] else None,
            })
    return features, labels, traces
