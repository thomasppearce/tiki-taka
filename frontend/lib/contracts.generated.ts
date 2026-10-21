/* Generated from backend/app/models by `make types`. Do not edit by hand. */

export interface TikiTakaContracts {
  [k: string]: unknown;
}
/**
 * Approve a proposal, optionally editing its copy for one feed's audience and language.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "AudienceBody".
 */
export interface AudienceBody {
  analyst: LocalizedText;
  casual: LocalizedText;
}
/**
 * One piece of copy per supported language. English is always present.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "LocalizedText".
 */
export interface LocalizedText {
  en: string;
  es: string | null;
}
/**
 * A state change, who made it, and what it changed.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * A goal that changed the top of the Golden Boot race. Written by code, citable.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "BootSwing".
 */
export interface BootSwing {
  match_clock_ms: number;
  match_id: string;
  /**
   * The goal.
   */
  event_id: string;
  player_id: string;
  summary: string;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Channel".
 */
export interface Channel {
  clock_ms: number;
  version: number;
  on_air: Cut;
  pending: PendingCut | null;
  /**
   * The producer has paused automatic cuts.
   */
  held: boolean;
  /**
   * The producer has fixed the feed on a match.
   */
  pinned_match_id: string | null;
  /**
   * Earlier cuts, newest first.
   */
  history: Cut[];
  /**
   * Every live match, most deserving first.
   */
  signals: MatchSignal[];
  /**
   * What the Director, Watchers, and producer did.
   */
  log: ChannelLog[];
  /**
   * The Watcher and Director agents are connected.
   */
  agents: boolean;
  lens: Lens;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Cut".
 */
export interface Cut {
  cut_id: string;
  match_id: string;
  clock_ms: number;
  reason: "kickoff" | "goal" | "penalty" | "pressure" | "check_in" | "manual";
  decided_by: "code" | "director" | "producer";
  package: CutPackage;
  /**
   * Open with a replay of this goal or chance.
   */
  replay_event_id: string | null;
  /**
   * A split screen: the match the cut left, kept beside it while it matters.
   */
  also_match_id: string | null;
  /**
   * Why that match stays on screen (code-written).
   */
  also_why: string | null;
  /**
   * When the split ends.
   */
  also_until_ms: number | null;
}
/**
 * What the viewer is told when the feed cuts to a match.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "CutPackage".
 */
export interface CutPackage {
  /**
   * Why we're here.
   */
  why: string;
  /**
   * What a goal here would change in the table.
   */
  at_stake: string | null;
  /**
   * The story of this match so far.
   */
  story: string;
  claims: Claim[];
  /**
   * 'code', or the agents that wrote it.
   */
  written_by: string[];
  /**
   * On a personal whip-around: what this match means to you.
   */
  for_you: string | null;
  /**
   * A player's story here (the Golden Boot race, a milestone...), by code.
   */
  storyline: string | null;
}
/**
 * A factual statement made by a proposal. Every claim cites the events that support it.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * The Director's next cut, counting down. The producer can take it now or hold it.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "PendingCut".
 */
export interface PendingCut {
  match_id: string;
  reason: "kickoff" | "goal" | "penalty" | "pressure" | "check_in" | "manual";
  proposed_ms: number;
  take_at_ms: number;
  package: CutPackage;
  replay_event_id: string | null;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "MatchSignal".
 */
export interface MatchSignal {
  match_id: string;
  home: SideSignal;
  away: SideSignal;
  /**
   * How much the match deserves the screen right now.
   */
  score: number;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "SideSignal".
 */
export interface SideSignal {
  club_id: string;
  /**
   * Something about to happen: recent threat, shots.
   */
  pressure: number;
  /**
   * What a goal for this side would change (table weight).
   */
  stake: number;
  stake_summary: string | null;
}
/**
 * One line of the channel's log: who did what, when.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "ChannelLog".
 */
export interface ChannelLog {
  clock_ms: number;
  agent: "director" | "watcher" | "checker" | "producer" | "code";
  match_id: string | null;
  detail: string;
}
/**
 * Whose whip-around this is: everyone's channel, a fan's club, or a fan's fantasy XI.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Lens".
 */
export interface Lens {
  kind: "channel" | "club" | "fantasy";
  club_id: string | null;
  /**
   * With live points.
   */
  xi: FantasyPlayer[];
  /**
   * The fantasy XI's total, as it stands.
   */
  points: number;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "FantasyPlayer".
 */
export interface FantasyPlayer {
  player_id: string;
  name: string;
  number: number;
  role: "gk" | "def" | "mid" | "fwd";
  club_id: string;
  match_id: string;
  /**
   * On the pitch now (or at full time).
   */
  on_pitch: boolean;
  points: number;
  items: FantasyItem[];
}
/**
 * One line of a fantasy player's score, with the events that earned it.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "FantasyItem".
 */
export interface FantasyItem {
  label: string;
  points: number;
  event_ids: string[];
}
/**
 * Move the matchday clock (a demo control): to `minute` minutes played (as
 * MATCH_START_MINUTE counts them: 55 is where a cold start begins), or, with no minute, to the
 * moment the day's last match ends.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "ClockRequest".
 */
export interface ClockRequest {
  minute: number | null;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "ClubRef".
 */
export interface ClubRef {
  club_id: string;
  name: string;
  short: string;
  color: string;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
  produced_by: (
    "interpreter" | "explainer" | "checker" | "fact_checker" | "producer" | "localizer" | "renderer" | "orchestrator"
  )[];
  trace_id: string | null;
  /**
   * The player this is about; drives player tags and player focus.
   */
  player_id: string | null;
}
/**
 * An approved graphic on air. Each viewer renders it for their own feed profile.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * Start a drill: `blip` fails the agent's next model call once (the retry recovers it);
 * `down` fails every call for a few minutes (the system falls back).
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "DrillRequest".
 */
export interface DrillRequest {
  agent: "interpreter" | "explainer" | "fact_checker" | "producer" | "localizer" | "watcher" | "director";
  mode: "blip" | "down";
}
/**
 * The drill now: which agent is failing and how, or none.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "DrillState".
 */
export interface DrillState {
  agent: ("interpreter" | "explainer" | "fact_checker" | "producer" | "localizer" | "watcher" | "director") | null;
  mode: ("blip" | "down") | null;
  /**
   * Until a `down` drill ends by itself.
   */
  seconds_left: number;
}
/**
 * Measurements attached to an event. Which ones are set depends on the event type.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * The season's top scorers as it stands, and the goals that changed the top of the race.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "GoldenBoot".
 */
export interface GoldenBoot {
  rows: ScorerRow[];
  /**
   * Oldest first.
   */
  swings: BootSwing[];
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "ScorerRow".
 */
export interface ScorerRow {
  /**
   * Players level share a position.
   */
  position: number;
  player_id: string;
  name: string;
  club: ClubRef;
  /**
   * League goals before today.
   */
  season_goals: number;
  today: number;
  goals: number;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "HoldRequest".
 */
export interface HoldRequest {
  held: boolean;
}
/**
 * A defining play, ranked by importance, with the events that make it up.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "LeagueTable".
 */
export interface LeagueTable {
  clock_ms: number;
  /**
   * Which round of the season this is.
   */
  matchday_number: number;
  /**
   * The season's last: the title and the drop are decided.
   */
  last_matchday: boolean;
  rows: TableRow[];
  /**
   * Every zone change so far today, oldest first.
   */
  swings: TableSwing[];
  /**
   * For each live match and side, what a goal would do.
   */
  stakes: Stake[];
  golden_boot: GoldenBoot;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "TableRow".
 */
export interface TableRow {
  position: number;
  club: ClubRef;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  zone: ("champions" | "continental" | "relegation") | null;
  /**
   * Position before today's kickoff.
   */
  start_position: number;
  /**
   * Today's match.
   */
  match_id: string;
  /**
   * Today's match as it stands (or as it ended).
   */
  result: "winning" | "drawing" | "losing";
}
/**
 * A goal that changed the table's zones: who moved where. Written by code, citable.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "TableSwing".
 */
export interface TableSwing {
  match_clock_ms: number;
  match_id: string;
  /**
   * The goal.
   */
  event_id: string;
  changes: ZoneChange[];
  /**
   * One sentence, e.g. 'Halvern Town go top on goal difference.'
   */
  summary: string;
}
/**
 * One club moving into or out of a zone.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "ZoneChange".
 */
export interface ZoneChange {
  club_id: string;
  from_position: number;
  to_position: number;
  from_zone: ("champions" | "continental" | "relegation") | null;
  to_zone: ("champions" | "continental" | "relegation") | null;
}
/**
 * What one more goal for one side in one live match would change in the table right now.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Stake".
 */
export interface Stake {
  match_id: string;
  scorer_club_id: string;
  changes: ZoneChange[];
  summary: string;
  /**
   * How much the change matters: title and drop 1, top four 0.5.
   */
  weight: number;
}
/**
 * A match event as it happens, with how much it mattered.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "LiveEvent".
 */
export interface LiveEvent {
  event: MatchEvent;
  impact: EventImpact;
}
/**
 * A single timed event in a synthetic match.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
    | "throw_in"
    | "goal_kick"
    | "corner"
    | "free_kick"
    | "penalty"
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "PitchPoint".
 */
export interface PitchPoint {
  x: number;
  y: number;
}
/**
 * Everything needed to open a match: the card, stats, key moments, squads, and recent play.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * One match's recap at its final whistle: written by its Watcher and checked (or by code,
 * from its goals, if every draft failed its checks or the agents are off).
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "MatchRecap".
 */
export interface MatchRecap {
  match_id: string;
  status: "pending" | "writing" | "ready";
  home: ClubRef;
  away: ClubRef;
  /**
   * The final score.
   */
  score_home: number;
  score_away: number;
  written_by: ("agents" | "code") | null;
  headline: string | null;
  story: string | null;
  claims: Claim[];
  checks: string[];
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Matchday".
 */
export interface Matchday {
  clock_ms: number;
  /**
   * Which round of the season this is.
   */
  matchday_number: number;
  /**
   * The season's last: the title and the drop are decided.
   */
  last_matchday: boolean;
  leagues: LeagueGroup[];
}
/**
 * Something worth surfacing, grounded in the events that triggered it.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "OverlayStat".
 */
export interface OverlayStat {
  label: string;
  value: string;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "OverlayStyle".
 */
export interface OverlayStyle {
  theme: string;
  animation_in: "slide_up" | "fade" | "wipe";
  animation_out: "fade" | "slide_down" | "wipe";
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "PinRequest".
 */
export interface PinRequest {
  match_id: string | null;
}
/**
 * One player's position. Players can stand just off the pitch (throw-ins), hence the margin.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * How a matchday unfolded: written by the recap writer agent and checked (or by code, if
 * every draft failed its checks or the agents are off), beside where code says the day left
 * the table. On the season's last matchday that is how the season ended.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Recap".
 */
export interface Recap {
  /**
   * pending: matches still playing; writing: the agent is on it; ready.
   */
  status: "pending" | "writing" | "ready";
  matchday: number | null;
  /**
   * The season's last matchday: the top is the champions.
   */
  season_over: boolean;
  written_by: ("agents" | "code") | null;
  headline: string | null;
  standfirst: string | null;
  beats: RecapBeat[];
  top: ClubRef | null;
  top_four: ClubRef[];
  /**
   * The relegation places: relegated, if the season is over.
   */
  bottom_three: ClubRef[];
  /**
   * The leader (the winner).
   */
  golden_boot: ScorerRow | null;
  facts: RecapFact[];
  /**
   * What the checkers sent back on the way, if anything.
   */
  checks: string[];
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "RecapBeat".
 */
export interface RecapBeat {
  minute: number;
  match_id: string | null;
  text: string;
  /**
   * The facts this beat rests on.
   */
  fact_ids: string[];
}
/**
 * One fact written by code: an outcome, a goal that moved the table or the Golden Boot, or
 * a final score. The recap's beats cite these by id.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "RecapFact".
 */
export interface RecapFact {
  /**
   * A goal ('<match_id>:<event_id>'), a final score ('ft:<match_id>'), or an outcome ('final:<what>').
   */
  fact_id: string;
  minute: number | null;
  match_id: string | null;
  text: string;
}
/**
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Replay".
 */
export interface Replay {
  match_id: string;
  /**
   * The goal or shot replayed.
   */
  event_id: string;
  kind: "goal" | "chance";
  /**
   * One line, e.g. 'Ambrose scores for Halvern Town'.
   */
  label: string;
  /**
   * What the goal changed in the table, e.g. 'As it stands: Halvern Town go top'.
   */
  as_it_stands: string | null;
  from_ms: number;
  to_ms: number;
  /**
   * Slow motion from here...
   */
  slow_from_ms: number;
  /**
   * ...to here: the shot.
   */
  slow_to_ms: number;
  shooter_id: string | null;
  /**
   * Every 250 ms across the window.
   */
  frames: TrackingFrame[];
  /**
   * The events in the window, oldest first.
   */
  events: MatchEvent[];
}
/**
 * All 22 players and the ball at one match-clock instant. Streamed alongside MatchEvents so
 * the control room can draw formations moving in sync with the actions.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
 * Every player in the league, for picking a fantasy XI, and a suggested XI.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "Squads".
 */
export interface Squads {
  players: PlayerRef[];
  suggested_xi: string[];
  /**
   * How fantasy points are scored, one rule per line.
   */
  rules: string[];
}
/**
 * Take the pending cut now (no match_id), or cut straight to a match.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "TakeRequest".
 */
export interface TakeRequest {
  match_id: string | null;
}
/**
 * Setting `focus_player_id` turns on player-focus mode for the feed.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
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
/**
 * A fan's own matchday beside the recap, written by code from the same facts: what the day
 * did to their club (its result, where it finished, the goals that moved it), or how their
 * fantasy XI scored. A guest gets the recap alone.
 *
 * This interface was referenced by `TikiTakaContracts`'s JSON-Schema
 * via the `definition` "YourDay".
 */
export interface YourDay {
  /**
   * pending until the day's last match ends.
   */
  status: "pending" | "writing" | "ready";
  kind: ("club" | "fantasy") | null;
  club: ClubRef | null;
  headline: string | null;
  /**
   * Each with the goal or result behind it.
   */
  lines: RecapFact[];
  /**
   * The fantasy XI's total.
   */
  points: number | null;
}
