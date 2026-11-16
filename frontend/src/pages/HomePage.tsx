import { BackendStatus } from "../components/BackendStatus.tsx";

/** Placeholder. Phase 9a replaces it with the "New Investigation" dashboard (SPECS.md §14). */
export function HomePage() {
  return (
    <main>
      <h1>OSINT Framework</h1>
      <p>Public-source digital exposure analysis.</p>
      <BackendStatus />
    </main>
  );
}
