/**
 * Mock match state for designing the control room before the real generator and agents exist.
 * Typed against the generated contracts so the UI is built on the shapes the backend will send.
 * Clubs and players are fictional.
 */

import type { MatchEvent, Proposal } from "@/lib/contracts.generated";

export type TeamId = "t_home" | "t_away";

export type Club = { id: TeamId; name: string; short: string };

export const CLUBS: Record<TeamId, Club> = {
  t_home: { id: "t_home", name: "Northgate Rovers", short: "NGR" },
  t_away: { id: "t_away", name: "Westmere Athletic", short: "WMA" },
};

export type Player = { name: string; number: number; team: TeamId };

export const PLAYERS: Record<string, Player> = {
  p_home_01: { name: "Elias Varga", number: 1, team: "t_home" },
  p_home_04: { name: "Callum Reyes-Booth", number: 4, team: "t_home" },
  p_home_06: { name: "Mateo Strand", number: 6, team: "t_home" },
  p_home_08: { name: "Rafa Quist", number: 8, team: "t_home" },
  p_home_09: { name: "Idris Kallo", number: 9, team: "t_home" },
  p_home_10: { name: "Theo Marlow", number: 10, team: "t_home" },
  p_away_01: { name: "Anders Vik", number: 1, team: "t_away" },
  p_away_06: { name: "Ollie Kaczmarek", number: 6, team: "t_away" },
  p_away_07: { name: "Kofi Rasmussen", number: 7, team: "t_away" },
  p_away_08: { name: "Benedek Sato", number: 8, team: "t_away" },
  p_away_09: { name: "Marco Desai", number: 9, team: "t_away" },
  p_away_10: { name: "Yusuf Lindqvist", number: 10, team: "t_away" },
};

export const MATCH = {
  clockMs: 3_792_000,
  period: "2H",
  score: { t_home: 1, t_away: 0 },
  storyline: "Second-half comeback",
};

const EMPTY_ATTRIBUTES: MatchEvent["attributes"] = {
  pass_distance_m: null,
  pass_difficulty: null,
  ball_speed_kmh: null,
  pressure_level: null,
  player_speed_kmh: null,
  distance_covered_m: null,
  top_speed_kmh: null,
  sprint_distance_m: null,
};

function event(
  n: number,
  clock: string,
  type: MatchEvent["type"],
  player: string,
  at: [number, number],
  to: [number, number] | null = null,
  attributes: Partial<MatchEvent["attributes"]> = {},
): MatchEvent {
  const [minute, second] = clock.split(":").map(Number);
  return {
    event_id: `evt_${String(n).padStart(6, "0")}`,
    match_id: "m_demo",
    minute,
    second,
    match_clock_ms: (minute * 60 + second) * 1000,
    type,
    team_id: PLAYERS[player].team,
    player_id: player,
    target_player_id: null,
    location: { x: at[0], y: at[1] },
    end_location: to ? { x: to[0], y: to[1] } : null,
    outcome: "success",
    attributes: { ...EMPTY_ATTRIBUTES, ...attributes },
  };
}

/** Recent events, oldest first. Home attacks toward x = 100, so Westmere pressure sits at low x. */
export const RECENT_EVENTS: MatchEvent[] = [
  event(596, "61:02", "pass", "p_away_06", [52, 30], [38, 18], {
    pass_distance_m: 18.6,
    pass_difficulty: 0.31,
  }),
  event(598, "61:09", "pass", "p_away_08", [38, 18], [27, 33], {
    pass_distance_m: 14.2,
    pass_difficulty: 0.48,
  }),
  event(599, "61:14", "pressure", "p_home_06", [29, 35], null, {
    pressure_level: 0.72,
  }),
  event(601, "61:18", "pass", "p_away_10", [27, 33], [19, 52], {
    pass_distance_m: 15.9,
    pass_difficulty: 0.66,
  }),
  event(603, "61:25", "pass", "p_away_07", [19, 52], [24, 41], {
    pass_distance_m: 9.4,
    pass_difficulty: 0.42,
  }),
  event(605, "61:31", "pass", "p_away_10", [24, 41], [14, 30], {
    pass_distance_m: 11.8,
    pass_difficulty: 0.71,
  }),
  event(606, "61:36", "tackle", "p_home_04", [15, 29]),
  event(607, "61:44", "pass", "p_away_06", [33, 22], [21, 14], {
    pass_distance_m: 12.5,
    pass_difficulty: 0.37,
  }),
  event(609, "61:52", "pass", "p_away_07", [21, 14], [12, 44], {
    pass_distance_m: 21.3,
    pass_difficulty: 0.83,
  }),
  event(611, "61:58", "shot", "p_away_09", [13, 45], null, {
    ball_speed_kmh: 96.4,
  }),
  event(612, "62:20", "sprint", "p_home_09", [41, 60], [78, 52], {
    top_speed_kmh: 34.2,
    sprint_distance_m: 38.5,
  }),
  event(614, "62:41", "pass", "p_away_08", [44, 62], [30, 55], {
    pass_distance_m: 14.7,
    pass_difficulty: 0.29,
  }),
  event(616, "62:55", "pressure", "p_home_08", [31, 54], null, {
    pressure_level: 0.64,
  }),
  event(618, "63:04", "pass", "p_away_10", [30, 55], [18, 38], {
    pass_distance_m: 14.8,
    pass_difficulty: 0.58,
  }),
];

const now = MATCH.clockMs;

export const PROPOSALS: Proposal[] = [
  {
    proposal_id: "prop_0141",
    moment_id: "mom_0087",
    type: "tactical_insight",
    priority: 0.86,
    confidence: 0.91,
    expires_at_clock_ms: now + 42_000,
    headline: "Westmere are pinning Northgate back",
    body: {
      analyst: {
        en: "Field tilt has swung from 41% to 68% for Westmere since the 55th minute, and each of their last 8 passes ended in the final third.",
        es: "La inclinación del campo pasó del 41% al 68% para Westmere desde el minuto 55, y sus últimos 8 pases terminaron en el último tercio.",
      },
      casual: {
        en: "Westmere have camped in Northgate's half for eight minutes. The equaliser feels close.",
        es: "Westmere lleva ocho minutos instalado en campo del Northgate. El empate se siente cerca.",
      },
    },
    claims: [
      {
        text: "Field tilt rose from 41% to 68% since 55'",
        evidence_event_ids: [
          "evt_000598",
          "evt_000601",
          "evt_000607",
          "evt_000618",
        ],
      },
      {
        text: "Westmere's last 8 passes all ended in the final third",
        evidence_event_ids: [
          "evt_000598",
          "evt_000601",
          "evt_000603",
          "evt_000605",
          "evt_000607",
          "evt_000609",
          "evt_000614",
          "evt_000618",
        ],
      },
    ],
    status: "pending",
    produced_by: ["interpreter", "explainer", "producer", "localizer"],
    trace_id: "trc_5e0a91c2",
  },
  {
    proposal_id: "prop_0142",
    moment_id: "mom_0088",
    type: "player_tag",
    priority: 0.74,
    confidence: 0.97,
    expires_at_clock_ms: now + 18_000,
    headline: "Kallo hits 34.2 km/h on the break",
    body: {
      analyst: {
        en: "Fastest sprint of the match: 38.5 m at a peak of 34.2 km/h, his third run above 32 km/h.",
        es: "El sprint más rápido del partido: 38,5 m con un pico de 34,2 km/h, su tercera carrera por encima de 32 km/h.",
      },
      casual: {
        en: "Idris Kallo just hit 34.2 km/h. Nobody has run faster tonight.",
        es: "Idris Kallo acaba de alcanzar 34,2 km/h. Nadie ha corrido más rápido esta noche.",
      },
    },
    claims: [
      {
        text: "Top speed 34.2 km/h over 38.5 m",
        evidence_event_ids: ["evt_000612"],
      },
    ],
    status: "pending",
    produced_by: ["interpreter", "explainer", "producer", "localizer"],
    trace_id: "trc_7b14d0e9",
  },
  {
    proposal_id: "prop_0143",
    moment_id: "mom_0084",
    type: "stat_graphic",
    priority: 0.52,
    confidence: 0.95,
    expires_at_clock_ms: now + 75_000,
    headline: "Marlow keeps Northgate ticking under pressure",
    body: {
      analyst: {
        en: "Theo Marlow has completed 19 of 21 passes while pressed this half, the most of any midfielder.",
        es: "Theo Marlow ha completado 19 de 21 pases bajo presión en esta mitad, la mayor cifra entre los centrocampistas.",
      },
      casual: {
        en: "Even with Westmere swarming, Theo Marlow keeps finding a teammate.",
        es: "Aunque Westmere presiona en masa, Theo Marlow sigue encontrando a un compañero.",
      },
    },
    claims: [
      {
        text: "19 of 21 passes completed under pressure this half",
        evidence_event_ids: ["evt_000521", "evt_000547", "evt_000588"],
      },
    ],
    status: "pending",
    produced_by: ["interpreter", "explainer", "producer", "localizer"],
    trace_id: "trc_c3d2a7f0",
  },
];

/** Player positions for the program monitor's synthetic camera frame (normalized 0-100). */
export const FEED_SNAPSHOT = {
  ball: { x: 19, y: 52 },
  players: [
    { team: "t_home", x: 4, y: 50 },
    { team: "t_home", x: 13, y: 26 },
    { team: "t_home", x: 12, y: 42 },
    { team: "t_home", x: 13, y: 58 },
    { team: "t_home", x: 16, y: 74 },
    { team: "t_home", x: 23, y: 44 },
    { team: "t_home", x: 24, y: 61 },
    { team: "t_home", x: 30, y: 22 },
    { team: "t_home", x: 31, y: 80 },
    { team: "t_home", x: 39, y: 47 },
    { team: "t_home", x: 45, y: 63 },
    { team: "t_away", x: 93, y: 50 },
    { team: "t_away", x: 52, y: 30 },
    { team: "t_away", x: 50, y: 50 },
    { team: "t_away", x: 53, y: 70 },
    { team: "t_away", x: 35, y: 35 },
    { team: "t_away", x: 30, y: 55 },
    { team: "t_away", x: 38, y: 76 },
    { team: "t_away", x: 20, y: 39 },
    { team: "t_away", x: 17, y: 60 },
    { team: "t_away", x: 26, y: 18 },
    { team: "t_away", x: 24, y: 86 },
  ] satisfies { team: TeamId; x: number; y: number }[],
};

/** The overlay currently on air in the program monitor. */
export const ON_AIR = {
  label: "Second half",
  headline: "Westmere have the ball",
  split: { t_away: 58, t_home: 42 },
  splitLabel: "Possession",
};

/** Momentum per minute, -1 (Westmere on top) to 1 (Northgate on top). */
export const MOMENTUM: number[] = Array.from({ length: 64 }, (_, minute) => {
  const wave =
    0.32 * Math.sin(minute / 6.5) + 0.18 * Math.sin(minute / 2.7 + 1.3);
  const homeSpell = minute > 14 && minute < 32 ? 0.35 : 0;
  const awaySurge = minute > 54 ? -0.12 * (minute - 54) : 0;
  return Math.max(-0.95, Math.min(0.95, wave + homeSpell + awaySurge));
});

export type TimelineMarker = {
  minute: number;
  kind: "goal" | "moment" | "aired";
  team?: TeamId;
  label: string;
};

export const TIMELINE_MARKERS: TimelineMarker[] = [
  { minute: 23, kind: "goal", team: "t_home", label: "Goal: Kallo" },
  { minute: 31, kind: "aired", label: "Aired: Marlow passing map" },
  {
    minute: 47,
    kind: "aired",
    label: "Aired: Westmere switch to a back three",
  },
  { minute: 56, kind: "moment", label: "Momentum shift detected" },
  { minute: 62, kind: "moment", label: "Kallo sprint threshold" },
];

export type AgentName = Proposal["produced_by"][number];

export type AgentState = {
  agent: AgentName;
  status: "done" | "working" | "retrying" | "idle";
  detail: string;
};

export const AGENT_STATES: AgentState[] = [
  {
    agent: "interpreter",
    status: "done",
    detail: "Momentum shift: field tilt +27 pts",
  },
  {
    agent: "explainer",
    status: "done",
    detail: "2 claims grounded in 6 events",
  },
  {
    agent: "producer",
    status: "done",
    detail: "Ranked 1st of 3, 42s to expiry",
  },
  {
    agent: "localizer",
    status: "retrying",
    detail: "Spanish variant failed schema, retry 1 of 3",
  },
  { agent: "renderer", status: "idle", detail: "Waiting for approval" },
];

export type AuditLine = { clock: string; actor: string; text: string };

export const AUDIT_LOG: AuditLine[] = [
  {
    clock: "63:11",
    actor: "localizer",
    text: "Retrying prop_0141: es body failed validation",
  },
  {
    clock: "63:09",
    actor: "producer",
    text: "Queued prop_0141 at priority 0.86",
  },
  {
    clock: "62:47",
    actor: "you",
    text: "Approved prop_0139 (stat graphic) for Analyst EN",
  },
  {
    clock: "62:30",
    actor: "producer",
    text: "Expired prop_0137 after 60s without a decision",
  },
];
