"""Reparse hash-verified local demos and record context coverage; never grant training approval."""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from dota_items.data.observer import ObserverIndex
from dota_items.storage import file_hash, read_json, write_json
from dota_items.workflow.workspace import Workspace


def inspect_preparation(workspace, preparation_id):
    manifest, folder = workspace.preparation(preparation_id)
    match = read_json(folder / "cleaned.json")
    channels = match["context"]["channels"]
    observations = [
        json.loads(line) for line in (folder / "observer.jsonl").read_text().splitlines()
    ]
    feature_ids = [
        json.loads(line)["sample_id"]
        for line in (folder / "features.jsonl").read_text().splitlines()
    ]
    assert [row["sample_id"] for row in observations] == feature_ids
    states = channels["coach_state_snapshots"] or []
    combat = channels["combat_log"] or []
    index = ObserverIndex(match)
    # Inspect a hidden enemy at a real cutoff and perturb every hidden position.
    # Its last known position must remain invariant. Restore before inspecting others.
    probe = next(
        (
            r
            for r in observations
            if any(e["visibility"] == "hidden" and e["last_seen"] is not None for e in r["enemies"])
        ),
        None,
    )
    leakage_checked = False
    if probe:
        team = probe["observer_team"]
        restored = []
        for player in match["players"]:
            slot = player["player_slot"]
            if (slot < 5) == (team == "radiant"):
                continue
            pid = slot if slot < 5 else slot - 123
            visibility = index.visibility.get(pid)
            for pos in player["position_log"]:
                row = visibility.at_tick(pos["time"], pos["source_tick"]) if visibility else None
                if row is None or row["payload"][team + "_state"] != "visible":
                    restored.append((pos, pos["x"], pos["y"]))
                    pos.update(x=1e9, y=-1e9)
        cutoff = probe["cutoff_seconds"]
        cfg = manifest["config"]
        actual = ObserverIndex(match).sample(
            probe["observer_slot"],
            cutoff,
            cfg["max_observation_age_seconds"],
            cfg["history_seconds"],
        )
        assert actual == probe, "Hidden enemy coordinates leaked into observer output"
        for pos, x, y in restored:
            pos.update(x=x, y=y)
        leakage_checked = bool(restored)
    return {
        "match_id": match["match_id"],
        "preparation_id": preparation_id,
        "manifest_sha256": file_hash(folder / "manifest.json"),
        "raw_sha256": file_hash(folder / "raw.json"),
        "observer_sha256": file_hash(folder / "observer.jsonl"),
        "adapter": match["schema_version"],
        "capture": match.get("capture_version"),
        "adapter_fingerprint": match.get("adapter_fingerprint"),
        "dependencies": manifest["dependencies"],
        "code": manifest["code"],
        "counts": manifest["counts"],
        "quality": read_json(folder / "quality.json")["quarantined"],
        "channel_rows": {k: len(v) if v is not None else None for k, v in channels.items()},
        "state_nulls": {
            k: sum(r["payload"].get(k) is None for r in states)
            for k in ("hp", "max_hp", "mana", "max_mana", "level", "life_state")
        },
        "inventory_complete": sum(r["payload"]["inventory_complete"] for r in states),
        "inventory_unknown_slots": dict(
            Counter(str(s) for r in states for s in r["payload"]["inventory_unknown_slots"])
        ),
        "combat_types": dict(Counter(r["payload"]["log_type"] for r in combat)),
        "combat_visibility": {
            team: dict(Counter(str(r["payload"].get("visible_" + team)) for r in combat))
            for team in ("radiant", "dire")
        },
        "self_state_status": dict(Counter(r["self_state_status"] for r in observations)),
        "enemy_visibility": dict(
            Counter(e["visibility"] for r in observations for e in r["enemies"])
        ),
        "known_last_seen": sum(
            e["last_seen"] is not None for r in observations for e in r["enemies"]
        ),
        "real_hidden_position_perturbation_passed": leakage_checked,
        "sample_identity_alignment_passed": True,
        "state_example": states[0]["payload"] if states else None,
        "training_admission": "held_semantic_review_required",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cohort", type=Path, default=Path("docs/acceptance/7.41f-2026-10-06.json")
    )
    parser.add_argument("--match-ids", type=int, nargs="+", required=True)
    args = parser.parse_args()
    report_path = args.output / "report.json"
    if report_path.exists():
        raise ValueError("Use a new output directory; existing audit reports are immutable")
    args.output.mkdir(parents=True, exist_ok=True)
    cohort = {row["match_id"]: row for row in read_json(args.cohort)["matches"]}
    report = {
        "schema_version": "context-replay-audit/1",
        "binary_reparsed": True,
        "source_cohort_sha256": file_hash(args.cohort),
        "results": [],
    }
    failed = False
    for mid in args.match_ids:
        source = args.replays / f"{mid}.dem.bz2"
        if file_hash(source) != cohort[mid]["archive_sha256"]:
            raise ValueError(f"Replay hash mismatch: {mid}")
        root = args.output / "workspaces" / str(mid)
        start = time.monotonic()
        with (args.output / f"{mid}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dota_items.workflow.cli",
                    "--workspace",
                    str(root),
                    "prepare",
                    str(source),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
                check=False,
            )
        if result.returncode:
            failed = True
            row = {"match_id": mid, "status": "failed", "log": f"{mid}.log"}
        else:
            batch = read_json(args.output / f"{mid}.log")
            row = inspect_preparation(Workspace(root), batch["results"][0]["preparation_id"])
            row.update(status="prepared_and_audited", archive_sha256=file_hash(source))
        row["wall_seconds"] = round(time.monotonic() - start, 3)
        report["results"].append(row)
        write_json(report_path, report)
        print(mid, row["status"], row["wall_seconds"], flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
