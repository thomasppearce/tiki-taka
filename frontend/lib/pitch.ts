/** Pitch geometry in meters (FIFA standard 105 x 68). Event coordinates are normalized 0-100. */

export const PITCH = { length: 105, width: 68 } as const;

/** SVG viewBox with 2m of margin so the goals and outer lines aren't clipped. */
export const PITCH_VIEWBOX = "-2 -2 109 72";

export function toPitch(point: { x: number; y: number }): {
  x: number;
  y: number;
} {
  return {
    x: (point.x / 100) * PITCH.length,
    y: (point.y / 100) * PITCH.width,
  };
}
