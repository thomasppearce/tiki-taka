"""The eval's own arithmetic (app/evals/graphics.py), without calling Foundry."""

from app.evals.graphics import Answer, briefs, render
from app.evals.solo import SoloGraphic
from app.live.service import MatchdayService


def test_every_featured_moment_becomes_a_brief_with_its_evidence(
    service: MatchdayService,
) -> None:
    moments = briefs(service)
    featured = next(m for m in service.matches if m.featured)
    assert len(moments) == len(service.desks[featured.match_id].candidates)
    for candidate, brief in moments:
        assert set(candidate.evidence_ids) <= set(brief.citable)
        assert brief.text()


def test_the_single_agent_answers_every_specialist_s_fields_in_order() -> None:
    fields = list(SoloGraphic.model_fields)
    assert fields[:4] == ["worth_airing", "angle", "type", "focus_player_id"]
    assert fields.index("claims") < fields.index("priority") < fields.index("casual_body_es")


def _answer(system: str, **kw: object) -> Answer:
    return Answer(system=system, moment_id="km_1", minute=9, kind="goal", label="Goal", **kw)  # type: ignore[arg-type]


def test_the_summary_counts_what_airs_and_what_was_wrong_with_it() -> None:
    team = [
        _answer("team", airs=True, first_draft_ok=False, scores={"groundedness": 5.0}),
        _answer("team", problems=["cites evt_9, which is not in the brief."]),
    ]
    solo = [
        _answer("solo", airs=True, problems=["says 45, which isn't in the brief."]),
        _answer("solo", airs=True, scores={"groundedness": 2.0}),
    ]
    meta = {"generated_at": "2026-10-13T00:00:00", "matchday": "x", "writer_model": "w"}
    page = render({**meta, "judge_model": "j"}, team, solo)
    assert "| Graphics put on air | 1 | 2 |" in page
    assert "| On air with something the brief doesn't support | 0 | 1 |" in page
    assert "| Held back by the checker (the scripted copy airs instead) | 1 | no checker |" in page
    assert "| First draft passed the checker | 0/1 (0%) | no checker |" in page
