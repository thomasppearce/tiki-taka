/**
 * Mock match state for designing the control room before the real generator and agents exist.
 * Typed against the generated contracts so the UI is built on the shapes the backend will send.
 * Clubs and players are fictional.
 */

import type { MatchEvent, Proposal } from "@/lib/contracts.generated";
import type {
  AgentState,
  AuditLine,
  IncomingTemplate,
  OnAirGraphic,
  TimelineMarker,
} from "@/lib/controlRoom";

export type TeamId = "t_home" | "t_away";

export type Club = { id: TeamId; name: string; short: string };

export const CLUBS: Record<TeamId, Club> = {
  t_home: { id: "t_home", name: "Northgate Rovers", short: "NGR" },
  t_away: { id: "t_away", name: "Westmere Athletic", short: "WMA" },
};

export type Player = { name: string; number: number; team: TeamId };

export const PLAYERS: Record<string, Player> = {
  p_home_01: { name: "Elias Varga", number: 1, team: "t_home" },
  p_home_02: { name: "Ruben Okoro-Lyle", number: 2, team: "t_home" },
  p_home_03: { name: "Sam Ferreira-Holt", number: 3, team: "t_home" },
  p_home_04: { name: "Callum Reyes-Booth", number: 4, team: "t_home" },
  p_home_05: { name: "Dario Pennant", number: 5, team: "t_home" },
  p_home_06: { name: "Mateo Strand", number: 6, team: "t_home" },
  p_home_07: { name: "Lewis Achterberg", number: 7, team: "t_home" },
  p_home_08: { name: "Rafa Quist", number: 8, team: "t_home" },
  p_home_09: { name: "Idris Kallo", number: 9, team: "t_home" },
  p_home_10: { name: "Theo Marlow", number: 10, team: "t_home" },
  p_home_11: { name: "Nico Varnaby", number: 11, team: "t_home" },
  p_away_01: { name: "Anders Vik", number: 1, team: "t_away" },
  p_away_02: { name: "Tobias Wren", number: 2, team: "t_away" },
  p_away_03: { name: "Emil Gasparyan", number: 3, team: "t_away" },
  p_away_04: { name: "Callan Dumas-Reid", number: 4, team: "t_away" },
  p_away_05: { name: "Jonas Mbaye-Ross", number: 5, team: "t_away" },
  p_away_06: { name: "Ollie Kaczmarek", number: 6, team: "t_away" },
  p_away_07: { name: "Kofi Rasmussen", number: 7, team: "t_away" },
  p_away_08: { name: "Benedek Sato", number: 8, team: "t_away" },
  p_away_09: { name: "Marco Desai", number: 9, team: "t_away" },
  p_away_10: { name: "Yusuf Lindqvist", number: 10, team: "t_away" },
  p_away_11: { name: "Ilya Brannock", number: 11, team: "t_away" },
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
  card_color: null,
};

/** Build a MatchEvent; attributes not given are null. */
export function makeEvent(
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
  makeEvent(596, "61:02", "pass", "p_away_06", [52, 30], [38, 18], {
    pass_distance_m: 18.6,
    pass_difficulty: 0.31,
  }),
  makeEvent(598, "61:09", "pass", "p_away_08", [38, 18], [27, 33], {
    pass_distance_m: 14.2,
    pass_difficulty: 0.48,
  }),
  makeEvent(599, "61:14", "pressure", "p_home_06", [29, 35], null, {
    pressure_level: 0.72,
  }),
  makeEvent(601, "61:18", "pass", "p_away_10", [27, 33], [19, 52], {
    pass_distance_m: 15.9,
    pass_difficulty: 0.66,
  }),
  makeEvent(603, "61:25", "pass", "p_away_07", [19, 52], [24, 41], {
    pass_distance_m: 9.4,
    pass_difficulty: 0.42,
  }),
  makeEvent(605, "61:31", "pass", "p_away_10", [24, 41], [14, 30], {
    pass_distance_m: 11.8,
    pass_difficulty: 0.71,
  }),
  makeEvent(606, "61:36", "tackle", "p_home_04", [15, 29]),
  makeEvent(607, "61:44", "pass", "p_away_06", [33, 22], [21, 14], {
    pass_distance_m: 12.5,
    pass_difficulty: 0.37,
  }),
  makeEvent(609, "61:52", "pass", "p_away_07", [21, 14], [12, 44], {
    pass_distance_m: 21.3,
    pass_difficulty: 0.83,
  }),
  makeEvent(611, "61:58", "shot", "p_away_09", [13, 45], null, {
    ball_speed_kmh: 96.4,
  }),
  makeEvent(612, "62:20", "sprint", "p_home_09", [41, 60], [78, 52], {
    top_speed_kmh: 34.2,
    sprint_distance_m: 38.5,
  }),
  makeEvent(614, "62:41", "pass", "p_away_08", [44, 62], [30, 55], {
    pass_distance_m: 14.7,
    pass_difficulty: 0.29,
  }),
  makeEvent(616, "62:55", "pressure", "p_home_08", [31, 54], null, {
    pressure_level: 0.64,
  }),
  makeEvent(618, "63:04", "pass", "p_away_10", [30, 55], [18, 38], {
    pass_distance_m: 14.8,
    pass_difficulty: 0.58,
  }),
];

const now = MATCH.clockMs;

const PIPELINE_AGENTS: Proposal["produced_by"] = [
  "interpreter",
  "explainer",
  "producer",
  "localizer",
];

export const PROPOSALS: Proposal[] = [
  {
    proposal_id: "prop_0141",
    moment_id: "mom_0087",
    type: "tactical_insight",
    priority: 0.86,
    confidence: 0.91,
    expires_at_clock_ms: now + 42_000,
    headline: {
      analyst: {
        en: "Westmere are pinning Northgate back",
        es: "Westmere encierra al Northgate en su campo",
      },
      casual: {
        en: "Westmere are all over Northgate",
        es: "Westmere no deja respirar al Northgate",
      },
    },
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
    produced_by: PIPELINE_AGENTS,
    trace_id: "trc_5e0a91c2",
    player_id: null,
  },
  {
    proposal_id: "prop_0142",
    moment_id: "mom_0088",
    type: "player_tag",
    priority: 0.74,
    confidence: 0.97,
    expires_at_clock_ms: now + 18_000,
    headline: {
      analyst: {
        en: "Kallo hits 34.2 km/h on the break",
        es: "Kallo alcanza 34,2 km/h en la contra",
      },
      casual: {
        en: "Kallo is flying: 34.2 km/h",
        es: "Kallo vuela: 34,2 km/h",
      },
    },
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
    produced_by: PIPELINE_AGENTS,
    trace_id: "trc_7b14d0e9",
    player_id: "p_home_09",
  },
  {
    proposal_id: "prop_0143",
    moment_id: "mom_0084",
    type: "stat_graphic",
    priority: 0.52,
    confidence: 0.95,
    expires_at_clock_ms: now + 75_000,
    headline: {
      analyst: {
        en: "Marlow keeps Northgate ticking under pressure",
        es: "Marlow sostiene al Northgate bajo presión",
      },
      casual: {
        en: "Marlow stays calm in the storm",
        es: "Marlow mantiene la calma en plena tormenta",
      },
    },
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
    produced_by: PIPELINE_AGENTS,
    trace_id: "trc_c3d2a7f0",
    player_id: "p_home_10",
  },
];

/**
 * Proposals the simulated agents produce during the session, in order. Every claim is backed by
 * events in RECENT_EVENTS, and the copy says nothing those events do not support.
 */
export const INCOMING_TEMPLATES: IncomingTemplate[] = [
  {
    ttlMs: 45_000,
    localizerFails: false,
    proposal: {
      type: "stat_graphic",
      priority: 0.79,
      confidence: 0.98,
      headline: {
        analyst: {
          en: "Desai's strike clocked at 96.4 km/h",
          es: "El disparo de Desai, a 96,4 km/h",
        },
        casual: {
          en: "Desai nearly breaks the net",
          es: "Desai casi rompe la red",
        },
      },
      body: {
        analyst: {
          en: "Hardest shot of the match so far, struck from 14 m.",
          es: "El disparo más potente del partido hasta ahora, desde 14 m.",
        },
        casual: {
          en: "Marco Desai hit that one at 96 km/h. Westmere are getting closer.",
          es: "Marco Desai le pegó a 96 km/h. Westmere se acerca.",
        },
      },
      claims: [
        {
          text: "Shot speed 96.4 km/h, the fastest this match",
          evidence_event_ids: ["evt_000611"],
        },
      ],
      status: "pending",
      produced_by: PIPELINE_AGENTS,
      trace_id: "trc_19ac44b0",
      player_id: "p_away_09",
    },
  },
  {
    ttlMs: 50_000,
    localizerFails: true,
    proposal: {
      type: "tactical_insight",
      priority: 0.83,
      confidence: 0.88,
      headline: {
        analyst: {
          en: "Northgate drop into a low block",
          es: "El Northgate se repliega en bloque bajo",
        },
        casual: {
          en: "Northgate are parking the bus",
          es: "El Northgate aparca el autobús",
        },
      },
      body: {
        analyst: {
          en: "Their last three defensive actions all came within 33 m of their own goal, the deepest at 16 m.",
          es: "Sus tres últimas acciones defensivas fueron a menos de 33 m de su portería, la más profunda a 16 m.",
        },
        casual: {
          en: "Northgate have pulled everyone back to protect the lead.",
          es: "El Northgate ha metido a todos atrás para proteger la ventaja.",
        },
      },
      claims: [
        {
          text: "Last 3 defensive actions all within 33 m of their own goal",
          evidence_event_ids: ["evt_000599", "evt_000606", "evt_000616"],
        },
      ],
      status: "pending",
      produced_by: PIPELINE_AGENTS,
      trace_id: "trc_8d02f5e1",
      player_id: null,
    },
  },
  {
    ttlMs: 55_000,
    localizerFails: false,
    proposal: {
      type: "narrative_line",
      priority: 0.68,
      confidence: 0.9,
      headline: {
        analyst: {
          en: "Lindqvist is running this spell",
          es: "Lindqvist dirige este dominio",
        },
        casual: {
          en: "Lindqvist is pulling the strings",
          es: "Lindqvist mueve los hilos",
        },
      },
      body: {
        analyst: {
          en: "Played 3 of Westmere's last 8 final-third passes, including two of the three hardest (difficulty 71 and 66).",
          es: "Ha dado 3 de los últimos 8 pases de Westmere en el último tercio, incluidos dos de los tres más difíciles (dificultad 71 y 66).",
        },
        casual: {
          en: "Yusuf Lindqvist keeps getting on the ball in dangerous areas.",
          es: "Yusuf Lindqvist no para de aparecer en zonas peligrosas.",
        },
      },
      claims: [
        {
          text: "3 of Westmere's last 8 final-third passes",
          evidence_event_ids: ["evt_000601", "evt_000605", "evt_000618"],
        },
        {
          text: "Pass difficulty 71 and 66, two of the three hardest",
          evidence_event_ids: ["evt_000605", "evt_000601"],
        },
      ],
      status: "pending",
      produced_by: PIPELINE_AGENTS,
      trace_id: "trc_5b7e2c3a",
      player_id: "p_away_10",
    },
  },
];

/** The graphic already on air when the session opens (approved before 63:00). */
export const INITIAL_ON_AIR: OnAirGraphic = {
  id: "ovl_0139",
  template: "lower_third",
  label: { en: "Second half", es: "Segunda parte" },
  headline: {
    analyst: { en: "Westmere have the ball", es: "Westmere tiene el balón" },
    casual: { en: "It's all Westmere", es: "Todo es de Westmere" },
  },
  split: { t_away: 58, t_home: 42 },
  splitLabel: { en: "Possession", es: "Posesión" },
  startedAtMs: now - 2_000,
  durationMs: 9_000,
};

/** Momentum for a minute, -1 (Westmere on top) to 1 (Northgate on top). */
export function momentumAt(minute: number): number {
  const wave =
    0.32 * Math.sin(minute / 6.5) + 0.18 * Math.sin(minute / 2.7 + 1.3);
  const homeSpell = minute > 14 && minute < 32 ? 0.35 : 0;
  const awaySurge =
    minute > 54 ? -0.75 * (1 - Math.exp(-(minute - 54) / 5)) : 0;
  return Math.max(-0.95, Math.min(0.95, wave + homeSpell + awaySurge));
}

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

/** Agent states for prop_0141, shown until the orchestrator starts its first job. */
export const INITIAL_AGENT_STATES: AgentState[] = [
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
    status: "done",
    detail: "4 variants written after 1 retry",
  },
];

export const INITIAL_AUDIT_LOG: AuditLine[] = [
  {
    id: "a4",
    clock: "63:11",
    actor: "localizer",
    text: "Retried prop_0141: es body now passes validation",
  },
  {
    id: "a3",
    clock: "63:09",
    actor: "producer",
    text: "Queued prop_0141 at priority 0.86",
  },
  {
    id: "a2",
    clock: "62:47",
    actor: "you",
    text: "Approved prop_0139 (possession) for Analyst EN",
  },
  {
    id: "a1",
    clock: "62:30",
    actor: "producer",
    text: "Expired prop_0137 without a decision",
  },
];
