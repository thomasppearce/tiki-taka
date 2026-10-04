"""The proposal desk for one match: the deterministic producer, decisions, on-air, and the log.

Until the agents run on Foundry, a deterministic producer turns key moments (and high-speed
sprints) into proposals. It keeps the same contract and the same audit trail the agents will, so
it is also the fallback that keeps the queue alive if the agents are unavailable.

Each match gets a precomputed timeline of desk actions: agent handoffs (with the occasional
localizer failure and retry), then the proposal's creation. As the matchday clock advances the
desk replays whatever is due, in order. Approvals and rejections come from the producer in real
time; on matches without a producer, autopilot airs the most important proposals.
"""

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.generator.matchday import ScheduledMatch
from app.live.copy import Copy, CopyContext, moment_copy, sprint_copy
from app.models import AuditRecord, OverlayCommand, Proposal, ViewerProfile
from app.models.audit import ActorType, AuditAction
from app.models.desk import ApproveRequest, Desk, OnAir
from app.models.insight import KeyMoment
from app.models.overlays import OverlayPayload, OverlayTemplate
from app.models.proposals import AgentName, AudienceBody, LocalizedText

FEED_PROFILES: dict[str, ViewerProfile] = {
    "feed_analyst_en": ViewerProfile(
        profile_id="feed_analyst_en", audience="analyst", language="en"
    ),
    "feed_casual_es": ViewerProfile(profile_id="feed_casual_es", audience="casual", language="es"),
}

# When each agent finishes, in ms after the moment is knowable.
STAGES: tuple[tuple[AgentName, int], ...] = (
    ("interpreter", 1_000),
    ("explainer", 3_000),
    ("producer", 3_800),
    ("localizer", 5_300),
)
RETRY_MS = 1_800  # a failed localizer run costs this much extra
MIN_IMPORTANCE = 0.6
MAX_PENDING = 5
ON_AIR_MS = 7_000
AUTOPILOT_IMPORTANCE = 0.85
SPRINT_TAG_KMH = 32.0
SPRINT_IMPORTANCE = 0.65
SPRINT_TAG_GAP_MS = 20 * 60_000  # one speed tag per player per 20 minutes
REPEAT_GAP_MS = 5 * 60_000  # the same label is not proposed twice within 5 minutes
SHIFT_CONFIRM_MS = 3 * 60_000  # a momentum shift is only known once the swing has held
WARM_START_MS = 90_000  # on startup, replay only the last 90 s so the log looks lived-in
DEFAULT_TTL_MS = 45_000
TTL_MS = {"player_tag": 25_000}
MAX_AUDIT = 60
YOU = "producer (you)"

Decision = Literal["approved", "rejected", "expired"]


@dataclass(frozen=True)
class _Candidate:
    index: int
    moment_id: str
    label: str
    importance: float
    known_ms: int  # when the moment became knowable to the agents
    copy: Copy
    localizer_fails: bool

    @property
    def ready_ms(self) -> int:
        return self.known_ms + STAGES[-1][1] + (RETRY_MS if self.localizer_fails else 0)

    @property
    def proposal_id(self) -> str:
        return f"prop_{self.index:04d}"


@dataclass(frozen=True)
class _Action:
    at_ms: int
    kind: Literal["handoff", "failure", "retry", "create"]
    candidate: _Candidate
    agent: AgentName = "producer"


@dataclass(frozen=True)
class _Aired:
    proposal: Proposal
    template: OverlayTemplate
    start_clock_ms: int
    approved_by: str
    approved_at: datetime


@dataclass
class _State:
    started: bool = False
    cursor: int = 0
    clock_ms: int = 0
    version: int = 0
    pending: list[Proposal] = field(default_factory=list)
    on_air: OnAir | None = None
    audit: list[AuditRecord] = field(default_factory=list)
    aired: list[_Aired] = field(default_factory=list)
    counts: dict[Decision, int] = field(
        default_factory=lambda: {"approved": 0, "rejected": 0, "expired": 0}
    )


class ProposalDesk:
    def __init__(
        self,
        match: ScheduledMatch,
        moments: list[KeyMoment],
        ctx: CopyContext,
        autopilot: bool,
    ) -> None:
        self.match = match
        self.autopilot = autopilot
        self._lock = threading.Lock()
        self.candidates = self._candidates(moments, ctx)
        self.actions = sorted(
            (a for c in self.candidates for a in _actions(c)), key=lambda a: a.at_ms
        )
        self.state = _State()

    def _candidates(self, moments: list[KeyMoment], ctx: CopyContext) -> list[_Candidate]:
        raw: list[tuple[int, str, str, float, Copy]] = []
        for m in moments:
            if m.importance < MIN_IMPORTANCE:
                continue
            copy = moment_copy(m, ctx)
            if copy is None:
                continue
            known = max(
                m.match_clock_ms + (SHIFT_CONFIRM_MS if m.kind == "momentum_shift" else 0),
                *(ctx.events[e].match_clock_ms for e in m.evidence_event_ids),
            )
            raw.append((known, m.moment_id, m.label, m.importance, copy))
        fastest = 0.0
        last_tag: dict[str | None, int] = {}
        for e in self.match.result.events:
            speed = e.attributes.top_speed_kmh or 0.0
            if e.type != "sprint" or speed < SPRINT_TAG_KMH:
                continue
            record = speed > fastest
            fastest = max(fastest, speed)
            recent = e.match_clock_ms - last_tag.get(e.player_id, -SPRINT_TAG_GAP_MS)
            if not record and recent < SPRINT_TAG_GAP_MS:
                continue
            last_tag[e.player_id] = e.match_clock_ms
            copy = sprint_copy(e, record, ctx)
            label = f"{ctx.surname(e.player_id)} hits {speed:.1f} km/h"
            raw.append((e.match_clock_ms, f"km_{e.event_id[4:]}", label, SPRINT_IMPORTANCE, copy))
        raw.sort(key=lambda r: r[0])
        last_seen: dict[str, int] = {}
        kept: list[tuple[int, str, str, float, Copy]] = []
        for r in raw:
            if r[0] - last_seen.get(r[2], -REPEAT_GAP_MS) >= REPEAT_GAP_MS:
                kept.append(r)
            last_seen[r[2]] = r[0]
        return [
            _Candidate(i + 1, moment_id, label, importance, known, copy, i % 5 == 3)
            for i, (known, moment_id, label, importance, copy) in enumerate(kept)
        ]

    # --- Clock ---------------------------------------------------------------------------------

    def reset(self) -> None:
        """Forget every decision; the next sync replays from its clock (minus the warm start)."""
        with self._lock:
            self.state = _State()

    def sync(self, clock_ms: int) -> None:
        """Replay everything due by `clock_ms` in order: handoffs, new proposals, expiries."""
        with self._lock:
            s = self.state
            if clock_ms < s.clock_ms:
                self.state = s = _State()  # the matchday loop kicked off again
            if not s.started:
                s.started = True
                s.clock_ms = max(0, clock_ms - WARM_START_MS)
                while s.cursor < len(self.actions) and self.actions[s.cursor].at_ms < s.clock_ms:
                    s.cursor += 1
            while s.cursor < len(self.actions) and self.actions[s.cursor].at_ms <= clock_ms:
                action = self.actions[s.cursor]
                self._advance(action.at_ms)
                self._apply(action)
                s.cursor += 1
            self._advance(clock_ms)

    def _advance(self, clock_ms: int) -> None:
        s = self.state
        s.clock_ms = max(s.clock_ms, clock_ms)
        for p in [p for p in s.pending if p.expires_at_clock_ms <= s.clock_ms]:
            self._decide(p, "expired", "producer", "agent")
        if s.on_air and s.clock_ms >= s.on_air.start_clock_ms + s.on_air.duration_ms:
            s.on_air = None
            s.version += 1

    def _apply(self, action: _Action) -> None:
        c = action.candidate
        if action.kind == "create":
            self._create(c)
            return
        if action.kind == "failure":
            detail = "Spanish variant failed schema validation; retrying (attempt 2 of 3)"
            self._log("agent_failure", "localizer", "agent", None, detail)
            return
        if action.kind == "retry":
            self._log("retry", "localizer", "agent", None, "Retry succeeded: 4 variants written")
            return
        cited = sum(len(claim.evidence_event_ids) for claim in c.copy.claims)
        detail = {
            "interpreter": f"Detected: {c.label}",
            "explainer": f"Grounded {len(c.copy.claims)} claim(s) in {cited} cited event(s)",
            "producer": f"Ranked at priority {c.importance:.2f}",
            "localizer": "Wrote 4 variants: analyst and casual, EN and ES",
        }.get(action.agent, "")
        self._log("handoff", action.agent, "agent", None, detail)

    def _create(self, c: _Candidate) -> None:
        s = self.state
        if len(s.pending) >= MAX_PENDING:
            weakest = min(s.pending, key=lambda p: p.priority)
            if weakest.priority >= c.importance:
                self._log("handoff", "producer", "agent", None, f"Held back, queue full: {c.label}")
                return
            self._decide(weakest, "expired", "producer", "agent")
        trace = hashlib.sha256(f"{self.match.match_id}/{c.index}".encode()).hexdigest()[:16]
        proposal = Proposal(
            proposal_id=c.proposal_id,
            moment_id=c.moment_id,
            type=c.copy.type,
            priority=round(c.importance, 2),
            confidence=0.9,
            expires_at_clock_ms=c.ready_ms + TTL_MS.get(c.copy.type, DEFAULT_TTL_MS),
            headline=c.copy.headline,
            body=c.copy.body,
            claims=c.copy.claims,
            status="pending",
            produced_by=["interpreter", "explainer", "producer", "localizer"],
            trace_id=trace,
            player_id=c.copy.player_id,
        )
        s.pending.append(proposal)
        s.pending.sort(key=lambda p: -p.priority)
        self._log("created", "producer", "agent", proposal.proposal_id, c.label)
        if self.autopilot and c.importance >= AUTOPILOT_IMPORTANCE:
            self._air(proposal, "autopilot", "system")

    # --- Decisions -----------------------------------------------------------------------------

    def approve(self, proposal_id: str, request: ApproveRequest, clock_ms: int) -> OnAir:
        """Put a pending proposal on air, optionally with edited copy for one feed profile.

        Raises KeyError if the proposal is not pending (decided, expired, or unknown)."""
        self.sync(clock_ms)
        with self._lock:
            proposal = self._pending(proposal_id)
            if request.headline or request.body:
                profile = FEED_PROFILES.get(request.profile_id, FEED_PROFILES["feed_analyst_en"])
                proposal = proposal.model_copy(
                    update={
                        "status": "edited",
                        "headline": _edit(proposal.headline, profile, request.headline),
                        "body": _edit(proposal.body, profile, request.body),
                    }
                )
                language = profile.language.upper()
                detail = f"Edited the {profile.audience} {language} copy before airing"
                self._log("edited", YOU, "human", proposal_id, detail)
            return self._air(proposal, YOU, "human")

    def reject(self, proposal_id: str, clock_ms: int) -> None:
        """Raises KeyError if the proposal is not pending."""
        self.sync(clock_ms)
        with self._lock:
            self._decide(self._pending(proposal_id), "rejected", YOU, "human")

    def _air(self, proposal: Proposal, by: str, actor_type: ActorType) -> OnAir:
        s = self.state
        template: OverlayTemplate = (
            "player_tag" if proposal.type == "player_tag" and proposal.player_id else "lower_third"
        )
        if proposal.status != "edited":
            proposal = proposal.model_copy(update={"status": "approved"})
        s.on_air = OnAir(
            proposal=proposal,
            template=template,
            start_clock_ms=s.clock_ms,
            duration_ms=ON_AIR_MS,
            approved_by=by,
        )
        s.aired.append(_Aired(proposal, template, s.clock_ms, by, datetime.now(UTC)))
        self._decide(proposal, "approved", by, actor_type)
        return s.on_air

    def _decide(
        self, proposal: Proposal, decision: Decision, actor: str, actor_type: ActorType
    ) -> None:
        s = self.state
        s.pending = [p for p in s.pending if p.proposal_id != proposal.proposal_id]
        s.counts[decision] += 1
        self._log(decision, actor, actor_type, proposal.proposal_id, proposal.headline.analyst.en)

    def _pending(self, proposal_id: str) -> Proposal:
        for p in self.state.pending:
            if p.proposal_id == proposal_id:
                return p
        raise KeyError(proposal_id)

    def _log(
        self,
        action: AuditAction,
        actor: str,
        actor_type: ActorType,
        proposal_id: str | None,
        detail: str,
    ) -> None:
        s = self.state
        s.version += 1
        s.audit.insert(
            0,
            AuditRecord(
                audit_id=f"aud_{s.version:05d}",
                timestamp=datetime.now(UTC),
                match_clock_ms=s.clock_ms,
                action=action,
                actor_type=actor_type,
                actor=actor,
                proposal_id=proposal_id,
                detail=detail,
            ),
        )
        del s.audit[MAX_AUDIT:]

    # --- Views ---------------------------------------------------------------------------------

    def snapshot(self, clock_ms: int) -> Desk:
        self.sync(clock_ms)
        with self._lock:
            s = self.state
            return Desk(
                match_id=self.match.match_id,
                version=s.version,
                clock_ms=s.clock_ms,
                proposals=list(s.pending),
                on_air=s.on_air,
                audit=list(s.audit),
                aired=s.counts["approved"],
                rejected=s.counts["rejected"],
                expired=s.counts["expired"],
            )

    def overlays(self, profile_id: str, clock_ms: int) -> list[OverlayCommand]:
        """Every graphic aired so far, as timed overlay commands rendered for one feed profile.

        Raises KeyError for an unknown profile."""
        profile = FEED_PROFILES[profile_id]
        self.sync(clock_ms)
        with self._lock:
            return [
                OverlayCommand(
                    overlay_id=f"ovl_{a.proposal.proposal_id[5:]}_{profile_id.removeprefix('feed_')}",
                    proposal_id=a.proposal.proposal_id,
                    profile_id=profile_id,
                    template=a.template,
                    start_clock_ms=a.start_clock_ms,
                    duration_ms=ON_AIR_MS,
                    audience=profile.audience,
                    language=profile.language,
                    payload=OverlayPayload(
                        headline=_localized(a.proposal.headline, profile),
                        body=_localized(a.proposal.body, profile),
                        player_id=a.proposal.player_id,
                    ),
                    approved_by=a.approved_by,
                    approved_at=a.approved_at,
                )
                for a in self.state.aired
            ]


def _actions(c: _Candidate) -> list[_Action]:
    actions = [
        _Action(c.known_ms + offset, "handoff", c, agent)
        for agent, offset in STAGES
        if not (agent == "localizer" and c.localizer_fails)
    ]
    if c.localizer_fails:
        actions.append(_Action(c.known_ms + STAGES[-1][1], "failure", c, "localizer"))
        actions.append(_Action(c.ready_ms, "retry", c, "localizer"))
    actions.append(_Action(c.ready_ms, "create", c))
    return actions


def _localized(copy: AudienceBody, profile: ViewerProfile) -> str:
    text: LocalizedText = getattr(copy, profile.audience)
    return getattr(text, profile.language) or text.en


def _edit(copy: AudienceBody, profile: ViewerProfile, text: str | None) -> AudienceBody:
    if not text:
        return copy
    current: LocalizedText = getattr(copy, profile.audience)
    return copy.model_copy(
        update={profile.audience: current.model_copy(update={profile.language: text})}
    )
