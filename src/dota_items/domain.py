"""Validated boundaries with explicit time semantics and provenance."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemEvent(DomainModel):
    item_key: str = Field(min_length=1)
    time_seconds: float
    event_kind: Literal["purchase_record"] = "purchase_record"
    source_event_ref: str

    @field_validator("time_seconds")
    @classmethod
    def finite_time(cls, value: float) -> float:
        import math

        if not math.isfinite(value):
            raise ValueError("time_seconds must be finite")
        return value


class PlayerTimeline(DomainModel):
    schema_version: Literal["0.1"] = "0.1"
    match_id: int = Field(gt=0)
    player_slot: int = Field(ge=0, le=255)
    hero_id: int = Field(gt=0)
    patch_id: int | None = None
    game_mode: int | None = None
    duration_seconds: int = Field(ge=0)
    purchase_log_status: Literal["present", "missing", "invalid"]
    events: list[ItemEvent] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    source_fingerprint: str
    source: str


class FirstRecord(DomainModel):
    item_key: str
    time_seconds: float
    source_event_ref: str


class AnalysisResult(DomainModel):
    schema_version: Literal["0.1"] = "0.1"
    timeline: PlayerTimeline
    first_records: list[FirstRecord]
    candidate_items: list[str]
    limitations: list[str]
