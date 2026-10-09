"""Versioned contracts shared by future trainers and predictors."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WorkspaceConfig(Contract):
    schema_version: Literal["coach-workspace/1"] = "coach-workspace/1"
    seed: int = 42
    validation_fraction: float = Field(default=0.15, gt=0, lt=1)
    test_fraction: float = Field(default=0.15, gt=0, lt=1)
    candidate_items: list[str] = Field(
        default_factory=lambda: ["power_treads", "desolator", "black_king_bar"]
    )

    @model_validator(mode="after")
    def validate_split(self):
        if self.validation_fraction + self.test_fraction >= 1:
            raise ValueError("validation_fraction + test_fraction must be below 1")
        if not self.candidate_items or any(not item.strip() for item in self.candidate_items):
            raise ValueError("candidate_items must contain nonempty item keys")
        return self


class Labels(Contract):
    tier: Literal["pro", "high_mmr", "personal", "unknown", "synthetic"] = "unknown"
    patch: str = Field(min_length=1)
    role: int = Field(ge=1, le=5)
    player_slots: list[int] = Field(min_length=1)
    label_source: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self):
        valid = {*range(5), *range(128, 133)}
        if len(set(self.player_slots)) != len(self.player_slots):
            raise ValueError("player_slots must be unique")
        if any(slot not in valid for slot in self.player_slots):
            raise ValueError("player_slots must use 0–4 or 128–132")
        if not self.patch.strip() or not self.label_source.strip():
            raise ValueError("patch and label_source cannot be blank")
        return self


class ModelOutput(Contract):
    schema_version: Literal["coach-model/1"] = "coach-model/1"
    framework: str = Field(min_length=1)
    feature_schema: str = Field(min_length=1)
    tasks: list[Literal["item", "route"]] = Field(min_length=1)
    artifacts: list[str] = Field(min_length=1)
    metrics: dict[str, float]
    notes: str = ""

    @model_validator(mode="after")
    def unique_artifacts(self):
        if len(set(self.artifacts)) != len(self.artifacts):
            raise ValueError("artifacts must be unique")
        return self


class Alternative(Contract):
    label: str = Field(min_length=1, max_length=300)
    score: float = Field(ge=0, le=1)


class Decision(Contract):
    time_seconds: float = Field(ge=0)
    task: Literal["item", "route"]
    observed_action: str | None = Field(default=None, max_length=300)
    alternatives: list[Alternative] = Field(min_length=1, max_length=10)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=3000)


class Predictions(Contract):
    schema_version: Literal["coach-predictions/1"] = "coach-predictions/1"
    model_id: str
    match_id: int = Field(gt=0)
    player_slot: int
    decisions: list[Decision] = Field(max_length=10000)
    limitations: list[str] = Field(default_factory=list)
