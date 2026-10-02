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
# Read train.jsonl / validation.jsonl / test.jsonl relative to args.dataset.
# Fit scalers, vocabularies and weights on train only. Never use test for tuning.
# Slice observations by decision time; construct targets separately from future data.
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
