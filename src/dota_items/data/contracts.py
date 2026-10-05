"""Strict contracts for preparation; no expert or completeness claims are inferred."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FEATURE_SCHEMA = "coach-features/1"
PIPELINE_VERSION = "coach-preparation/1"
ECONOMY = ("gold", "net_worth", "last_hits", "denies", "xp_progress")
NUMERIC = (
    "time_seconds", "x", "y", "position_age", *ECONOMY, "economy_age",
    "recent_purchase_count",
)
SLOTS = {*range(5), *range(128, 133)}


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class PreparationConfig(StrictContract):
    schema_version: Literal["coach-preparation-config/1"] = "coach-preparation-config/1"
    step_seconds: int = Field(default=30, ge=1, le=600)
    history_seconds: int = Field(default=120, ge=1, le=3600)
    horizon_seconds: int = Field(default=60, ge=1, le=1800)
    max_observation_age_seconds: int = Field(default=30, ge=0, le=600)
    route_tolerance_seconds: int = Field(default=10, ge=0, le=60)
    max_duration_seconds: int = Field(default=21600, ge=60, le=86400)
    max_rows_per_channel: int = Field(default=500000, ge=1, le=2000000)
    max_samples_per_match: int = Field(default=100000, ge=1, le=1000000)
    invalid_policy: Literal["quarantine", "reject"] = "quarantine"
    candidate_items: list[str] = Field(
        default_factory=lambda: ["power_treads", "desolator", "black_king_bar"],
        min_length=1, max_length=512,
    )

    @field_validator("candidate_items")
    @classmethod
    def item_names(cls, values):
        import re

        if {"other", "no_purchase"} & set(values) or len(set(values)) != len(values) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", value) for value in values
        ):
            raise ValueError("candidate_items must be unique canonical item keys")
        return values


class Coverage(StrictContract):
    """Explicit source assertion of continuous purchase event recording."""

    start_seconds: float = Field(ge=-3600)
    end_seconds: float = Field(ge=0)
    source: str = Field(min_length=1, max_length=500)
