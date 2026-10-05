"""Run user-owned programs through a small, framework-independent protocol."""

import importlib.metadata
import math
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..storage import (
    digest,
    file_hash,
    identifier,
    inside,
    now,
    read_json,
    verify_files,
    write_json,
)
from .contracts import ModelOutput
from .workspace import Workspace


def environment_info() -> dict[str, str]:
    result = {"python": sys.version.split()[0]}
    for name in (
        "dota2-item-timing",
        "gem-dota",
        "torch",
        "numpy",
        "pydantic",
        "pandas",
        "scikit-learn",
    ):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return result


def run_program(script: Path, arguments: list[str], folder: Path, timeout: float) -> list[str]:
    if not script.is_file():
        raise ValueError(f"Adapter script does not exist: {script}")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    command = [sys.executable, str(script.resolve()), *arguments]
    write_json(
        folder / "invocation.json",
        {
            "command": command,
            "cwd": str(script.resolve().parent),
            "timeout_seconds": timeout,
        },
    )
    shutil.copyfile(script, folder / "adapter.py")
    with (folder / "process.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            cwd=script.resolve().parent,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    if completed.returncode:
        raise ValueError(f"Adapter exited {completed.returncode}; inspect {folder / 'process.log'}")
    return command


def model_output(folder: Path) -> tuple[ModelOutput, dict[str, str]]:
    result = ModelOutput.model_validate(read_json(folder / "model.json"))
    fingerprints = {"model.json": file_hash(folder / "model.json")}
    for relative in result.artifacts:
        if relative in ("registry.json", "model.json"):
            raise ValueError(f"Reserved artifact name: {relative}")
        path = inside(folder, relative)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Model artifact is missing or empty: {relative}")
        fingerprints[relative] = file_hash(path)
    return result, fingerprints


def train(
    workspace: Workspace,
    dataset_id: str,
    trainer: Path,
    *,
    parameters: Path | None = None,
    timeout: float = 86400,
) -> dict[str, Any]:
    _, dataset_dir = workspace.dataset(dataset_id)
    trainer = trainer.resolve()
    if not trainer.is_file():
        raise ValueError(f"Trainer does not exist: {trainer}")
    config = read_json(parameters) if parameters else {}
    if not isinstance(config, dict):
        raise ValueError("Trainer configuration must be a JSON object")
    run_id = "run-" + uuid.uuid4().hex[:16]
    folder = workspace.root / "runs" / run_id
    output = folder / "output"
    output.mkdir(parents=True)
    write_json(folder / "config.json", config)
    state = {
        "schema_version": "coach-run/1",
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "running",
        "started_at": now(),
        "finished_at": None,
        "trainer_sha256": file_hash(trainer),
        "environment": environment_info(),
        "config": config,
    }
    write_json(folder / "run.json", state)
    try:
        state["command"] = run_program(
            trainer,
            [
                "--dataset",
                str(dataset_dir),
                "--output",
                str(output),
                "--config",
                str(folder / "config.json"),
            ],
            folder,
            timeout,
        )
        result, fingerprints = model_output(output)
        workspace.dataset(dataset_id)  # Adapters must not mutate dataset snapshots.
        state.update(status="succeeded", model=result.model_dump(), files=fingerprints)
    except BaseException as error:
        state.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            error=str(error),
            finished_at=now(),
        )
        write_json(folder / "run.json", state)
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ValueError(f"Run {run_id} failed: {error}") from error
    state["finished_at"] = now()
    write_json(folder / "run.json", state)
    return state


def register_model(workspace: Workspace, run_id: str) -> dict[str, Any]:
    workspace.config()
    folder = workspace.root / "runs" / identifier(run_id)
    run = read_json(folder / "run.json")
    if run.get("status") != "succeeded":
        raise ValueError("Only a succeeded run can be registered")
    workspace.dataset(run["dataset_id"])
    output = folder / "output"
    verify_files(output, run["files"])
    description, fingerprints = model_output(output)
    identity = {
        "schema_version": "coach-registry/1",
        "run_id": run_id,
        "dataset_id": run["dataset_id"],
        "model": description.model_dump(),
        "files": fingerprints,
    }
    model_id = digest(identity)[:24]
    destination = workspace.root / "models" / model_id
    with tempfile.TemporaryDirectory(dir=workspace.root / ".staging") as temporary:
        staging = Path(temporary) / "model"
        staging.mkdir()
        for relative in fingerprints:
            target = inside(staging, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(inside(output, relative), target)
        write_json(
            staging / "registry.json", {**identity, "model_id": model_id, "registered_at": now()}
        )
        if destination.exists():
            load_model(workspace, model_id)
        else:
            staging.rename(destination)
    return {"model_id": model_id, "path": str(destination), "dataset_id": run["dataset_id"]}


def load_model(workspace: Workspace, model_id: str) -> tuple[dict[str, Any], Path]:
    workspace.config()
    folder = workspace.root / "models" / identifier(model_id)
    registry = read_json(folder / "registry.json")
    identity = {k: v for k, v in registry.items() if k not in ("model_id", "registered_at")}
    if digest(identity)[:24] != model_id or registry.get("schema_version") != "coach-registry/1":
        raise ValueError("Model registry fingerprint mismatch")
    verify_files(folder, registry["files"])
    ModelOutput.model_validate(registry["model"])
    return registry, folder
