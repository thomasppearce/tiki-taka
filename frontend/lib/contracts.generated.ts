/* Generated from backend/app/models by `make types`. Do not edit by hand. */

export interface MatchDeskContracts {
  [k: string]: unknown;
}
/**
 * Approve a proposal, optionally editing its copy for one feed's audience and language.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "ApproveRequest".
 */
export interface ApproveRequest {
  profile_id: string;
  headline: string | null;
  body: string | null;
}
/**
 * The same insight written for each audience.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "AudienceBody".
 */
export interface AudienceBody {
  analyst: LocalizedText;
  casual: LocalizedText;
}
/**
 * One piece of copy per supported language. English is always present.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "LocalizedText".
 */
export interface LocalizedText {
  en: string;
  es: string | null;
}
/**
 * A state change, who made it, and what it changed.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "AuditRecord".
 */
export interface AuditRecord {
  audit_id: string;
  timestamp: string;
  match_clock_ms: number | null;
  action: "handoff" | "created" | "approved" | "edited" | "rejected" | "expired" | "agent_failure" | "retry";
  actor_type: "agent" | "human" | "system";
  actor: string;
  proposal_id: string | null;
  before: {
    [k: string]: unknown;
  } | null;
  after: {
    [k: string]: unknown;
  } | null;
  detail: string | null;
}
/**
 * A factual statement made by a proposal. Every claim cites the events that support it.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "Claim".
 */
export interface Claim {
  text: string;
  /**
   * @minItems 1
   */
  evidence_event_ids: [string, ...string[]];
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "ClubRef".
 */
export interface ClubRef {
  club_id: string;
  name: string;
  short: string;
  color: string;
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "Desk".
 */
export interface Desk {
  match_id: string;
  version: number;
  clock_ms: number;
  proposals: Proposal[];
  on_air: OnAir | null;
  audit: AuditRecord[];
  aired: number;
  rejected: number;
  expired: number;
}
/**
 * A candidate graphic or line. It must make at least one cited claim: no narration without
 * receipts. `headline` and `body` are both written per audience and language.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "Proposal".
 */
export interface Proposal {
  proposal_id: string;
  moment_id: string;
  type: "stat_graphic" | "narrative_line" | "tactical_insight" | "player_tag" | "recap_beat";
  priority: number;
  confidence: number;
  expires_at_clock_ms: number;
  headline: AudienceBody;
  body: AudienceBody;
  /**
   * @minItems 1
   */
  claims: [Claim, ...Claim[]];
  status: "pending" | "approved" | "edited" | "rejected" | "expired";
  produced_by: ("interpreter" | "explainer" | "producer" | "localizer" | "renderer" | "orchestrator")[];
  trace_id: string | null;
  /**
   * The player this is about; drives player tags and player focus.
   */
  player_id: string | null;
}
/**
 * An approved graphic on air. Each viewer renders it for their own feed profile.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "OnAir".
 */
export interface OnAir {
  proposal: Proposal;
  template: "lower_third" | "stat_bar" | "player_tag" | "momentum_graph" | "scorebug_update";
  start_clock_ms: number;
  duration_ms: number;
  approved_by: string;
}
/**
 * Measurements attached to an event. Which ones are set depends on the event type.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "EventAttributes".
 */
export interface EventAttributes {
  pass_distance_m: number | null;
  pass_difficulty: number | null;
  /**
   * Ball speed; on shots this is the shot speed.
   */
  ball_speed_kmh: number | null;
  pressure_level: number | null;
  /**
   * The acting player's speed at the moment of the event.
   */
  player_speed_kmh: number | null;
  /**
   * The acting player's cumulative distance this match.
   */
  distance_covered_m: number | null;
  top_speed_kmh: number | null;
  sprint_distance_m: number | null;
  card_color: ("yellow" | "red") | null;
}
/**
 * How much one action changed the game for the acting team.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "EventImpact".
 */
export interface EventImpact {
  event_id: string;
  team_id: string | null;
  /**
   * Expected threat added (negative when possession is lost).
   */
  threat: number;
  importance: number;
}
/**
 * A defining play, ranked by importance, with the events that make it up.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "KeyMoment".
 */
export interface KeyMoment {
  moment_id: string;
  kind: "goal" | "big_chance" | "save" | "red_card" | "decisive_pass" | "ball_won" | "momentum_shift";
  match_clock_ms: number;
  team_id: string | null;
  /**
   * Short English label, e.g. 'Goal: Kallo'.
   */
  label: string;
  importance: number;
  /**
   * @minItems 1
   */
  evidence_event_ids: [string, ...string[]];
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "LeagueGroup".
 */
export interface LeagueGroup {
  league_id: string;
  name: string;
  matches: MatchCard[];
}
/**
 * One match on the match centre: score, clock, a momentum ribbon, and its biggest moment.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "MatchCard".
 */
export interface MatchCard {
  match_id: string;
  league_id: string;
  league_name: string;
  home: ClubRef;
  away: ClubRef;
  score_home: number;
  score_away: number;
  clock_ms: number;
  status: "live" | "full_time";
  featured: boolean;
  momentum: number[];
  top_moment: KeyMoment | null;
}
/**
 * A match event as it happens, with how much it mattered.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "LiveEvent".
 */
export interface LiveEvent {
  event: MatchEvent;
  impact: EventImpact;
}
/**
 * A single timed event in a synthetic match.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "MatchEvent".
 */
export interface MatchEvent {
  event_id: string;
  match_id: string;
  minute: number;
  second: number;
  match_clock_ms: number;
  type:
    | "pass"
    | "shot"
    | "tackle"
    | "possession_change"
    | "pressure"
    | "foul"
    | "card"
    | "substitution"
    | "goal"
    | "save"
    | "sprint"
    | "offside"
    | "kickoff"
    | "half_end";
  team_id: string | null;
  player_id: string | null;
  target_player_id: string | null;
  location: PitchPoint | null;
  end_location: PitchPoint | null;
  outcome: ("success" | "fail" | "blocked" | "saved" | "off_target" | "goal") | null;
  attributes: EventAttributes;
}
/**
 * Normalized pitch coordinates (0-100 on both axes). x runs in the home attacking direction.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "PitchPoint".
 */
export interface PitchPoint {
  x: number;
  y: number;
}
/**
 * Everything needed to open a match: the card, stats, key moments, squads, and recent play.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "MatchDetail".
 */
export interface MatchDetail {
  card: MatchCard;
  home_stats: TeamStats;
  away_stats: TeamStats;
  key_moments: KeyMoment[];
  players: PlayerRef[];
  recent_events: MatchEvent[];
  impacts: EventImpact[];
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "TeamStats".
 */
export interface TeamStats {
  team_id: string;
  goals: number;
  shots: number;
  shots_on_target: number;
  xg: number;
  passes: number;
  pass_accuracy: number;
  possession_pct: number;
  /**
   * Share of both teams' final-third passes made by this team.
   */
  field_tilt_pct: number;
  tackles: number;
  fouls: number;
  offsides: number;
  yellow_cards: number;
  red_cards: number;
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "PlayerRef".
 */
export interface PlayerRef {
  player_id: string;
  club_id: string;
  name: string;
  number: number;
  role: "gk" | "def" | "mid" | "fwd";
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "Matchday".
 */
export interface Matchday {
  clock_ms: number;
  leagues: LeagueGroup[];
}
/**
 * Something worth surfacing, grounded in the events that triggered it.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "Moment".
 */
export interface Moment {
  moment_id: string;
  kind:
    | "momentum_shift"
    | "pressure_spike"
    | "milestone"
    | "tactical_change"
    | "key_chance"
    | "control_vs_chaos"
    | "player_threshold";
  match_clock_ms: number;
  summary: string;
  metrics: {
    [k: string]: number;
  };
  /**
   * @minItems 1
   */
  evidence_event_ids: [string, ...string[]];
}
/**
 * Rendered for one output feed: `profile_id` names the ViewerProfile it was made for.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "OverlayCommand".
 */
export interface OverlayCommand {
  overlay_id: string;
  proposal_id: string;
  profile_id: string;
  template: "lower_third" | "stat_bar" | "player_tag" | "momentum_graph" | "scorebug_update";
  start_clock_ms: number;
  duration_ms: number;
  audience: "analyst" | "casual";
  language: "en" | "es";
  payload: OverlayPayload;
  style: OverlayStyle;
  approved_by: string;
  approved_at: string;
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "OverlayPayload".
 */
export interface OverlayPayload {
  headline: string;
  body: string | null;
  stats: OverlayStat[];
  player_id: string | null;
  /**
   * The feed's spotlight metric (ViewerProfile.spotlight_metric).
   */
  spotlight: OverlayStat | null;
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "OverlayStat".
 */
export interface OverlayStat {
  label: string;
  value: string;
}
/**
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "OverlayStyle".
 */
export interface OverlayStyle {
  theme: string;
  animation_in: "slide_up" | "fade" | "wipe";
  animation_out: "fade" | "slide_down" | "wipe";
}
/**
 * One player's position. Players can stand just off the pitch (throw-ins), hence the margin.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "PlayerPosition".
 */
export interface PlayerPosition {
  player_id: string;
  team_id: string;
  x: number;
  y: number;
  speed_kmh: number | null;
}
/**
 * All 22 players and the ball at one match-clock instant. Streamed alongside MatchEvents so
 * the control room can draw formations moving in sync with the actions.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "TrackingFrame".
 */
export interface TrackingFrame {
  match_id: string;
  match_clock_ms: number;
  ball: PitchPoint;
  /**
   * @minItems 1
   */
  players: [PlayerPosition, ...PlayerPosition[]];
}
/**
 * Setting `focus_player_id` turns on player-focus mode for the feed.
 *
 * This interface was referenced by `MatchDeskContracts`'s JSON-Schema
 * via the `definition` "ViewerProfile".
 */
export interface ViewerProfile {
  profile_id: string;
  audience: "analyst" | "casual";
  language: "en" | "es";
  favorite_club_id: string | null;
  favorite_player_ids: string[];
  focus_player_id: string | null;
  /**
   * The single performance metric this viewer cares about.
   */
  spotlight_metric:
    ("pass_accuracy" | "pass_difficulty" | "distance_covered" | "top_speed" | "shot_speed" | "pressures") | null;
}
