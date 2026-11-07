"""Small, strict boundary for road-condition observations (not ground truth)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    timestamp_seconds: float = Field(ge=0, le=3600)
    observation: str = Field(min_length=1, max_length=500)


class VisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate: bool
    category: Literal["road_obstruction", "person_in_roadway", "none", "uncertain"]
    title: str = Field(min_length=1, max_length=160)
    observations: list[Observation] = Field(max_length=12)
    unknowns: list[str] = Field(max_length=12)

    @model_validator(mode="after")
    def coherent_candidate(self):
        if self.candidate and (self.category not in {"road_obstruction", "person_in_roadway"} or not self.observations):
            raise ValueError("A road candidate requires visible evidence.")
        if not self.candidate and self.category in {"road_obstruction", "person_in_roadway"}:
            raise ValueError("A road hazard category must be a candidate for human review.")
        if any(not item or len(item) > 500 for item in self.unknowns):
            raise ValueError("Unknowns must be short, non-empty statements.")
        return self


# Keep this schema simple for the provider's supported JSON-schema subset.
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate": {"type": "boolean"},
        "category": {"type": "string", "enum": ["road_obstruction", "person_in_roadway", "none", "uncertain"]},
        "title": {"type": "string"},
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "timestamp_seconds": {"type": "number"},
                    "observation": {"type": "string"},
                },
                "required": ["timestamp_seconds", "observation"],
            },
        },
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["candidate", "category", "title", "observations", "unknowns"],
}
