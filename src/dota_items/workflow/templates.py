"""Starter adapters intentionally do not claim to implement a learned model."""

TRAINER = '''"""Implement your trainer here; the workflow owns datasets, logs, and artifacts."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--config", type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
config = json.loads(args.config.read_text(encoding="utf-8"))
# For coach-samples/1, preprocessing is already fitted on train only:
# import numpy as np
# with np.load(args.dataset / "train.npz", allow_pickle=False) as batch:
#     X = batch["X"]
#     mask = batch["item_mask"]
#     X_item, y_item = X[mask], batch["item_target"][mask]
#     route_mask = batch["route_mask"]
#     X_route, y_route = X[route_mask], batch["route_target"][route_mask]
# Never train on item_target=-1 or unmasked zero-filled route placeholders.
# Copy preprocessor.json into output artifacts for identical inference transforms.
# train.features/labels/trace.jsonl provide readable rows and source references.
# coach-dataset/1 instead contains observation bundles: run build-samples first.
# Never fit parameters or tune using test. See docs/data-pipeline.md.
# Write checkpoints beneath args.output and a model.json matching contracts/model.schema.json.
# See docs/coach-workflow.md for the output protocol.
raise SystemExit("Trainer is not implemented yet. Add your model here in the next phase.")
'''

PREDICTOR = '''"""Implement model inference here; no training is required by this interface."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=Path, required=True)
parser.add_argument("--match", type=Path, required=True)
parser.add_argument("--player-slot", type=int, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
registry = json.loads((args.model / "registry.json").read_text(encoding="utf-8"))
match = json.loads(args.match.read_text(encoding="utf-8"))
# Load your registered artifacts from args.model, using the same feature transforms as training.
# Each prediction may consume observations only at or before its decision time.
# Reference whole rows in the normalized match, e.g. players[0].position_log[12].
# Write args.output using contracts/predictions.schema.json and registry["model_id"].
raise SystemExit("Predictor is not implemented yet. Add inference in the next phase.")
'''
