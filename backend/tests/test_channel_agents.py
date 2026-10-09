"""The channel's agents: the Director agent deciding cuts, Watchers telling stories, the checker
holding both to their briefs. A fake stands in for Foundry: it records what the channel asks, and
the test answers as the agents would."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from app.agents.channel_brief import MatchBrief
from app.agents.channel_checker import check_decision, check_story
from app.agents.schemas import CutDecision, DraftClaim, StoryUpdate
from app.live.channel import CUT_COUNTDOWN_MS, LATE_DECISION_MS, ChannelDirector
from app.live.service import MatchdayService


class FakeAgents:
    def __init__(self) -> None:
        self.stories: list[tuple[str, str, MatchBrief]] = []
        self.decisions: list[tuple[str, str, Sequence[MatchBrief]]] = []

    def request_story(self, channel: Any, match_id: str, key: str, brief: MatchBrief) -> None:
        self.stories.append((match_id, key, brief))

    def request_decision(
        self, channel: Any, key: str, reason: str, on_air: str, briefs: Sequence[MatchBrief]
    ) -> None:
        self.decisions.append((key, reason, briefs))


def director_with_agents(service: MatchdayService) -> tuple[ChannelDirector, FakeAgents]:
    director = ChannelDirector(service)
    agents = FakeAgents()
    director.agents = agents
    return director, agents


def until_proposal(director: ChannelDirector, agents: FakeAgents, start: int) -> int:
    """Watch from `start` until the code proposes a pressure cut or check-in; return that time."""
    for t in range(start, start + 30 * 60_000, 1_000):
        director.sync(t)
        assert director.state
        p = director.state.pending
        if p and p.reason in ("pressure", "check_in") and agents.decisions:
            return t
    raise AssertionError("no proposal")


def claim_from(brief: MatchBrief) -> list[DraftClaim]:
    fact = brief.events[-1] if brief.events else None
    return [DraftClaim(text="It happened", evidence_event_ids=[fact.event_id])] if fact else []


def test_the_director_agent_can_choose_another_candidate(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    t = until_proposal(director, agents, 40 * 60_000)
    key, _, briefs = agents.decisions[-1]
    assert len(briefs) >= 2 and director.state and director.state.pending
    proposed, other = briefs[0], briefs[1]
    assert director.state.pending.match_id == proposed.match_id
    decision = CutDecision(
        match_id=other.match_id, why="A better story here.", at_stake=None, claims=claim_from(other)
    )
    director.decision_ready(key, decision, 2.1, 1500, cached=False)
    pending = director.state.pending
    assert pending and pending.match_id == other.match_id
    assert pending.package.why == "A better story here."
    assert "director" in pending.package.written_by
    assert director.log[0].agent == "director" and "over" in director.log[0].detail
    director.sync(t + CUT_COUNTDOWN_MS + 1_000)
    assert director.state.on_air.match_id == other.match_id
    assert director.state.on_air.decided_by == "director"


def test_a_late_decision_rewrites_the_cut_it_was_for(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    t = until_proposal(director, agents, 40 * 60_000)
    key, _, briefs = agents.decisions[-1]
    director.sync(t + CUT_COUNTDOWN_MS + 1_000)  # the countdown ran out: the code's pick aired
    assert director.state and director.state.on_air.decided_by == "code"
    words = CutDecision(
        match_id=briefs[0].match_id, why="Rewritten.", at_stake=None, claims=claim_from(briefs[0])
    )
    director.decision_ready(key, words, 6.0, 1500, cached=False)
    assert director.state.on_air.package.why == "Rewritten."
    assert director.state.on_air.decided_by == "code"  # the words are the agent's, not the cut


def test_a_decision_too_late_is_ignored(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    t = until_proposal(director, agents, 40 * 60_000)
    key, _, briefs = agents.decisions[-1]
    director.sync(t + CUT_COUNTDOWN_MS + LATE_DECISION_MS + 2_000)
    assert director.state
    before = director.state.on_air.package.why
    words = CutDecision(match_id=briefs[0].match_id, why="Too late.", at_stake=None, claims=[])
    director.decision_ready(key, words, 20.0, 1500, cached=False)
    assert director.state.on_air.package.why == before
    assert "too late" in director.log[0].detail


def test_watchers_tell_the_story_on_air(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    director.sync(20 * 60_000)
    assert director.state
    asked = {match_id for match_id, _, _ in agents.stories}
    assert len(asked) == len(service.matches)  # every Watcher, as the channel starts
    on_air = director.state.on_air.match_id
    brief = next(b for m, _, b in agents.stories if m == on_air)
    update = StoryUpdate(story="A tense start.", claims=claim_from(brief))
    sent_back = ["The story doesn't give the score as it is now: 0-0."]
    director.story_ready(on_air, "k", update, 1.5, 900, cached=False, sent_back=sent_back)
    package = director.state.on_air.package
    assert package.story == "A tense start." and package.written_by[0] == "watcher"
    watcher, checker = director.log[:2]  # newest first: the checker sent it back, then it passed
    assert watcher.agent == "watcher" and checker.agent == "checker"
    assert checker.detail == f"Sent the Watcher's story back: {sent_back[0]}"


def test_a_goal_asks_its_watcher_for_a_new_story(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    director.sync(77 * 60_000)
    agents.stories.clear()
    for t in range(77 * 60_000, 80 * 60_000, 1_000):  # Halvern score at 78'
        director.sync(t)
    goal = next(e for e in service.by_id["m_l1_2"].result.events if e.type == "goal")
    assert any(m == "m_l1_2" and goal.event_id in key for m, key, _ in agents.stories)


def test_the_checker_holds_stories_and_decisions_to_their_briefs(
    service: MatchdayService,
) -> None:
    director, agents = director_with_agents(service)
    director.sync(80 * 60_000)
    brief = next(b for m, _, b in agents.stories if m == "m_l1_2")
    assert brief.scores[-1] == (0, 1)
    good = StoryUpdate(story="Halvern Town lead 1-0.", claims=claim_from(brief))
    assert check_story(good, brief) == []
    stale = StoryUpdate(story="Still level at 0-0, with 2-2 a fair result.", claims=[])
    problems = " | ".join(check_story(stale, brief))
    assert "as it is now: 0-1" in problems and "says 2-2" in problems and "0-0" not in problems
    bad = StoryUpdate(
        story="Halvern Town lead 0-1 after 97 minutes.",
        claims=[DraftClaim(text="They scored", evidence_event_ids=["evt_999999"])],
    )
    problems = " | ".join(check_story(bad, brief))
    assert "says 97" in problems and "evt_999999" in problems
    table = StoryUpdate(
        story="Halvern Town lead 0-1, move top and out of the 2nd place, in the 2nd half.",
        claims=claim_from(brief),
    )
    problems = " | ".join(check_story(table, brief))
    assert '"move top"' in problems and '"2nd"' in problems and "half" not in problems
    told = replace(brief, story="Earlier.").text(watcher=True)  # no table, no last story
    assert "AS IT STANDS" not in told and "STORY SO FAR" not in told
    elsewhere = CutDecision(match_id="m_l1_9", why="Go.", at_stake=None, claims=[])
    assert "not a candidate" in check_decision(elsewhere, [brief])[0]


def test_a_goal_on_air_rewrites_the_package(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    winner = [e for e in service.by_id["m_l1_1"].result.events if e.type == "goal"][-1]
    start = winner.match_clock_ms // 1_000 * 1_000 - 30_000
    director.sync(start)
    director.pin(start, "m_l1_1")  # the title decider stays on air through its winner
    agents.decisions.clear()
    for t in range(start, start + 40_000, 1_000):
        director.sync(t)
    assert director.state and director.state.on_air.match_id == "m_l1_1"
    cut_id = director.state.on_air.cut_id
    package = director.state.on_air.package
    assert service.surname(winner.player_id) in package.why  # the code's words at once
    assert package.at_stake and package.at_stake.startswith("As it stands:")
    key, reason, briefs = agents.decisions[-1]
    assert reason == "goal" and [b.match_id for b in briefs] == ["m_l1_1"]
    words = CutDecision(
        match_id="m_l1_1", why="The winner.", at_stake=None, claims=claim_from(briefs[0])
    )
    director.decision_ready(key, words, 1.7, 1400, cached=False)
    assert director.state.on_air.package.why == "The winner."
    assert director.state.on_air.cut_id == cut_id  # same cut: no stinger, no second replay
    assert "for the goal" in director.log[0].detail
