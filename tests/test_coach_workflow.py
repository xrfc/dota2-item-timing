import copy
import json
import shutil
import types
from pathlib import Path

import pytest
from test_replay_ingestion import DEMO, fake_match, install_fake_gem

from dota_items.sources.gem_observations import observations
from dota_items.sources.gem_replay import canonicalize_match, ingest_demo
from dota_items.workflow.cli import ingest, initialize, main
from dota_items.workflow.contracts import Labels, Predictions
from dota_items.workflow.datasets import build_dataset
from dota_items.workflow.demo import demo
from dota_items.workflow.jobs import load_model, register_model, train
from dota_items.workflow.reviews import review, validate_predictions
from dota_items.workflow.storage import file_hash, read_json, write_json, writer_lock
from dota_items.workflow.validation import validate_match
from dota_items.workflow.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    initialize(workspace)
    demo(workspace)
    return workspace


def dataset_id(workspace):
    return workspace.status()["datasets"][0]


def synthetic_match(workspace):
    _, folder = workspace.record(1000000100)
    return read_json(folder / "normalized.json")


def write_trainer(path: Path, body: str | None = None) -> Path:
    path.write_text(
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--dataset", type=Path)
p.add_argument("--output", type=Path)
p.add_argument("--config", type=Path)
a = p.parse_args()
assert (a.dataset / "train.jsonl").is_file()
assert json.loads(a.config.read_text()) == {}
print("Test adapter executed; no model learned")
"""
        + (
            body
            if body is not None
            else """
(a.output / "weights.bin").write_bytes(b"infrastructure-test-fixture")
(a.output / "model.json").write_text(json.dumps({
    "schema_version": "coach-model/1", "framework": "test-fixture", "feature_schema": "test/1",
    "tasks": ["item", "route"], "artifacts": ["weights.bin"], "metrics": {},
    "notes": "Fake artifact used only to test orchestration"
}))
"""
        ),
        encoding="utf-8",
    )
    return path


def write_predictor(path: Path, reference="players[0].position_log[1]") -> Path:
    path.write_text(
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--model", type=Path)
p.add_argument("--match", type=Path)
p.add_argument("--player-slot", type=int)
p.add_argument("--output", type=Path)
a = p.parse_args()
registry = json.loads((a.model / "registry.json").read_text())
match = json.loads(a.match.read_text())
output = {"schema_version": "coach-predictions/1", "model_id": registry["model_id"],
    "match_id": match["match_id"], "player_slot": a.player_slot,
    "decisions": [{"time_seconds": 10, "task": "route", "observed_action": "test",
        "alternatives": [{"label": "<script>test</script>", "score": 0.8}],
        "evidence_refs": [REFERENCE], "note": "synthetic prediction"}]}
a.output.write_text(json.dumps(output))
""".replace("REFERENCE", repr(reference)),
        encoding="utf-8",
    )
    return path


def test_offline_demo_cli_is_repeatable(tmp_path, capsys):
    args = ["--workspace", str(tmp_path / "demo"), "demo"]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["dataset"]["dataset_id"] == second["dataset"]["dataset_id"]
    assert second["doctor"]["validated_matches"] == 6
    assert Path(second["report"]).is_file()


def test_dataset_grouping_filtering_and_snapshot_independence(workspace):
    manifest, folder = workspace.dataset(dataset_id(workspace))
    ids = [row["match_id"] for row in manifest["matches"]]
    assert len(ids) == len(set(ids)) == 6
    split_ids = [
        {json.loads(row)["match_id"] for row in (folder / f"{s}.jsonl").read_text().splitlines()}
        for s in ("train", "validation", "test")
    ]
    assert all(split_ids)
    assert not (
        split_ids[0] & split_ids[1] or split_ids[0] & split_ids[2] or split_ids[1] & split_ids[2]
    )
    workspace.annotate(
        1000000100,
        Labels(
            tier="synthetic",
            patch="synthetic",
            role=2,
            player_slots=[0],
            label_source="new annotation",
        ),
    )
    assert workspace.dataset(manifest["dataset_id"])[0] == manifest
    with pytest.raises(ValueError, match="at least 3"):
        build_dataset(workspace, patch="synthetic", role=1)  # Synthetic is opt-in.


def test_real_references_exclude_personal_and_unknown(workspace, tmp_path):
    raw = synthetic_match(workspace)
    del raw["_fixture"]
    for index, tier in enumerate(["pro", "pro", "high_mmr", "personal", "unknown"]):
        raw["match_id"] = 200 + index
        path = tmp_path / f"{index}.json"
        write_json(path, raw)
        workspace.import_json(path)
        workspace.annotate(
            raw["match_id"],
            Labels(
                tier=tier,
                patch="test-patch",
                role=1,
                player_slots=[0],
                label_source="test metadata",
            ),
        )
    result = build_dataset(workspace, patch="test-patch", role=1, hero_id=44, require_spatial=True)
    manifest, _ = workspace.dataset(result["dataset_id"])
    assert {row["match_id"] for row in manifest["matches"]} == {200, 201, 202}
    assert result["split_matches"] == {"train": 1, "validation": 1, "test": 1}


def test_missing_channels_do_not_enter_spatial_dataset(workspace, tmp_path):
    raw = synthetic_match(workspace)
    raw["match_id"] = 300
    raw["players"][0].pop("position_log")
    path = tmp_path / "no-position.json"
    write_json(path, raw)
    workspace.import_json(path)
    workspace.annotate(
        300,
        Labels(tier="synthetic", patch="synthetic", role=1, player_slots=[0], label_source="test"),
    )
    result = build_dataset(
        workspace, patch="synthetic", role=1, require_spatial=True, allow_synthetic=True
    )
    assert any(row["match_id"] == 300 for row in result["excluded"])


def test_duplicate_and_conflicting_matches(workspace, tmp_path):
    raw = synthetic_match(workspace)
    path = tmp_path / "copy.json"
    write_json(path, raw)
    assert workspace.import_json(path)["status"] == "cached"
    raw["players"][0]["purchase_log"][0]["key"] = "branches"
    write_json(path, raw)
    with pytest.raises(ValueError, match="different content"):
        workspace.import_json(path)
    assert workspace.status()["matches"] == 6


def test_corruption_and_workspace_move(workspace, tmp_path):
    moved = tmp_path / "moved workspace"
    shutil.move(workspace.root, moved)
    relocated = Workspace(moved)
    assert relocated.doctor()["ok"]
    _, folder = relocated.dataset(dataset_id(relocated))
    (folder / "train.jsonl").write_text("corrupt", encoding="utf-8")
    assert not relocated.doctor()["ok"]
    with pytest.raises(ValueError, match="changed artifact"):
        relocated.dataset(folder.name)


def test_import_batch_continues_and_records_failure(workspace, tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "bad.json").write_text("broken")
    write_json(inputs / "good.json", synthetic_match(workspace))
    result = ingest(workspace, inputs, force=False, recursive=True)
    assert not result["ok"]
    assert [row["status"] for row in result["results"]] == ["failed", "cached"]
    assert (workspace.root / "imports" / f"{result['batch_id']}.json").is_file()


def test_writer_lock_prevents_catalog_races(workspace):
    with writer_lock(workspace.root):
        with pytest.raises(ValueError, match="writer is busy"):
            workspace.annotate(
                1000000100,
                Labels(
                    tier="synthetic",
                    patch="synthetic",
                    role=1,
                    player_slots=[0],
                    label_source="test",
                ),
            )


def test_pause_aware_observations_never_invent_missing_values():
    match = fake_match()
    match.game_clock = types.SimpleNamespace(game_seconds_at=lambda tick: {30: 0, 90: 1}.get(tick))
    player = match.players[0]
    player.position_log = [(30, 1.0, 2.0), (60, 3.0, 4.0), (90, float("nan"), 1)]
    player.times = [30, 90]
    player.gold_t = [50]
    result = observations(player, 0, match)
    assert [row["time"] for row in result["position_log"]] == [0]
    assert result["economy_log"][1]["gold"] is None
    match.game_clock = None
    assert observations(player, 0, match) == {"position_log": [], "economy_log": []}


def test_gem_evidence_ingest_and_cache_invalidation(tmp_path, monkeypatch):
    source = tmp_path / "match.dem"
    source.write_bytes(DEMO)
    calls = []
    install_fake_gem(monkeypatch, calls)
    imported = ingest_demo(source, tmp_path / "cache")
    path = Path(imported["normalized_json"])
    assert validate_match(path)["match_id"] == 42
    raw = read_json(path)
    raw["schema_version"] = "gem-adapter/1.0"
    write_json(path, raw)
    assert ingest_demo(source, tmp_path / "cache")["status"] == "imported"
    assert len(calls) == 2
    raw_path = path.parent / "raw-gem.json"
    original = read_json(raw_path)
    original["players"][0]["purchase_log"][0]["value_name"] = "item_wrong"
    write_json(raw_path, original)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_match(path)
    normalized = read_json(path)
    normalized["evidence_sha256"] = file_hash(raw_path)
    write_json(path, normalized)
    with pytest.raises(ValueError, match="item mismatch"):
        validate_match(path)


def test_model_execution_registration_and_review(workspace, tmp_path):
    trainer = write_trainer(tmp_path / "train adapter.py")
    run = train(workspace, dataset_id(workspace), trainer)
    assert run["status"] == "succeeded"
    registered = register_model(workspace, run["run_id"])
    assert register_model(workspace, run["run_id"]) == registered
    predictor = write_predictor(tmp_path / "predict adapter.py")
    result = review(workspace, 1000000100, 0, model_id=registered["model_id"], predictor=predictor)
    html = Path(result["report"]).read_text(encoding="utf-8")
    assert result["status"] == "succeeded"
    assert "&lt;script&gt;test&lt;/script&gt;" in html and "<script>" not in html
    predictions = read_json(Path(result["report"]).parent / "predictions.json")
    assert any("独立" in message for message in predictions["limitations"])
    _, model_dir = load_model(workspace, registered["model_id"])
    (model_dir / "weights.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed artifact"):
        load_model(workspace, registered["model_id"])


@pytest.mark.parametrize(
    "body,message",
    [
        ("raise SystemExit(7)", "exited 7"),
        ("pass", "model.json"),
        ('(a.output / "model.json").write_text("{}")', "validation errors"),
    ],
)
def test_failed_training_keeps_logs_and_cannot_register(workspace, tmp_path, body, message):
    trainer = write_trainer(tmp_path / "fail.py", body)
    with pytest.raises(ValueError, match=message):
        train(workspace, dataset_id(workspace), trainer)
    state = workspace.status()["runs"][0]
    assert state["status"] == "failed"
    assert (workspace.root / "runs" / state["run_id"] / "process.log").is_file()
    with pytest.raises(ValueError, match="succeeded"):
        register_model(workspace, state["run_id"])


def test_training_timeout_is_recorded(workspace, tmp_path):
    trainer = write_trainer(tmp_path / "slow.py", "import time; time.sleep(5)")
    with pytest.raises(ValueError, match="timed out"):
        train(workspace, dataset_id(workspace), trainer, timeout=0.05)
    assert workspace.status()["runs"][0]["status"] == "failed"


def test_template_has_no_fake_training_success(workspace):
    with pytest.raises(ValueError, match="failed"):
        train(workspace, dataset_id(workspace), workspace.root / "adapters/train.py")
    assert workspace.status()["models"] == []


def test_future_evidence_rejected_and_review_failure_recorded(workspace, tmp_path):
    run = train(workspace, dataset_id(workspace), write_trainer(tmp_path / "train.py"))
    model = register_model(workspace, run["run_id"])
    predictor = write_predictor(tmp_path / "predict.py", "players[0].purchase_log[1]")
    with pytest.raises(ValueError, match="Future evidence"):
        review(workspace, 1000000100, 0, model_id=model["model_id"], predictor=predictor)
    assert any(row["status"] == "failed" for row in workspace.status()["reviews"])


@pytest.mark.parametrize(
    "reference", ["players[1].position_log[0]", "players[0].position_log[1].x"]
)
def test_wrong_evidence_scope_rejected(workspace, reference):
    predictions = Predictions.model_validate(
        {
            "model_id": "test",
            "match_id": 1000000100,
            "player_slot": 0,
            "decisions": [
                {
                    "time_seconds": 10,
                    "task": "route",
                    "evidence_refs": [reference],
                    "alternatives": [{"label": "test", "score": 0.5}],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="Evidence"):
        validate_predictions(predictions, synthetic_match(workspace), 0, "test")


def test_artifact_traversal_rejected(workspace, tmp_path):
    trainer = write_trainer(
        tmp_path / "bad-artifact.py",
        """
(a.output / "model.json").write_text(json.dumps({
 "framework": "test", "feature_schema": "test/1", "tasks": ["item"],
 "artifacts": ["../escape.bin"], "metrics": {}}))
""",
    )
    with pytest.raises(ValueError, match="relative artifact path"):
        train(workspace, dataset_id(workspace), trainer)


def test_nonfinite_predictions_and_invalid_time_series_rejected(workspace, tmp_path):
    raw = copy.deepcopy(synthetic_match(workspace))
    raw["players"][0]["position_log"].reverse()
    path = tmp_path / "unsorted.json"
    write_json(path, raw)
    with pytest.raises(ValueError, match="Unordered"):
        validate_match(path)
    with pytest.raises(ValueError):
        Predictions.model_validate(
            {
                "model_id": "test",
                "match_id": 1,
                "player_slot": 0,
                "decisions": [
                    {
                        "time_seconds": float("nan"),
                        "task": "item",
                        "evidence_refs": ["x"],
                        "alternatives": [{"label": "test", "score": 0.5}],
                    }
                ],
            }
        )


def test_canonicalizer_exports_time_series_without_final_statistics():
    match = fake_match()
    match.players[0].position_log = [(30, 100, 200)]
    match.players[0].times = [30]
    match.players[0].net_worth_t = [700]
    match.players[0].gold_per_min = 9999  # End-of-game aggregate must not become a feature.
    canonical, _ = canonicalize_match(match)
    player = canonical["players"][0]
    assert player["position_log"][0]["time"] == 1
    assert player["economy_log"][0]["net_worth"] == 700
    assert "gold_per_min" not in player
