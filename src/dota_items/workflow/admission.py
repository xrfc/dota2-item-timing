"""Human-reviewed admission for real legacy feature training, never inferred from coverage."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from ..data.contracts import FEATURE_SCHEMA, StrictContract
from ..storage import file_hash, inside, read_json

CHECKS = {"pipeline", "clock", "positions", "economy", "purchases", "labels_and_masks"}


class Check(StrictContract):
    status: Literal["held", "passed"] = "held"
    compared: int = Field(default=0, ge=0)
    mismatched: int = Field(default=0, ge=0)
    missing: int = Field(default=0, ge=0)
    evidence: list[str] = Field(default_factory=list)
    notes: str = ""


class MatchReview(StrictContract):
    match_id: int = Field(gt=0)
    player_slots: list[int]
    checks: dict[str, Check]


class Admission(StrictContract):
    schema_version: Literal["coach-training-admission/1"] = "coach-training-admission/1"
    dataset_id: str
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_schema: Literal["coach-features/1"] = "coach-features/1"
    tasks: list[Literal["item", "route"]]
    status: Literal["held", "passed"] = "held"
    reviewer: str = ""
    reviewed_at: str = ""
    limitations: str = ""
    evidence_files: dict[str, str] = Field(default_factory=dict)
    matches: list[MatchReview]


def synthetic_only(manifest):
    rows = manifest.get("matches", [])
    return (
        manifest.get("filters", {}).get("synthetic_only") is True
        and bool(rows)
        and all(row.get("labels", {}).get("tier") == "synthetic" for row in rows)
    )


def admission_template(workspace, dataset_id):
    manifest, folder = workspace.dataset(dataset_id)
    if manifest["schema_version"] != "coach-samples/1":
        raise ValueError("Build samples first; admission is bound to the exact sample snapshot")
    if manifest.get("feature_schema") != FEATURE_SCHEMA:
        raise ValueError("Unsupported feature schema")
    return Admission(
        dataset_id=dataset_id,
        manifest_sha256=file_hash(folder / "manifest.json"),
        tasks=["item", "route"],
        matches=[
            MatchReview(
                match_id=row["match_id"],
                player_slots=row["player_slots"],
                checks={name: Check() for name in sorted(CHECKS)},
            )
            for row in manifest["matches"]
        ],
    ).model_dump()


def check_admission(workspace, dataset_id: str, path: Path | None):
    manifest, folder = workspace.dataset(dataset_id)
    if synthetic_only(manifest):
        return {
            "status": "synthetic_only",
            "limitations": "Infrastructure tests, not real training",
        }
    if path is None:
        raise ValueError(
            "Real training is held: supply --admission after independent semantic review"
        )
    if manifest["schema_version"] != "coach-samples/1":
        raise ValueError("Real training requires a reviewed sample snapshot; run build-samples")
    review = Admission.model_validate(read_json(path))
    if (
        review.dataset_id != dataset_id
        or review.manifest_sha256 != file_hash(folder / "manifest.json")
        or review.feature_schema != manifest.get("feature_schema")
    ):
        raise ValueError("Admission does not match this exact dataset/feature schema")
    if review.status != "passed" or not all(
        value.strip() for value in (review.reviewer, review.reviewed_at, review.limitations)
    ):
        raise ValueError("Admission is held or lacks reviewer/date/scope limitations")
    if not review.tasks or len(review.tasks) != len(set(review.tasks)):
        raise ValueError("Admission must name unique reviewed tasks")
    expected = {r["match_id"]: sorted(r["player_slots"]) for r in manifest["matches"]}
    actual = {r.match_id: sorted(r.player_slots) for r in review.matches}
    if len(expected) != len(manifest["matches"]) or len(actual) != len(review.matches):
        raise ValueError("Duplicate match in dataset or admission")
    if expected != actual:
        raise ValueError("Admission must cover every selected match/player across all splits")
    if not review.evidence_files:
        raise ValueError("Admission has no evidence files")
    for relative, sha in review.evidence_files.items():
        if len(sha) != 64 or file_hash(inside(path.parent, relative)) != sha:
            raise ValueError(f"Admission evidence fingerprint mismatch: {relative}")
    for match in review.matches:
        if set(match.checks) != CHECKS:
            raise ValueError("Admission must review every legacy feature/label domain")
        for name, check in match.checks.items():
            if (
                check.status != "passed"
                or check.compared <= 0
                or check.mismatched != 0
                or check.missing != 0
                or not check.notes.strip()
                or not check.evidence
                or not set(check.evidence) <= review.evidence_files.keys()
            ):
                raise ValueError(f"Admission held: match {match.match_id}, check {name}")
    return review.model_dump()
