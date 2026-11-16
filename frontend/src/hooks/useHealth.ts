import { useEffect, useState } from "react";
import { getHealth } from "../services/api.ts";
import type { HealthResponse } from "../types/api.ts";

export type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((data) => setState({ kind: "ok", data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ kind: "error", message: String(error) });
      });
    return () => controller.abort();
  }, []);
  return state;
}
