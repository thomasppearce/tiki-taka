"""Contract tests: the rules the data contracts enforce at the API boundary."""

import pytest
from pydantic import ValidationError

from app.models import MatchEvent, Proposal, ViewerProfile

PASS_EVENT = {
    "event_id": "evt_000412",
    "match_id": "m_001",
    "minute": 71,
    "second": 14,
    "match_clock_ms": 4274000,
    "type": "pass",
    "team_id": "t_home",
    "player_id": "p_home_08",
    "target_player_id": "p_home_10",
    "location": {"x": 62.4, "y": 31.0},
    "end_location": {"x": 78.9, "y": 40.2},
    "outcome": "success",
    "attributes": {"pass_distance_m": 18.4, "pass_difficulty": 0.62, "pressure_level": 0.7},
}

PROPOSAL = {
    "proposal_id": "prop_0141",
    "moment_id": "mom_0087",
    "type": "stat_graphic",
    "priority": 0.82,
    "confidence": 0.9,
    "expires_at_clock_ms": 4334000,
    "headline": {"analyst": {"en": "Home side pinning them in"}, "casual": {"en": "All one-way"}},
    "body": {"analyst": {"en": "Field tilt 71%."}, "casual": {"en": "All one-way traffic."}},
    "claims": [{"text": "Field tilt rose to 71%", "evidence_event_ids": ["evt_000412"]}],
}


def test_brief_example_event_round_trips() -> None:
    event = MatchEvent.model_validate(PASS_EVENT)
    assert MatchEvent.model_validate_json(event.model_dump_json()) == event


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        MatchEvent.model_validate({**PASS_EVENT, "speed": 30})


def test_pitch_coordinates_are_bounded() -> None:
    with pytest.raises(ValidationError):
        MatchEvent.model_validate({**PASS_EVENT, "location": {"x": 101, "y": 50}})


@pytest.mark.parametrize(
    ("event_type", "attributes", "missing"),
    [
        ("pass", {"pass_distance_m": 12.0}, "pass_difficulty"),
        ("shot", {}, "ball_speed_kmh"),
        ("sprint", {"top_speed_kmh": 33.1}, "sprint_distance_m"),
    ],
)
def test_events_carry_the_attributes_their_type_needs(
    event_type: str, attributes: dict[str, float], missing: str
) -> None:
    with pytest.raises(ValidationError, match=missing):
        MatchEvent.model_validate({**PASS_EVENT, "type": event_type, "attributes": attributes})


def test_unit_interval_attributes_are_bounded() -> None:
    attributes = {**PASS_EVENT["attributes"], "pressure_level": 1.2}
    with pytest.raises(ValidationError):
        MatchEvent.model_validate({**PASS_EVENT, "attributes": attributes})


def test_proposal_defaults_to_pending() -> None:
    assert Proposal.model_validate(PROPOSAL).status == "pending"


def test_proposal_headline_is_localized_per_audience() -> None:
    with pytest.raises(ValidationError):
        Proposal.model_validate({**PROPOSAL, "headline": "Home side pinning them in"})


def test_proposal_without_claims_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Proposal.model_validate({**PROPOSAL, "claims": []})


def test_claim_without_evidence_is_rejected() -> None:
    claims = [{"text": "Field tilt rose to 71%", "evidence_event_ids": []}]
    with pytest.raises(ValidationError):
        Proposal.model_validate({**PROPOSAL, "claims": claims})


def test_viewer_profile_rejects_unknown_spotlight_metric() -> None:
    with pytest.raises(ValidationError):
        ViewerProfile(profile_id="feed_1", audience="casual", spotlight_metric="vibes")
