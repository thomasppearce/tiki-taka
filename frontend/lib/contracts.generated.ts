/* Generated from backend/app/models by `make types`. Do not edit by hand. */

export interface MatchDeskContracts {
  [k: string]: unknown;
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
  action: "created" | "approved" | "edited" | "rejected" | "expired" | "agent_failure" | "retry";
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
