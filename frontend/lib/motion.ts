/**
 * The transitions.dev motion tokens for the `motion` library, mirroring the CSS variables in
 * globals.css so JS-driven and CSS-driven animation share one scale. Durations are in seconds.
 */

export const DURATION = {
  quick: 0.15,
  fast: 0.25,
  medium: 0.35,
  slow: 0.4,
  verySlow: 0.5,
} as const;

export const EASE = {
  smoothOut: [0.22, 1, 0.36, 1],
  inOut: "easeInOut",
} as const;
