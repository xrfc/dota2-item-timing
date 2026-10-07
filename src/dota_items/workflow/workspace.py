"""A workspace is movable: catalog and artifact paths are always relative."""

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..storage import (
    digest,
    hashes,
    identifier,
    inside,
    now,
    read_json,
    verify_files,
    write_json,
    writer_lock,
)
from .contracts import Labels, WorkspaceConfig
from .validation import validate_match


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def init(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        with writer_lock(self.root):
            for name in (
                "inbox/reference",
                "inbox/personal",
                "cache",
                "replays",
                "datasets",
                "prepared",
                "runs",
                "models",
                "reviews",
                ".staging",
            ):
                (self.root / name).mkdir(parents=True, exist_ok=True)
            config = self.root / "workspace.json"
            if not config.exists():
                write_json(config, WorkspaceConfig().model_dump())
            if not (self.root / "catalog.json").exists():
                write_json(
                    self.root / "catalog.json", {"schema_version": "coach-catalog/1", "matches": {}}
                )
        return {"workspace": str(self.root), "status": "ready"}

    def config(self) -> WorkspaceConfig:
        if not (self.root / "workspace.json").is_file():
            raise ValueError("Workspace is not initialized; run dota-coach init")
        return WorkspaceConfig.model_validate(read_json(self.root / "workspace.json"))

    def catalog(self) -> dict[str, Any]:
        self.config()
        value = read_json(self.root / "catalog.json")
        if value.get("schema_version") != "coach-catalog/1":
            raise ValueError("Unsupported catalog schema")
        return value

    def record(self, match_id: int) -> tuple[dict[str, Any], Path]:
        record = self.catalog()["matches"].get(str(match_id))
        if record is None:
            raise ValueError(f"Match {match_id} is not imported")
        folder = inside(self.root, record["path"])
        verify_files(folder, record["files"])
        return record, folder

    def import_json(self, path: Path, *, demo_sha256: str | None = None) -> dict[str, Any]:
        self.config()
        path = path.resolve()
        quality = validate_match(path)
        match_id = quality["match_id"]
        with writer_lock(self.root):
            catalog = self.catalog()
            with tempfile.TemporaryDirectory(dir=self.root / ".staging") as temporary:
                staging = Path(temporary) / "bundle"
                staging.mkdir()
                normalized = read_json(path)
                if quality["evidence_path"] is not None:
                    shutil.copyfile(quality["evidence_path"], staging / "raw.json")
                    normalized["evidence_source"] = "raw.json"
                write_json(staging / "normalized.json", normalized)
                validate_match(staging / "normalized.json")
                quality.pop("evidence_path")
                write_json(staging / "quality.json", quality)
                fingerprint = hashes(staging)
                bundle_id = digest(fingerprint)[:24]
                destination = self.root / "replays" / f"{match_id}-{bundle_id}"
                existing = catalog["matches"].get(str(match_id))
                if existing:
                    self.record(match_id)
                    if existing["files"] != fingerprint:
                        raise ValueError(
                            f"Match {match_id} already exists with different content; "
                            "use a separate workspace for a new parser version"
                        )
                    return {"status": "cached", "match_id": match_id, "bundle_id": bundle_id}
                if destination.exists():
                    # Recover a fully published bundle after a crash before catalog commit.
                    verify_files(destination, fingerprint)
                else:
                    staging.rename(destination)
                catalog["matches"][str(match_id)] = {
                    "match_id": match_id,
                    "bundle_id": bundle_id,
                    "path": destination.relative_to(self.root).as_posix(),
                    "files": fingerprint,
                    "demo_sha256": demo_sha256,
                    "labels": None,
                    "synthetic": quality["synthetic"],
                    "imported_at": now(),
                    "channels": quality["channels"],
                    "warnings": quality["warnings"],
                }
                write_json(self.root / "catalog.json", catalog)
        return {
            "status": "imported",
            "match_id": match_id,
            "bundle_id": bundle_id,
            "warnings": quality["warnings"],
        }

    def annotate(self, match_id: int, labels: Labels) -> dict[str, Any]:
        with writer_lock(self.root):
            record, folder = self.record(match_id)
            slots = {p["player_slot"] for p in read_json(folder / "normalized.json")["players"]}
            if not set(labels.player_slots) <= slots:
                raise ValueError("Selected player slots are absent from the match")
            if record["synthetic"] != (labels.tier == "synthetic"):
                raise ValueError(
                    "Synthetic data must be labeled synthetic and cannot be relabeled real"
                )
            catalog = self.catalog()
            catalog["matches"][str(match_id)]["labels"] = labels.model_dump()
            write_json(self.root / "catalog.json", catalog)
        return {"match_id": match_id, "labels": labels.model_dump()}

    def dataset(self, dataset_id: str) -> tuple[dict[str, Any], Path]:
        self.config()
        folder = self.root / "datasets" / identifier(dataset_id)
        manifest = read_json(folder / "manifest.json")
        if manifest.get("schema_version") not in ("coach-dataset/1", "coach-samples/1"):
            raise ValueError("Unsupported dataset schema")
        identity = {k: v for k, v in manifest.items() if k not in ("dataset_id", "created_at")}
        if digest(identity)[:24] != dataset_id:
            raise ValueError("Dataset manifest fingerprint mismatch")
        verify_files(folder, manifest["files"])
        return manifest, folder

    def preparation(self, preparation_id: str) -> tuple[dict[str, Any], Path]:
        folder = self.root / "prepared" / identifier(preparation_id)
        manifest = read_json(folder / "manifest.json")
        identity = {k: v for k, v in manifest.items() if k not in ("preparation_id", "created_at")}
        if (
            manifest.get("schema_version")
            not in ("coach-preparation/1", "coach-preparation/2", "coach-preparation/3")
            or digest(identity)[:24] != preparation_id
        ):
            raise ValueError("Preparation manifest fingerprint mismatch")
        verify_files(folder, manifest["files"])
        return manifest, folder

    def status(self) -> dict[str, Any]:
        catalog = self.catalog()
        matches = list(catalog["matches"].values())
        return {
            "workspace": str(self.root),
            "matches": len(matches),
            "prepared": sorted(p.name for p in (self.root / "prepared").glob("*") if p.is_dir()),
            "unlabeled_matches": sum(record["labels"] is None for record in matches),
            "match_ids": sorted(record["match_id"] for record in matches),
            "datasets": sorted(p.name for p in (self.root / "datasets").iterdir() if p.is_dir()),
            "models": sorted(p.name for p in (self.root / "models").iterdir() if p.is_dir()),
            "runs": [read_json(p) for p in sorted((self.root / "runs").glob("*/run.json"))],
            "reviews": [
                read_json(p) for p in sorted((self.root / "reviews").glob("*/review.json"))
            ],
        }

    def doctor(self) -> dict[str, Any]:
        self.config()
        checked = 0
        errors = []
        for match_id in self.catalog()["matches"]:
            try:
                _, folder = self.record(int(match_id))
                validate_match(folder / "normalized.json")
                checked += 1
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors.append(f"match {match_id}: {error}")
        for path in sorted((self.root / "datasets").iterdir()):
            if path.is_dir():
                try:
                    self.dataset(path.name)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"dataset {path.name}: {error}")
        for path in sorted((self.root / "prepared").glob("*")):
            if path.is_dir():
                try:
                    self.preparation(path.name)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"prepared {path.name}: {error}")
        return {
            "ok": not errors,
            "python": sys.version.split()[0],
            "replay_parser_installed": importlib.util.find_spec("gem") is not None,
            "validated_matches": checked,
            "errors": errors,
            "note": "Only .dem parsing needs the replay extra; no GPU or model is required.",
        }
