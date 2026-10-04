"""The proposal desk: the deterministic producer, the human decisions, and the overlay feed."""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.live.desk import (
    AUTOPILOT_IMPORTANCE,
    DEFAULT_TTL_MS,
    MAX_PENDING,
    ProposalDesk,
    _Candidate,
)
from app.live.service import MatchdayService
from app.models import Desk, OverlayCommand

FEATURED = "m_l1_1"
Pin = Callable[..., None]


@pytest.fixture
def desk(service: MatchdayService) -> Iterator[ProposalDesk]:
    """The featured match's desk, cleared before and after each test."""
    desk = service.desks[FEATURED]
    desk.reset()
    yield desk
    desk.reset()


def _first_goal(desk: ProposalDesk) -> _Candidate:
    return next(c for c in desk.candidates if c.label.startswith("Goal"))


def _pin_after_goal(desk: ProposalDesk, at_minute: Pin) -> str:
    goal = _first_goal(desk)
    at_minute((goal.ready_ms + 1_000) / 60_000)
    return goal.proposal_id


def test_proposals_only_cite_events_that_have_happened(service: MatchdayService) -> None:
    for desk in service.desks.values():
        clocks = {e.event_id: e.match_clock_ms for e in desk.match.result.events}
        for c in desk.candidates:
            for claim in c.copy.claims:
                assert all(clocks[e] <= c.known_ms for e in claim.evidence_event_ids)


def test_agents_hand_off_before_the_proposal_lands(
    client: TestClient, desk: ProposalDesk, at_minute: Pin
) -> None:
    proposal_id = _pin_after_goal(desk, at_minute)
    state = Desk.model_validate(client.get(f"/api/matches/{FEATURED}/desk").json())
    assert proposal_id in [p.proposal_id for p in state.proposals]
    handoffs = {r.actor for r in state.audit if r.action in ("handoff", "retry")}
    assert {"interpreter", "explainer", "producer", "localizer"} <= handoffs
    created = next(r for r in state.audit if r.action == "created")
    assert created.proposal_id == proposal_id and created.actor_type == "agent"
    assert state.on_air is None  # the featured match waits for its human producer


def test_approve_with_an_edit_airs_it_and_feeds_the_overlay_json(
    client: TestClient, desk: ProposalDesk, at_minute: Pin
) -> None:
    proposal_id = _pin_after_goal(desk, at_minute)
    before = Desk.model_validate(client.get(f"/api/matches/{FEATURED}/desk").json())
    original = next(p for p in before.proposals if p.proposal_id == proposal_id)
    url = f"/api/matches/{FEATURED}/proposals/{proposal_id}"
    edited = "Kallo breaks the deadlock"
    response = client.post(f"{url}/approve", json={"headline": edited})
    assert response.status_code == 200
    state = Desk.model_validate(response.json())
    assert state.on_air is not None
    assert state.on_air.proposal.proposal_id == proposal_id
    assert state.on_air.proposal.status == "edited"
    assert state.on_air.approved_by == "producer (you)"
    assert proposal_id not in [p.proposal_id for p in state.proposals]
    assert [r.action for r in state.audit[:2]] == ["approved", "edited"]
    assert state.aired == 1

    def overlay(profile_id: str) -> OverlayCommand:
        feed = client.get(f"/api/matches/{FEATURED}/overlays", params={"profile_id": profile_id})
        return next(
            o
            for o in map(OverlayCommand.model_validate, feed.json())
            if o.proposal_id == proposal_id
        )

    # The edit was made on the analyst English feed; the casual Spanish feed keeps its own copy.
    assert overlay("feed_analyst_en").payload.headline == edited
    spanish = overlay("feed_casual_es")
    assert spanish.language == "es" and spanish.payload.headline == original.headline.casual.es
    assert client.post(f"{url}/approve", json={}).status_code == 409


def test_reject_logs_the_human_decision(
    client: TestClient, desk: ProposalDesk, at_minute: Pin
) -> None:
    proposal_id = _pin_after_goal(desk, at_minute)
    url = f"/api/matches/{FEATURED}/proposals/{proposal_id}"
    state = Desk.model_validate(client.post(f"{url}/reject").json())
    assert state.rejected == 1 and state.on_air is None
    assert (state.audit[0].action, state.audit[0].actor_type) == ("rejected", "human")
    assert client.post(f"{url}/approve", json={}).status_code == 409


def test_unanswered_proposals_expire(desk: ProposalDesk) -> None:
    goal = _first_goal(desk)
    desk.sync(goal.ready_ms + 1_000)
    assert goal.proposal_id in [p.proposal_id for p in desk.state.pending]
    desk.sync(goal.ready_ms + DEFAULT_TTL_MS + 1_000)
    assert goal.proposal_id not in [p.proposal_id for p in desk.state.pending]
    assert any(
        r.action == "expired" and r.proposal_id == goal.proposal_id for r in desk.state.audit
    )


def test_the_queue_is_throttled(service: MatchdayService) -> None:
    for desk in service.desks.values():
        desk.reset()
        for t in range(0, desk.match.result.full_time_ms, 2_000):
            desk.sync(t)
            assert len(desk.state.pending) <= MAX_PENDING
        desk.reset()


def test_other_matches_air_their_biggest_moments_on_autopilot(service: MatchdayService) -> None:
    aired = 0
    for match_id, desk in service.desks.items():
        desk.reset()
        desk.sync(0)
        desk.sync(desk.match.result.full_time_ms)
        if match_id == FEATURED:
            assert desk.state.aired == []  # nothing airs without the producer
        for a in desk.state.aired:
            assert a.approved_by == "autopilot" and a.proposal.priority >= AUTOPILOT_IMPORTANCE
        aired += len(desk.state.aired)
        desk.reset()
    assert aired > 0


def test_the_desk_starts_over_when_the_matchday_loops(desk: ProposalDesk) -> None:
    desk.sync(0)
    desk.sync(30 * 60_000)
    assert desk.state.version > 0
    desk.sync(60_000)
    assert desk.state.clock_ms == 60_000
    assert all((r.match_clock_ms or 0) <= 60_000 for r in desk.state.audit)


def test_unknown_proposal_and_feed_profile(client: TestClient, desk: ProposalDesk) -> None:
    url = f"/api/matches/{FEATURED}"
    assert client.post(f"{url}/proposals/prop_9999/reject").status_code == 409
    assert client.get(f"{url}/overlays", params={"profile_id": "feed_nope"}).status_code == 404
    assert client.get("/api/matches/m_nope/desk").status_code == 404
