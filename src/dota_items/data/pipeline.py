"""One-file preparation and immutable, match-disjoint model-ready datasets."""

import importlib.metadata
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from ..sources.gem_replay import ingest_demo
from ..storage import digest, file_hash, hashes, inside, now, read_json, write_json, writer_lock
from ..workflow.validation import validate_match
from .cleaning import clean_match
from .contracts import FEATURE_SCHEMA, PIPELINE_VERSION, PreparationConfig
from .features import extract_samples
from .preprocessing import fit_preprocessor, save_arrays

MAX_JSON_BYTES = 256 * 1024**2


def dependencies():
    result = {}
    for name in ("pandas", "numpy", "scikit-learn", "gem-dota", "pydantic"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return result


def code_fingerprint():
    root = Path(__file__).resolve().parents[1]
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(root.rglob("*.py"))}


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def write_samples(folder, match, quality, config, slots=None):
    folder.mkdir(parents=True, exist_ok=True)
    features, labels, traces = extract_samples(match, quality, config, slots)
    for name, rows in (("features", features), ("labels", labels), ("trace", traces)):
        write_rows(folder / f"{name}.jsonl", rows)
    counts = {
        "samples": len(features),
        "item_supervised": sum(r["item_mask"] for r in labels),
        "route_supervised": sum(r["route_mask"] for r in labels),
    }
    write_json(folder / "quality.json", {**quality, **counts})
    return features, labels, counts


def read_input(path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Normalized JSON exceeds 256 MiB input limit")
    return read_json(path)


def prepare_one(workspace, path: Path, config: PreparationConfig, *, force=False):
    """Also import cleaned observations, so annotation/build-dataset needs no second upload."""
    source_sha = file_hash(path)
    parsed = None
    if path.suffix.lower() == ".json":
        input_path = path
    else:
        parsed = ingest_demo(path, workspace.root / "cache", force=force)
        input_path = Path(parsed["normalized_json"])
    raw = read_input(input_path)
    cleaned, quality = clean_match(raw, config)
    with tempfile.TemporaryDirectory(dir=workspace.root / ".staging") as temporary:
        staging = Path(temporary) / "prepared"
        staging.mkdir()
        # Preserve exact normalized input bytes; Gem evidence remains a separate immutable file.
        shutil.copyfile(input_path, staging / "input.json")
        if raw.get("evidence_source"):
            evidence = inside(input_path.parent, raw["evidence_source"])
            shutil.copyfile(evidence, staging / "raw.json")
            cleaned["evidence_source"] = "raw.json"
        write_json(staging / "cleaned.json", cleaned)
        # Validate surviving values and external raw evidence before publishing any samples.
        validate_match(staging / "cleaned.json")
        _, _, counts = write_samples(staging, cleaned, quality, config)
        try:
            validate_match(input_path)
            import_path = input_path
        except (ValueError, KeyError, TypeError):
            cleaned["cleaning_audit"] = {**quality, "input_sha256": file_hash(input_path)}
            write_json(staging / "cleaned.json", cleaned)
            import_path = staging / "cleaned.json"
        identity = {
            "schema_version": PIPELINE_VERSION, "feature_schema": FEATURE_SCHEMA,
            "source_sha256": source_sha, "match_id": cleaned["match_id"],
            "config": config.model_dump(), "dependencies": dependencies(),
            "code": code_fingerprint(), "counts": counts, "files": hashes(staging),
        }
        preparation_id = digest(identity)[:24]
        imported = workspace.import_json(
            import_path, demo_sha256=parsed.get("demo_sha256") if parsed else None
        )
        write_json(staging / "manifest.json", {
            **identity, "preparation_id": preparation_id, "created_at": now(),
        })
        destination = workspace.root / "prepared" / preparation_id
        with writer_lock(workspace.root):
            if destination.exists():
                workspace.preparation(preparation_id)
            else:
                staging.rename(destination)
    return {
        "status": "prepared", "preparation_id": preparation_id,
        "match_id": imported["match_id"], "path": str(destination), **counts,
        "quarantined": quality["quarantined"],
    }


def prepare(workspace, source, config: PreparationConfig, *, force=False):
    workspace.init()
    source = (source or workspace.root / "inbox").resolve()
    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = sorted(p for p in source.rglob("*") if p.is_file() and p.name.lower().endswith(
            (".json", ".dem", ".dem.bz2", ".dem.zst", ".dem.zip")))
    else:
        raise ValueError(f"Input does not exist: {source}")
    if not files:
        raise ValueError("No supported input files")
    batch = {"batch_id": "prepare-" + uuid.uuid4().hex[:16], "started_at": now(), "results": []}
    for path in files:
        try:
            result = prepare_one(workspace, path, config, force=force)
        except Exception as error:
            # Isolate a failed file; never silently publish partial features for it.
            result = {"status": "failed", "error_type": type(error).__name__, "error": str(error)}
        batch["results"].append({"source": str(path), **result})
        write_json(workspace.root / "imports" / f"{batch['batch_id']}.json", batch)
    batch.update(finished_at=now(), ok=all(r["status"] != "failed" for r in batch["results"]))
    write_json(workspace.root / "imports" / f"{batch['batch_id']}.json", batch)
    return batch


def build_samples(workspace, dataset_id: str, config: PreparationConfig):
    source_manifest, source = workspace.dataset(dataset_id)
    if source_manifest["schema_version"] != "coach-dataset/1":
        raise ValueError("build-samples requires an observation dataset, not prepared samples")
    grouped = {name: [] for name in ("train", "validation", "test")}
    all_ids = set()
    for row in source_manifest["matches"]:
        if row["match_id"] in all_ids:
            raise ValueError("Match appears more than once/across dataset splits")
        all_ids.add(row["match_id"])
        grouped[row["split"]].append(row)
    with writer_lock(workspace.root):
        with tempfile.TemporaryDirectory(dir=workspace.root / ".staging") as temporary:
            staging = Path(temporary) / "samples"
            staging.mkdir()
            split_rows, summaries = {}, {}
            for split, matches in grouped.items():
                features, labels, traces, qualities = [], [], [], []
                for row in matches:
                    raw = read_input(inside(source, row["path"]))
                    cleaned, quality = clean_match(raw, config)
                    x, y, trace = extract_samples(cleaned, quality, config, row["player_slots"])
                    features.extend(x)
                    labels.extend(y)
                    traces.extend(trace)
                    qualities.append({"match_id": row["match_id"], **quality})
                if not features:
                    raise ValueError(f"No samples in {split}")
                split_rows[split] = (features, labels)
                for kind, rows in (("features", features), ("labels", labels), ("trace", traces)):
                    write_rows(staging / f"{split}.{kind}.jsonl", rows)
                summaries[split] = {
                    "matches": len(matches), "samples": len(features),
                    "item_supervised": sum(r["item_mask"] for r in labels),
                    "route_supervised": sum(r["route_mask"] for r in labels),
                }
                write_json(staging / f"{split}.quality.json", qualities)
            if not any(summaries["train"][k] for k in ("item_supervised", "route_supervised")):
                raise ValueError("Train split has no supervised labels; inspect coverage/positions")
            state = fit_preprocessor(split_rows["train"][0])
            write_json(staging / "preprocessor.json", state)
            for split, (features, labels) in split_rows.items():
                save_arrays(staging / f"{split}.npz", features, labels, state, config)
            identity = {
                "schema_version": "coach-samples/1", "feature_schema": FEATURE_SCHEMA,
                "source_dataset_id": dataset_id, "source_manifest_sha256": file_hash(source / "manifest.json"),
                "preparation_version": PIPELINE_VERSION, "preparation_config": config.model_dump(),
                "filters": source_manifest["filters"], "config": source_manifest["config"],
                "matches": [{k: v for k, v in row.items() if k != "path"}
                            for row in source_manifest["matches"]],
                "dependencies": dependencies(), "code": code_fingerprint(),
                "splits": summaries, "item_classes": ["no_purchase", "other", *config.candidate_items],
                "feature_columns": state["output_columns"], "files": hashes(staging),
                "limitations": [
                    "Imitation labels describe observed behavior, not causal decision quality.",
                    "Purchase records are not completed builds or usable inventory.",
                    "Route target is endpoint displacement, not a safe/optimal route or map region.",
                    "No enemy visibility, life state, inventory or teammate context is modeled.",
                    "Honor task masks; unknown/censored labels are not negative examples.",
                    "Split is grouped by match; temporal/patch-disjoint evaluation remains separate.",
                ],
            }
            target_id = digest(identity)[:24]
            destination = workspace.root / "datasets" / target_id
            write_json(staging / "manifest.json", {**identity, "dataset_id": target_id, "created_at": now()})
            workspace.dataset(dataset_id)
            if destination.exists():
                workspace.dataset(target_id)
            else:
                staging.rename(destination)
    return {"dataset_id": target_id, "source_dataset_id": dataset_id,
            "path": str(destination), "splits": summaries}
