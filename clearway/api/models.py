"""Validated request and analysis boundaries for the local demonstration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SourceId = Literal["road-obstruction", "street-traffic", "traffic-jam", "person-roadway"]
AnalysisMode = Literal["fixture", "cached", "fresh"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ReplayRequest(StrictModel):
    source_id: SourceId
    analysis_mode: AnalysisMode = "fixture"


class LabelRequest(StrictModel):
    source_id: SourceId
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    label: Literal["road_obstruction", "person_in_roadway", "normal", "queue", "uncertain"]
    reviewer: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_interval(self):
        if self.start_seconds >= self.end_seconds:
            raise ValueError("The end must be after the start.")
        if not self.reviewer.strip():
            raise ValueError("A human reviewer name is required.")
        self.reviewer = self.reviewer.strip()
        return self


class Observation(StrictModel):
    timestamp_seconds: float = Field(ge=0)
    observation: str = Field(min_length=1, max_length=2000)


class AnalysisResult(BaseModel):
    """A malformed adapter response cannot write partial incident state."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    mode: Literal["fixture", "cached", "fresh", "unavailable"]
    status: Literal["complete", "unavailable"]
    message: str = Field(max_length=2000)
    observations: list[Observation] = Field(default_factory=list, max_length=100)
    candidate: bool = False
    title: str = Field(default="", max_length=300)
    category: str = Field(default="", max_length=100)
    unknowns: list[str] = Field(default_factory=list, max_length=100)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def coherent_result(self):
        if self.status == "unavailable" and self.candidate:
            raise ValueError("Unavailable analysis cannot create a candidate.")
        if self.candidate and (not self.title or not self.category or not self.observations):
            raise ValueError("Candidates need a title, category, and evidence.")
        if self.mode == "fixture" and self.provenance.get("fixture") is not True:
            raise ValueError("Fixture results require explicit fixture provenance.")
        if self.mode in ("cached", "fresh") and self.provenance.get("fixture") is not False:
            raise ValueError("Model outputs must carry genuine inference provenance.")
        return self
