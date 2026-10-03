"""Export the data contracts as one JSON Schema document.

Usage: `python -m app.models.schema <output-path>` (run by `make types`).

The schema feeds json-schema-to-typescript to generate the frontend types, and is committed under
docs/schema/ so any overlay consumer can validate against it.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic.json_schema import GenerateJsonSchema, models_json_schema

from app.models import CONTRACTS


class _NoFieldTitles(GenerateJsonSchema):
    """Field titles make json-schema-to-typescript emit alias noise like `type X = number`."""

    def field_title_should_be_set(self, schema: Any) -> bool:
        return False


def build_schema() -> dict[str, Any]:
    """Serialization-mode schema: describes what the backend sends over the wire."""
    _, schema = models_json_schema(
        [(model, "serialization") for model in CONTRACTS],
        title="MatchDeskContracts",
        schema_generator=_NoFieldTitles,
    )
    return schema


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_schema(), indent=2) + "\n")
    print(f"Wrote {out}")
