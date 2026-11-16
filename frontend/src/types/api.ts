// Wire types. From Phase 9a on these are generated from /api/v1/openapi.json
// (openapi-typescript) into src/types/openapi.d.ts; keep hand-written types minimal.
export interface HealthResponse {
  status: "ok";
  version: string;
}
