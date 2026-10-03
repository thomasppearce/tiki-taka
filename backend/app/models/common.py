"""Shared building blocks for the data contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
"""A value in [0, 1]: probabilities, ratings, and normalized levels."""

Audience = Literal["analyst", "casual"]

Language = Literal["en", "es"]
"""Supported output languages. Keep in sync with the fields on `LocalizedText`."""


class Contract(BaseModel):
    """Base for every model that crosses the API boundary.

    - `extra="forbid"`: unknown fields are rejected, so producers and consumers can't drift apart
      silently.
    - Defaulted fields are marked required in the serialization schema: the backend always sends
      every field, so the generated TypeScript types don't mark them optional.
    """

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class PitchPoint(Contract):
    """Normalized pitch coordinates (0-100 on both axes). x runs in the home attacking direction."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
