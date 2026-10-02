"""One entry point for preparing demonstrations and running future model adapters."""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from ..sources.gem_replay import ingest_demo
from .contracts import Labels, ModelOutput, Predictions, WorkspaceConfig
from .datasets import build_dataset
from .demo import demo
from .jobs import register_model, train
from .reviews import review
from .storage import now, write_json
from .templates import PREDICTOR, TRAINER
from .workspace import Workspace


def initialize(workspace: Workspace) -> dict:
    result = workspace.init()
    for name, model in (
        ("model", ModelOutput),
        ("predictions", Predictions),
        ("labels", Labels),
        ("workspace", WorkspaceConfig),
    ):
        write_json(workspace.root / "contracts" / f"{name}.schema.json", model.model_json_schema())
    folder = workspace.root / "adapters"
    folder.mkdir(exist_ok=True)
    for name, content in (("train.py", TRAINER), ("predict.py", PREDICTOR)):
        path = folder / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    return result


def ingest(workspace: Workspace, source: Path | None, *, force: bool, recursive: bool) -> dict:
    workspace.config()
    source = source or workspace.root / "inbox"
    if source.is_file():
        files = [source]
    elif source.is_dir():
        candidates = source.rglob("*") if recursive else source.iterdir()
        files = sorted(
            path
            for path in candidates
            if path.is_file()
            and path.name.lower().endswith((".dem", ".dem.bz2", ".dem.zst", ".dem.zip", ".json"))
        )
    else:
        raise ValueError(f"Input does not exist: {source}")
    if not files:
        raise ValueError(f"No supported replay or normalized JSON files in {source}")
    batch = {"batch_id": "import-" + uuid.uuid4().hex[:16], "started_at": now(), "results": []}
    for path in files:
        print(f"Importing {path.name} ...", file=sys.stderr, flush=True)
        try:
            if path.suffix.lower() == ".json":
                result = workspace.import_json(path)
            else:
                parsed = ingest_demo(path, workspace.root / "cache", force=force)
                result = workspace.import_json(
                    Path(parsed["normalized_json"]), demo_sha256=parsed.get("demo_sha256")
                )
            batch["results"].append({"source": path.name, **result})
        except Exception as error:
            batch["results"].append({"source": path.name, "status": "failed", "error": str(error)})
        write_json(workspace.root / "imports" / f"{batch['batch_id']}.json", batch)
    batch["finished_at"] = now()
    batch["ok"] = all(row["status"] != "failed" for row in batch["results"])
    write_json(workspace.root / "imports" / f"{batch['batch_id']}.json", batch)
    return batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DOTA2 coach data and model workflow")
    parser.add_argument(
        "--workspace", type=Path, default=Path(os.getenv("DOTA_COACH_WORKSPACE", "coach-workspace"))
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create workspace, adapter templates and JSON schemas")
    commands.add_parser("doctor", help="Validate environment and frozen data")
    commands.add_parser("status", help="List matches, datasets, runs, models and reviews")
    commands.add_parser(
        "demo", help="Exercise data/report infrastructure offline with synthetic data"
    )
    upload = commands.add_parser("ingest", help="Batch-import a folder or replay/normalized JSON")
    upload.add_argument("input", type=Path, nargs="?")
    upload.add_argument("--force", action="store_true", help="Reparse the intermediate cache")
    upload.add_argument("--no-recursive", action="store_true")
    label = commands.add_parser("annotate", help="Record expert provenance and selected players")
    label.add_argument("match_id", type=int)
    label.add_argument(
        "--tier", choices=["pro", "high_mmr", "personal", "unknown", "synthetic"], required=True
    )
    label.add_argument("--patch", required=True)
    label.add_argument("--role", type=int, choices=range(1, 6), required=True)
    label.add_argument("--player-slots", type=int, nargs="+", required=True)
    label.add_argument(
        "--label-source", required=True, help="Tournament, rank evidence, or personal"
    )
    dataset = commands.add_parser("build-dataset", help="Freeze a curated match-disjoint snapshot")
    dataset.add_argument("--patch", required=True)
    dataset.add_argument("--role", type=int, choices=range(1, 6), required=True)
    dataset.add_argument("--hero-id", type=int)
    dataset.add_argument(
        "--require-spatial", action="store_true", help="Require both position and economy channels"
    )
    dataset.add_argument(
        "--synthetic-only", action="store_true", help="Infrastructure testing only"
    )
    trainer = commands.add_parser("train", help="Run your future trainer and track its outputs")
    trainer.add_argument("dataset_id")
    trainer.add_argument("--trainer", type=Path)
    trainer.add_argument("--config", type=Path)
    trainer.add_argument("--timeout", type=float, default=86400)
    register = commands.add_parser("register-model", help="Freeze artifacts from a succeeded run")
    register.add_argument("run_id")
    report = commands.add_parser("review", help="Generate facts or invoke your model predictor")
    report.add_argument("match_id", type=int)
    report.add_argument("--player-slot", type=int, required=True)
    report.add_argument("--model")
    report.add_argument("--predictor", type=Path)
    report.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args(argv)
    workspace = Workspace(args.workspace)
    try:
        if args.command == "init":
            result = initialize(workspace)
        elif args.command == "demo":
            initialize(workspace)
            result = demo(workspace)
        elif args.command == "doctor":
            result = workspace.doctor()
        elif args.command == "status":
            result = workspace.status()
        elif args.command == "ingest":
            result = ingest(
                workspace, args.input, force=args.force, recursive=not args.no_recursive
            )
        elif args.command == "annotate":
            result = workspace.annotate(
                args.match_id,
                Labels(
                    tier=args.tier,
                    patch=args.patch,
                    role=args.role,
                    player_slots=args.player_slots,
                    label_source=args.label_source,
                ),
            )
        elif args.command == "build-dataset":
            result = build_dataset(
                workspace,
                patch=args.patch,
                role=args.role,
                hero_id=args.hero_id,
                require_spatial=args.require_spatial,
                allow_synthetic=args.synthetic_only,
            )
        elif args.command == "train":
            result = train(
                workspace,
                args.dataset_id,
                args.trainer or workspace.root / "adapters/train.py",
                parameters=args.config,
                timeout=args.timeout,
            )
        elif args.command == "register-model":
            result = register_model(workspace, args.run_id)
        else:
            predictor = args.predictor
            if args.model and predictor is None:
                predictor = workspace.root / "adapters/predict.py"
            result = review(
                workspace,
                args.match_id,
                args.player_slot,
                model_id=args.model,
                predictor=predictor,
                timeout=args.timeout,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("ok") is False else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Inspect status and logs before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
