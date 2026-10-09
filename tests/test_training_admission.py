"""Synthetic evidence exercises admission controls; no real semantic approval is asserted."""

import copy
from unittest.mock import patch

import pytest
from test_coach_workflow import write_trainer
from test_data_preparation import fixture

from dota_items.data.contracts import PreparationConfig
from dota_items.data.pipeline import build_samples
from dota_items.storage import file_hash, read_json, write_json
from dota_items.workflow.admission import admission_template, check_admission
from dota_items.workflow.cli import main
from dota_items.workflow.contracts import Labels
from dota_items.workflow.datasets import build_dataset
from dota_items.workflow.jobs import train
from dota_items.workflow.workspace import Workspace


@pytest.fixture
def reviewed(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.init()
    for match_id in range(100, 103):
        raw = fixture(match_id)
        # Deliberately exercise the real-input branch using synthetic test data only.
        raw.pop("_fixture")
        source = tmp_path / "test-input.json"
        write_json(source, raw)
        workspace.import_json(source)
        workspace.annotate(
            match_id,
            Labels(
                tier="high_mmr",
                patch="test",
                role=1,
                player_slots=[0],
                label_source="SYNTHETIC TEST ONLY, not rank evidence",
            ),
        )
    observations = build_dataset(workspace, patch="test", role=1)
    samples = build_samples(workspace, observations["dataset_id"], PreparationConfig())
    dataset_id = samples["dataset_id"]
    review = admission_template(workspace, dataset_id)
    evidence = tmp_path / "synthetic-evidence.txt"
    evidence.write_text("Synthetic control-flow evidence, not a real review")
    review.update(
        status="passed",
        reviewer="unit test",
        reviewed_at="2026-10-08",
        limitations="Synthetic test only",
        tasks=["item"],
        evidence_files={evidence.name: file_hash(evidence)},
    )
    for match in review["matches"]:
        for check in match["checks"].values():
            check.update(
                status="passed", compared=1, evidence=[evidence.name], notes="Synthetic check"
            )
    path = tmp_path / "review.json"
    write_json(path, review)
    return workspace, dataset_id, path, review, observations["dataset_id"]


def test_unreviewed_training_blocked_before_process_or_run_creation(reviewed, tmp_path):
    workspace, dataset_id, _, _, _ = reviewed
    with patch("dota_items.workflow.jobs.run_program") as process:
        with pytest.raises(ValueError, match="held"):
            train(workspace, dataset_id, write_trainer(tmp_path / "train.py"))
        process.assert_not_called()
    assert not list((workspace.root / "runs").iterdir())


def test_template_is_held_and_cli_returns_failure(reviewed):
    workspace, dataset_id, path, _, _ = reviewed
    write_json(path, admission_template(workspace, dataset_id))
    assert (
        main(
            [
                "--workspace",
                str(workspace.root),
                "check-admission",
                dataset_id,
                "--admission",
                str(path),
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "held",
        "manifest",
        "match",
        "slot",
        "duplicate",
        "domain",
        "missing",
        "mismatch",
        "zero",
        "evidence",
        "task",
        "schema",
        "blank",
    ],
)
def test_invalid_or_incomplete_reviews_rejected(reviewed, mutation):
    workspace, dataset_id, path, original, _ = reviewed
    review = copy.deepcopy(original)
    check = review["matches"][0]["checks"]["clock"]
    if mutation == "held":
        check["status"] = "held"
    elif mutation == "manifest":
        review["manifest_sha256"] = "0" * 64
    elif mutation == "match":
        review["matches"].pop()
    elif mutation == "slot":
        review["matches"][0]["player_slots"] = [1]
    elif mutation == "duplicate":
        review["matches"].append(review["matches"][0])
    elif mutation == "domain":
        del review["matches"][0]["checks"]["economy"]
    elif mutation == "missing":
        check["missing"] = 1
    elif mutation == "mismatch":
        check["mismatched"] = 1
    elif mutation == "zero":
        check["compared"] = 0
    elif mutation == "evidence":
        check["evidence"] = ["absent.txt"]
    elif mutation == "task":
        review["tasks"] = []
    elif mutation == "schema":
        review["feature_schema"] = "coach-observer/1"
    elif mutation == "blank":
        review["reviewer"] = " "
    write_json(path, review)
    with pytest.raises(ValueError):
        check_admission(workspace, dataset_id, path)


def test_evidence_tampering_and_observation_bypass_rejected(reviewed):
    workspace, dataset_id, path, _, observations = reviewed
    with pytest.raises(ValueError, match="sample snapshot"):
        check_admission(workspace, observations, path)
    (path.parent / "synthetic-evidence.txt").write_text("changed")
    with pytest.raises(ValueError, match="fingerprint"):
        check_admission(workspace, dataset_id, path)


def test_approved_run_snapshots_evidence_and_rejects_unreviewed_model_tasks(reviewed, tmp_path):
    workspace, dataset_id, path, review, _ = reviewed
    trainer = write_trainer(tmp_path / "train.py")
    trainer.write_text(
        trainer.read_text()
        .replace("train.jsonl", "train.features.jsonl")
        .replace("test/1", "coach-features/1")
        .replace('["item", "route"]', '["item"]')
    )
    run = train(workspace, dataset_id, trainer, admission=path)
    folder = workspace.root / "runs" / run["run_id"]
    assert read_json(folder / "admission.json") == review
    assert (folder / "admission-evidence/synthetic-evidence.txt").is_file()
    assert file_hash(folder / "admission.json") == run["admission_sha256"]
    trainer.write_text(trainer.read_text().replace('["item"]', '["route"]'))
    with pytest.raises(ValueError, match="exceeds reviewed"):
        train(workspace, dataset_id, trainer, admission=path)
