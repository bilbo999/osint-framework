import type { HealthResponse } from "../types/api.ts";

export const API_PREFIX = "/api/v1";

/** Single place that talks HTTP. Phase 9a adds CSRF header, error mapping and TanStack Query. */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_PREFIX}/health`, { signal, credentials: "same-origin" });
  if (!response.ok) throw new Error(`health check failed: ${response.status}`);
  return (await response.json()) as HealthResponse;
}
