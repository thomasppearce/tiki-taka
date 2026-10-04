/** The Match Desk backend: where it is, and small typed helpers for its REST endpoints. */

// Must be referenced literally so Next.js can inline it at build time.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

/** The fixture the full agent team works on, and the one the control room opens. */
export const FEATURED_MATCH_ID = "m_l1_1";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} on ${path}`);
  }
  return (await response.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function postJson<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
