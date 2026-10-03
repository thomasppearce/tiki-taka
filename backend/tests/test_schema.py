"""The exported JSON Schema is what the TypeScript types are generated from."""

from app.models import CONTRACTS
from app.models.schema import build_schema


def test_schema_defines_every_contract() -> None:
    definitions = build_schema()["$defs"]
    assert {model.__name__ for model in CONTRACTS} <= definitions.keys()


def test_defaulted_fields_are_required_on_the_wire() -> None:
    proposal = build_schema()["$defs"]["Proposal"]
    assert "status" in proposal["required"]


def test_unknown_fields_are_disallowed_in_the_schema() -> None:
    event = build_schema()["$defs"]["MatchEvent"]
    assert event["additionalProperties"] is False


def test_field_titles_are_omitted() -> None:
    event = build_schema()["$defs"]["MatchEvent"]
    assert "title" not in event["properties"]["event_id"]
