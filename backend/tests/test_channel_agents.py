"""The channel's agents: the Director agent deciding cuts, Watchers telling stories, the checker
holding both to their briefs. A fake stands in for Foundry: it records what the channel asks, and
the test answers as the agents would."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from app.agents.channel_brief import MatchBrief, match_brief
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
    key, brief = next((k, b) for m, k, b in agents.stories if m == on_air)
    update = StoryUpdate(story="A tense start.", claims=claim_from(brief))
    sent_back = ["The story doesn't give the score as it is now: 0-0."]
    director.story_ready(on_air, key, update, 1.5, 900, cached=False, sent_back=sent_back)
    package = director.state.on_air.package
    assert package.story == "A tense start." and package.written_by[0] == "watcher"
    watcher, checker = director.log[:2]  # newest first: the checker sent it back, then it passed
    assert watcher.agent == "watcher" and checker.agent == "checker"
    assert checker.detail == f"Sent the Watcher's story back: {sent_back[0]}"


def test_a_goal_asks_its_watcher_for_a_new_story(service: MatchdayService) -> None:
    director, agents = director_with_agents(service)
    goal = next(e for e in service.by_id["m_l1_2"].result.events if e.type == "goal")  # Halvern
    start = goal.match_clock_ms // 60_000 * 60_000 - 60_000
    director.sync(start)
    agents.stories.clear()
    for t in range(start, start + 3 * 60_000, 1_000):
        director.sync(t)
    assert any(m == "m_l1_2" and goal.event_id in key for m, key, _ in agents.stories)


def test_the_checker_holds_stories_and_decisions_to_their_briefs(
    service: MatchdayService,
) -> None:
    director, agents = director_with_agents(service)
    director.sync(82 * 60_000)  # Halvern have scored (80')
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


def test_the_checker_knows_how_the_lead_changed_hands(service: MatchdayService) -> None:
    from app.agents.channel_brief import match_brief

    decider = match_brief(service, "m_l1_1", 97 * 60_000, None)
    assert "Westmere Athletic lead for the first time" in decider.goals[-1]
    slip = CutDecision(
        match_id="m_l1_1",
        why="Desai puts Westmere Athletic ahead again at the death.",
        at_stake=None,
        claims=[],
    )
    assert "back in front" in check_decision(slip, [decider])[0]
    swings = match_brief(service, "m_l1_9", 66 * 60_000, None)  # 0-1, 1-1, then 1-2 at 65'
    back = StoryUpdate(story="Redstack Rovers are back in front, 2-1.", claims=[])
    assert check_story(back, swings) == []
    one_way = match_brief(service, "m_l1_8", 70 * 60_000, None)  # Mistral Bay were never caught
    level = StoryUpdate(story="Mistral Bay lead 1-0 after an early equaliser.", claims=[])
    assert any("equaliser" in p for p in check_story(level, one_way))


def test_a_late_winners_brief_has_the_table_after_it(service: MatchdayService) -> None:
    """Desai's winner comes in the last second before full time: the brief that tells it must
    already have Westmere out of the drop, and nothing left at stake in a finished match."""
    m = service.by_id["m_l1_1"]
    winner = [e for e in m.result.events if e.type == "goal"][-1]
    t = (winner.match_clock_ms // 1000 + 1) * 1000  # the channel's tick after the goal
    brief = match_brief(service, "m_l1_1", t, None)
    assert "Westmere Athletic 17th" in brief.standing
    assert not brief.stakes


def test_a_cut_with_nothing_at_stake_must_not_talk_about_the_table(
    service: MatchdayService,
) -> None:
    quiet = next(
        b
        for b in (match_brief(service, m.match_id, 69 * 60_000, None) for m in service.matches)
        if not b.stakes and not b.moves
    )
    made_up = CutDecision(
        match_id=quiet.match_id,
        why="A goal here could swing the title picture.",
        at_stake=None,
        claims=[],
    )
    assert any("Nothing in the table is at stake" in p for p in check_decision(made_up, [quiet]))
    on_the_pitch = made_up.model_copy(update={"why": "They are pushing hard for a winner."})
    assert not any("Nothing in the table" in p for p in check_decision(on_the_pitch, [quiet]))


def test_a_story_asked_before_the_clock_jumped_is_dropped(service: MatchdayService) -> None:
    """The producer skips ahead while Watchers are still writing: their answers describe a
    moment that is gone, so they never reach the screen."""
    director, agents = director_with_agents(service)
    director.sync(60 * 60_000)
    on_air = director.state.on_air.match_id if director.state else ""
    key, brief = next((k, b) for m, k, b in agents.stories if m == on_air)
    director.reset()
    director.sync(70 * 60_000)
    stale = StoryUpdate(story="Still 0-0 at 61'.", claims=claim_from(brief))
    director.story_ready(on_air, key, stale, 1.5, 900, cached=True)
    assert director.state and director.state.on_air.package.story != "Still 0-0 at 61'."
    assert all(
        entry.detail != "Still 0-0 at 61'. (1.5 s, 900 tokens, cached)" for entry in director.log
    )


def test_a_rivalry_must_come_from_the_brief(service: MatchdayService) -> None:
    """Mistral Bay v Lanterne Port FC is the Coast derby (its brief says so); Northgate v
    Westmere is no derby, so calling it one is made up."""
    northgate = match_brief(service, "m_l1_1", 30 * 60_000, None)
    home, away = northgate.scores[-1]
    story = StoryUpdate(story=f"{home}-{away} in a tense derby.", claims=[])
    assert any('"derby"' in p for p in check_story(story, northgate))
    coast = match_brief(service, "m_l1_8", 30 * 60_000, None)
    home, away = coast.scores[-1]
    story = StoryUpdate(story=f"{home}-{away} in the Coast derby.", claims=[])
    assert not any("derby" in p for p in check_story(story, coast))
