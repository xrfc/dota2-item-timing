"""Freeze curated matches into deterministic, match-disjoint dataset snapshots."""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..storage import (
    digest,
    hashes,
    json_bytes,
    now,
    read_json,
    verify_files,
    write_json,
    writer_lock,
)
from .contracts import Labels
from .workspace import Workspace


def build_dataset(
    workspace: Workspace,
    *,
    patch: str,
    role: int,
    hero_id: int | None = None,
    require_spatial: bool = False,
    allow_synthetic: bool = False,
) -> dict[str, Any]:
    config = workspace.config()
    if role not in range(1, 6) or not patch.strip():
        raise ValueError("Specify patch and a role from 1 to 5")
    with writer_lock(workspace.root):
        selected = []
        excluded = []
        for match_id, record in sorted(workspace.catalog()["matches"].items()):
            reason = None
            labels = Labels.model_validate(record["labels"]) if record["labels"] else None
            allowed_tiers = {"synthetic"} if allow_synthetic else {"pro", "high_mmr"}
            if labels is None or labels.tier not in allowed_tiers:
                reason = "unlabeled or wrong tier (personal/unknown are never training references)"
            elif labels.patch != patch or labels.role != role:
                reason = "patch or role filter"
            if reason:
                excluded.append({"match_id": int(match_id), "reason": reason})
                continue
            _, folder = workspace.record(int(match_id))
            match = read_json(folder / "normalized.json")
            slots = []
            for player in match["players"]:
                slot = player["player_slot"]
                if slot not in labels.player_slots or (hero_id and player["hero_id"] != hero_id):
                    continue
                quality = record["channels"][str(slot)]
                if quality["purchases"] != "present":
                    continue
                if require_spatial and not (quality["positions"] and quality["economy"]):
                    continue
                slots.append(slot)
            if not slots:
                excluded.append(
                    {"match_id": int(match_id), "reason": "no player passes channel/hero filters"}
                )
                continue
            selected.append(
                {
                    "match_id": int(match_id),
                    "bundle_id": record["bundle_id"],
                    "player_slots": sorted(slots),
                    "labels": labels.model_dump(),
                    "channels": {str(s): record["channels"][str(s)] for s in slots},
                    "source_path": folder,
                }
            )
        if len(selected) < 3:
            raise ValueError(
                "Need at least 3 eligible distinct matches for train/validation/test; "
                f"got {len(selected)}. "
                "Import and annotate more matches, or inspect filters and channel availability."
            )
        ordered = sorted(selected, key=lambda row: digest([config.seed, row["match_id"]]))
        n_validation = max(1, int(len(ordered) * config.validation_fraction))
        n_test = max(1, int(len(ordered) * config.test_fraction))
        if n_validation + n_test >= len(ordered):
            raise ValueError("Split fractions leave no training matches")
        splits = {
            "validation": ordered[:n_validation],
            "test": ordered[n_validation : n_validation + n_test],
            "train": ordered[n_validation + n_test :],
        }
        with tempfile.TemporaryDirectory(dir=workspace.root / ".staging") as temporary:
            staging = Path(temporary) / "snapshot"
            staging.mkdir()
            match_rows = []
            for split, records in splits.items():
                rows = []
                for record in records:
                    relative = f"matches/{record['match_id']}"
                    shutil.copytree(record["source_path"], staging / relative)
                    row = {k: v for k, v in record.items() if k != "source_path"}
                    row.update({"split": split, "path": f"{relative}/normalized.json"})
                    rows.append(row)
                    match_rows.append(row)
                (staging / f"{split}.jsonl").write_bytes(
                    b"".join(json_bytes(row).replace(b"\n", b" ").rstrip() + b"\n" for row in rows)
                )
            identity = {
                "schema_version": "coach-dataset/1",
                "observation_schema": "coach-match/1",
                "config": config.model_dump(),
                "filters": {
                    "patch": patch,
                    "role": role,
                    "hero_id": hero_id,
                    "require_spatial": require_spatial,
                    "synthetic_only": allow_synthetic,
                },
                "matches": sorted(match_rows, key=lambda row: row["match_id"]),
                "files": hashes(staging),
                "limitations": [
                    "This snapshot contains time series, not training windows or labels.",
                    "Trainers must enforce decision-time cutoffs and fit transforms on train only.",
                    "Sample counts are not independent match counts; splits are grouped by match.",
                    "Tier/role/patch are user-supplied labels, not inferred from the replay.",
                    "Enemy visibility, inventory availability and life state are unavailable.",
                ],
            }
            dataset_id = digest(identity)[:24]
            destination = workspace.root / "datasets" / dataset_id
            manifest = {**identity, "dataset_id": dataset_id, "created_at": now()}
            write_json(staging / "manifest.json", manifest)
            if destination.exists():
                workspace.dataset(dataset_id)
            else:
                staging.rename(destination)
            verify_files(destination, identity["files"])
        return {
            "dataset_id": dataset_id,
            "path": str(destination),
            "split_matches": {name: len(rows) for name, rows in splits.items()},
            "excluded": excluded,
        }
