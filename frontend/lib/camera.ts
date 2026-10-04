/**
 * A broadcast camera as a planar homography: the projective map from pitch meters to screen
 * pixels. It is fixed by four point correspondences (pitch corner -> screen corner), which is how
 * a real main camera sees the pitch plane. Straight lines stay straight; circles become ellipses.
 */

export type Point = { x: number; y: number };
export type Correspondence = { pitch: Point; screen: Point };
export type Homography = number[]; // row-major 3x3 with h[8] = 1

/** Solve the 8 unknowns of a homography from exactly four correspondences. */
export function solveHomography(pairs: Correspondence[]): Homography {
  if (pairs.length !== 4)
    throw new Error("A homography needs exactly 4 correspondences");
  const rows: number[][] = [];
  for (const { pitch: p, screen: s } of pairs) {
    rows.push([p.x, p.y, 1, 0, 0, 0, -s.x * p.x, -s.x * p.y, s.x]);
    rows.push([0, 0, 0, p.x, p.y, 1, -s.y * p.x, -s.y * p.y, s.y]);
  }
  return [...gaussianSolve(rows), 1];
}

export function project(h: Homography, p: Point): Point {
  const w = h[6] * p.x + h[7] * p.y + h[8];
  return {
    x: (h[0] * p.x + h[1] * p.y + h[2]) / w,
    y: (h[3] * p.x + h[4] * p.y + h[5]) / w,
  };
}

/** Screen pixels per pitch meter at a point (perspective makes far objects smaller). */
export function scaleAt(h: Homography, p: Point): number {
  const a = project(h, { x: p.x - 0.5, y: p.y });
  const b = project(h, { x: p.x + 0.5, y: p.y });
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** SVG path for a polyline of pitch points, projected to screen. */
export function projectPath(
  h: Homography,
  points: Point[],
  close = false,
): string {
  const d = points
    .map((p, i) => {
      const s = project(h, p);
      return `${i ? "L" : "M"}${s.x.toFixed(1)} ${s.y.toFixed(1)}`;
    })
    .join(" ");
  return close ? `${d} Z` : d;
}

/** Points along a circular arc on the pitch, for projecting circles and penalty arcs. */
export function arcPoints(
  center: Point,
  radius: number,
  fromRad = 0,
  toRad = Math.PI * 2,
  segments = 48,
): Point[] {
  return Array.from({ length: segments + 1 }, (_, i) => {
    const t = fromRad + ((toRad - fromRad) * i) / segments;
    return {
      x: center.x + radius * Math.cos(t),
      y: center.y + radius * Math.sin(t),
    };
  });
}

function gaussianSolve(augmented: number[][]): number[] {
  const m = augmented.map((row) => [...row]);
  const n = m.length;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(m[r][col]) > Math.abs(m[pivot][col])) pivot = r;
    }
    [m[col], m[pivot]] = [m[pivot], m[col]];
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const factor = m[r][col] / m[col][col];
      for (let c = col; c <= n; c++) m[r][c] -= factor * m[col][c];
    }
  }
  return m.map((row, i) => row[n] / row[i]);
}
