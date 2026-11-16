import { useHealth } from "../hooks/useHealth.ts";

export function BackendStatus() {
  const health = useHealth();
  switch (health.kind) {
    case "loading":
      return <p role="status">Checking backend…</p>;
    case "ok":
      return <p role="status">Backend online (v{health.data.version})</p>;
    case "error":
      return <p role="alert">Backend unreachable</p>;
  }
}
