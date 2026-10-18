"""The proposal desk for one match: the proposals, decisions, on-air, and the log.

Moments come from the aggregator (key plays) and the broadcast cues. On the featured match the
agent team on Microsoft Foundry writes each proposal (app/agents): the desk briefs the team when a
moment becomes knowable, logs each agent's step as it reports, and queues the graphic it returns.
If the team fails or doesn't answer in time, the desk uses its scripted copy and says so.

Every other match runs the scripted producer on a precomputed timeline (its handoffs simulate the
team's pacing), with autopilot airing the most important proposals. Approvals and rejections
come from the human producer in real time.
"""

import hashlib
import itertools
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, NamedTuple, Protocol

from app.generator.matchday import ScheduledMatch
from app.live.copy import Copy, CopyContext, moment_copy, sprint_copy
from app.live.cues import cues
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
MIN_IMPORTANCE = 0.5
MAX_PENDING = 5
ON_AIR_MS = 10_000  # a lower third stays up long enough to read twice, or to switch the feed
AUTOPILOT_IMPORTANCE = 0.85
# The featured match's graphics wait for the producer, while one is in the control room. With
# nobody there this long, the desk airs the agents' strongest ones itself, and logs it.
UNATTENDED_AFTER_S = 20.0
UNATTENDED_IMPORTANCE = 0.75
SPRINT_TAG_KMH = 32.0
SPRINT_IMPORTANCE = 0.65
SPRINT_TAG_GAP_MS = 20 * 60_000  # one speed tag per player per 20 minutes
REPEAT_GAP_MS = 5 * 60_000  # the same label is not proposed twice within 5 minutes
SHIFT_CONFIRM_MS = 3 * 60_000  # a momentum shift is only known once the swing has held
WARM_START_MS = 90_000  # on startup, replay only the last 90 s so the log looks lived-in
DEFAULT_TTL_MS = 60_000
TTL_MS = {"player_tag": 30_000}
DEFAULT_TEAM: list[AgentName] = ["interpreter", "explainer", "producer", "localizer"]
MAX_AUDIT = 60
YOU = "producer (you)"
AGENT_DEADLINE_MS = 60_000  # no answer from the team by then: the scripted copy goes out
SCRIPTED: list[AgentName] = ["orchestrator"]  # credited on scripted (fallback) proposals

Decision = Literal["approved", "rejected", "expired"]


@dataclass(frozen=True)
class AgentGraphic:
    """What the agent team hands back for one moment."""

    copy: Copy
    priority: float
    ttl_ms: int
    produced_by: list[AgentName]


class AgentBridge(Protocol):
    """Runs the agent team for a desk (app/agents/runner.py). Must not block."""

    def request(
        self, desk: "ProposalDesk", candidate: "_Candidate", generation: int, queue: str
    ) -> None: ...


class _Raw(NamedTuple):
    known: int
    moment_id: str
    label: str
    importance: float
    copy: Copy
    kind: str
    evidence: list[str]


@dataclass(frozen=True)
class _Candidate:
    index: int
    moment_id: str
    label: str
    importance: float
    known_ms: int  # when the moment became knowable to the agents
    copy: Copy  # the scripted copy: the fallback, and the whole proposal off the featured match
    localizer_fails: bool
    kind: str
    evidence_ids: list[str]

    @property
    def ready_ms(self) -> int:
        return self.known_ms + STAGES[-1][1] + (RETRY_MS if self.localizer_fails else 0)

    @property
    def proposal_id(self) -> str:
        return f"prop_{self.index:04d}"


@dataclass(frozen=True)
class _Action:
    at_ms: int
    kind: Literal["handoff", "failure", "retry", "create", "brief"]
    candidate: _Candidate
    agent: AgentName = "producer"


@dataclass(frozen=True)
class _Aired:
    proposal: Proposal
    template: OverlayTemplate
    start_clock_ms: int
    approved_by: str
    approved_at: datetime


_GENERATIONS = itertools.count(1)


@dataclass
class _State:
    generation: int = field(default_factory=lambda: next(_GENERATIONS))
    started: bool = False
    cursor: int = 0
    clock_ms: int = 0
    now_ms: int = 0  # the clock being synced to (replays catch up to it)
    version: int = 0
    pending: list[Proposal] = field(default_factory=list)
    on_air: OnAir | None = None
    audit: list[AuditRecord] = field(default_factory=list)
    aired: list[_Aired] = field(default_factory=list)
    counts: dict[Decision, int] = field(
        default_factory=lambda: {"approved": 0, "rejected": 0, "expired": 0}
    )
    awaiting: dict[int, tuple["_Candidate", int]] = field(default_factory=dict)  # index -> deadline
    types: dict[str, str] = field(default_factory=dict)  # proposal_id -> type, for the Producer


class ProposalDesk:
    def __init__(
        self,
        match: ScheduledMatch,
        moments: list[KeyMoment],
        ctx: CopyContext,
        autopilot: bool,
        agents: AgentBridge | None = None,
    ) -> None:
        self.match = match
        self.ctx = ctx
        self.autopilot = autopilot
        self.agents = agents
        self._attended_at = float("-inf")  # when a producer last had the control room open
        self._lock = threading.Lock()
        self.candidates = self._candidates(moments, ctx)
        timeline = _brief if agents else _actions
        self.actions = sorted(
            (a for c in self.candidates for a in timeline(c)), key=lambda a: a.at_ms
        )
        self.state = _State()

    def attend(self) -> None:
        """A producer has the control room open (its stream calls this as it plays)."""
        self._attended_at = time.monotonic()

    @property
    def unattended(self) -> bool:
        return time.monotonic() - self._attended_at > UNATTENDED_AFTER_S

    def _candidates(self, moments: list[KeyMoment], ctx: CopyContext) -> list[_Candidate]:
        raw: list[_Raw] = []
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
            raw.append(
                _Raw(known, m.moment_id, m.label, m.importance, copy, m.kind, m.evidence_event_ids)
            )
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
            key = f"km_{e.event_id[4:]}"
            raw.append(
                _Raw(e.match_clock_ms, key, label, SPRINT_IMPORTANCE, copy, "sprint", [e.event_id])
            )
        # Between the defining plays: offsides, bookings, changes, stat checks, territory, runners.
        result = self.match.result
        teams = (self.match.home.club_id, self.match.away.club_id)
        for cue in cues(result.events, ctx, teams, result.full_time_ms):
            evidence = list(dict.fromkeys(i for c in cue.copy.claims for i in c.evidence_event_ids))
            raw.append(
                _Raw(cue.at_ms, cue.key, cue.label, cue.importance, cue.copy, cue.kind, evidence)
            )
        raw.sort(key=lambda r: r.known)
        last_seen: dict[str, int] = {}
        kept: list[_Raw] = []
        for r in raw:
            if r.known - last_seen.get(r.label, -REPEAT_GAP_MS) >= REPEAT_GAP_MS:
                kept.append(r)
            last_seen[r.label] = r.known
        return [
            _Candidate(
                i + 1,
                r.moment_id,
                r.label,
                r.importance,
                r.known,
                r.copy,
                i % 5 == 3,
                r.kind,
                list(r.evidence),
            )
            for i, r in enumerate(kept)
        ]

    # --- Clock ---------------------------------------------------------------------------------

    def reset(self) -> None:
        """Forget every decision; the next sync replays from its clock (minus the warm start)."""
        with self._lock:
            # The version keeps counting, so a page holding the old desk takes the new one.
            self.state = _State(version=self.state.version + 1)

    def sync(self, clock_ms: int) -> None:
        """Replay everything due by `clock_ms` in order: handoffs, new proposals, expiries."""
        with self._lock:
            s = self.state
            if clock_ms < s.clock_ms:
                self.state = s = _State(version=s.version + 1)  # the matchday loop kicked off again
            s.now_ms = clock_ms
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
        for index, (c, deadline) in list(s.awaiting.items()):
            if s.clock_ms >= deadline:
                del s.awaiting[index]
                detail = f"No answer on {c.label} within {AGENT_DEADLINE_MS // 1000} s"
                self._log(
                    "agent_failure", "orchestrator", "agent", None, f"{detail}; scripted copy used"
                )
                self._create(c, c.copy, c.importance, _ttl(c.copy), SCRIPTED)
        for p in [p for p in s.pending if p.expires_at_clock_ms <= s.clock_ms]:
            self._decide(p, "expired", "producer", "agent")
        if s.on_air and s.clock_ms >= s.on_air.start_clock_ms + s.on_air.duration_ms:
            s.on_air = None
            s.version += 1
        if s.on_air is None:
            self._autopilot_next()

    def _autopilot_bar(self) -> float | None:
        """The priority autopilot airs at, or None while the producer decides."""
        if self.autopilot:
            return AUTOPILOT_IMPORTANCE
        return UNATTENDED_IMPORTANCE if self.unattended else None

    def _autopilot_next(self) -> None:
        """The screen is free: autopilot airs the strongest graphic still waiting, so one that
        landed while another was on air gets its turn."""
        bar = self._autopilot_bar()
        waiting = [p for p in self.state.pending if bar is not None and p.priority >= bar]
        if waiting:
            self._air(max(waiting, key=lambda p: p.priority), "autopilot", "system")

    def _apply(self, action: _Action) -> None:
        c = action.candidate
        if action.kind == "brief" and self.agents:
            s = self.state
            # The team gets its full time from when it is briefed, even if the desk is replaying
            # moments it missed (the warm start), so the deadline runs from "now", not the moment.
            s.awaiting[c.index] = (c, max(s.clock_ms, s.now_ms) + AGENT_DEADLINE_MS)
            self._log("handoff", "orchestrator", "agent", None, f"Briefed the team: {c.label}")
            self.agents.request(self, c, s.generation, self._queue_summary())
            return
        if action.kind == "create":
            self._create(c, c.copy, c.importance, _ttl(c.copy), DEFAULT_TEAM)
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
            "explainer": f"Grounded {_count(len(c.copy.claims), 'claim')} in "
            f"{_count(cited, 'cited event')}",
            "producer": f"Ranked at priority {c.importance:.2f}",
            "localizer": "Wrote 4 variants: analyst and casual, EN and ES",
        }.get(action.agent, "")
        self._log("handoff", action.agent, "agent", None, detail)

    def _create(
        self,
        c: _Candidate,
        copy: Copy,
        priority: float,
        ttl_ms: int,
        produced_by: list[AgentName],
    ) -> None:
        s = self.state
        if len(s.pending) >= MAX_PENDING:
            weakest = min(s.pending, key=lambda p: p.priority)
            if weakest.priority >= priority:
                self._log("handoff", "producer", "agent", None, f"Held back, queue full: {c.label}")
                return
            self._decide(weakest, "expired", "producer", "agent")
        trace = hashlib.sha256(f"{self.match.match_id}/{c.index}".encode()).hexdigest()[:16]
        proposal = Proposal(
            proposal_id=c.proposal_id,
            moment_id=c.moment_id,
            type=copy.type,
            priority=round(priority, 2),
            confidence=0.9,
            expires_at_clock_ms=s.clock_ms + ttl_ms,
            headline=copy.headline,
            body=copy.body,
            claims=copy.claims,
            status="pending",
            produced_by=produced_by,
            trace_id=trace,
            player_id=copy.player_id,
        )
        s.pending.append(proposal)
        s.pending.sort(key=lambda p: -p.priority)
        s.types[proposal.proposal_id] = copy.type
        self._log("created", "producer", "agent", proposal.proposal_id, c.label)
        # Autopilot never cuts a graphic short for one that matters no more (two often land at
        # once: the 60' stats and the hardest runner); the other waits its turn.
        on = s.on_air
        free = (
            on is None
            or s.clock_ms >= on.start_clock_ms + on.duration_ms
            or priority > on.proposal.priority
        )
        bar = self._autopilot_bar()
        if bar is not None and priority >= bar and free:
            self._air(proposal, "autopilot", "system")

    # --- The agent team's answers (from the runner, on the event loop) ------------------------

    def agent_step(self, index: int, generation: int, agent: str, action: str, detail: str) -> None:
        """Log one agent's step for a moment the desk is still waiting on."""
        with self._lock:
            s = self.state
            if s.generation == generation and index in s.awaiting:
                self._log(action, agent, "agent", None, detail)  # type: ignore[arg-type]

    def agent_result(
        self,
        index: int,
        generation: int,
        graphic: AgentGraphic | None,
        status: str,
        reason: str = "",
    ) -> None:
        """Queue the team's graphic, or fall back to the scripted copy and say why."""
        with self._lock:
            s = self.state
            if s.generation != generation or index not in s.awaiting:
                return  # the matchday looped, or the deadline already passed
            c, _ = s.awaiting.pop(index)
            if graphic:
                self._create(c, graphic.copy, graphic.priority, graphic.ttl_ms, graphic.produced_by)
            elif status != "passed":  # the Interpreter's pass is already in the log
                why = {
                    "failed_checks": "The checks rejected every draft",
                    "error": f"The agent team failed ({reason or 'error'})",
                }.get(status, f"The agent team {status}")
                self._log(
                    "agent_failure",
                    "orchestrator",
                    "agent",
                    None,
                    f"{why} on {c.label}; scripted copy used",
                )
                self._create(c, c.copy, c.importance, _ttl(c.copy), SCRIPTED)

    def _queue_summary(self) -> str:
        """The live queue and this producer's recent decisions, for the Producer agent."""
        s = self.state
        queue = [
            f"- {p.type}, priority {p.priority:.2f}, {_seconds_left(p, s.clock_ms)} s left: "
            f"{p.headline.analyst.en}"
            for p in s.pending
        ]
        decisions = [
            f"- {r.action} a {s.types.get(r.proposal_id or '', 'graphic')}: {r.detail}"
            for r in s.audit
            if r.actor_type == "human" and r.action in ("approved", "rejected")
        ][:8]
        return "QUEUE:\n" + (
            "\n".join(queue) or "- empty"
        ) + "\n" "PRODUCER'S RECENT DECISIONS:\n" + ("\n".join(decisions) or "- none yet")

    # --- Decisions -----------------------------------------------------------------------------

    def approve(self, proposal_id: str, request: ApproveRequest, clock_ms: int) -> OnAir:
        """Put a pending proposal on air, optionally with edited copy for one feed profile.

        Raises KeyError if the proposal is not pending (decided, expired, or unknown)."""
        self.attend()
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
        self.attend()
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


def _brief(c: _Candidate) -> list[_Action]:
    """With the agent team, the desk only briefs it when the moment becomes knowable."""
    return [_Action(c.known_ms, "brief", c)]


def _seconds_left(p: Proposal, clock_ms: int) -> int:
    return max(0, (p.expires_at_clock_ms - clock_ms) // 1000)


def _ttl(copy: Copy) -> int:
    return TTL_MS.get(copy.type, DEFAULT_TTL_MS)


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


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"
