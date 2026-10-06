"""Reclean saved real parser exports; this command does not claim to reparse demo bytes."""

import argparse
import shutil
from collections import Counter
from pathlib import Path

import gem

from dota_items.data.acceptance import audit_prepared, compare_api_observations
from dota_items.data.contracts import PreparationConfig
from dota_items.data.pipeline import prepare_one
from dota_items.storage import file_hash, read_json, write_json
from dota_items.workflow.validation import resolve_ref
from dota_items.workflow.workspace import Workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/acceptance"))
    parser.add_argument("--output", type=Path, default=Path("data/regression"))
    args = parser.parse_args()
    source_report = read_json(args.source / "report.json")
    results = []
    for original in source_report["results"]:
        match_id = original["match_id"]
        if "archive_sha256" not in original:
            continue
        replay = args.source / "replays" / f"{match_id}.dem.bz2"
        if file_hash(replay) != original["archive_sha256"]:
            raise ValueError(f"Archive fingerprint mismatch for {match_id}")
        cached = list(
            (args.source / "workspaces" / str(match_id) / "cache" / "matches").glob(
                "*/normalized.json"
            )
        )
        if len(cached) != 1:
            raise ValueError(f"Expected one saved parser export for {match_id}")
        api = read_json(args.source / "metadata" / f"{match_id}.json")
        workspace = Workspace(args.output / "workspaces" / str(match_id))
        workspace.init()
        prepared = prepare_one(workspace, cached[0], PreparationConfig())
        folder = Path(prepared["path"])
        audit = audit_prepared(folder, api)
        normalized = read_json(folder / "input.json")
        cleaned = read_json(folder / "cleaned.json")
        raw = read_json(folder / "raw.json")
        quality = read_json(folder / "quality.json")
        clock = gem.from_dict({"game_clock": raw.get("game_clock")}).game_clock
        examples = []
        for issue in quality["issues"]:
            if issue["reason"] == "conflicting sampled states at same time":
                row = resolve_ref(normalized, issue["source_ref"])
                examples.append({"reference": issue["source_ref"], "row": row})
                if len(examples) == 8:
                    break
        diagnostic = {
            "game_clock": raw.get("game_clock"),
            "post_game_tick": raw.get("post_game_tick"),
            "raw_players": [
                {
                    "player_id": p["player_id"],
                    "hero_id": p["hero_id"],
                    "hero_name": p["hero_name"],
                    "positions": len(p["position_log"]),
                    "economy_samples": len(p["times"]),
                    "first_sample_time": clock.game_seconds_at(p["times"][0])
                    if clock and p["times"]
                    else None,
                }
                for p in raw["players"]
            ],
            "conflict_examples": examples,
            "cleaning_actions": dict(Counter(i["action"] for i in quality["issues"])),
            "api_rank_tiers": dict(Counter(p.get("rank_tier") for p in api["players"])),
            "api_leaver_status": {
                str(p["player_slot"]): p.get("leaver_status") for p in api["players"]
            },
        }
        result = {
            "match_id": match_id,
            "archive_sha256": original["archive_sha256"],
            "preparation": prepared,
            "audit": audit,
            "source_diagnostics": diagnostic,
            "api_comparison_before": compare_api_observations(normalized, api),
            "api_comparison_after": compare_api_observations(cleaned, api),
        }
        results.append(result)
        exports = args.output / "exports" / str(match_id)
        exports.mkdir(parents=True, exist_ok=True)
        for name in (
            "cleaned.json",
            "quality.json",
            "manifest.json",
            "features.jsonl",
            "labels.jsonl",
            "trace.jsonl",
        ):
            shutil.copyfile(folder / name, exports / name)
        write_json(
            args.output / "report.json",
            {
                "schema_version": "saved-replay-regression/1",
                "parser_exports_reused": True,
                "source_report_sha256": file_hash(args.source / "report.json"),
                "results": results,
            },
        )
        print(f"Audited {match_id}: {audit['pipeline_status']}", flush=True)


if __name__ == "__main__":
    main()
