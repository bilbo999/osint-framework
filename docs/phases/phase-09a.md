# Fase 9a: Frontend base — shell, auth, flujo simple, progreso, resumen y findings

## Objetivo
Construir la base del frontend y el flujo para usuarios no técnicos (SPECS.md §14–15): login,
dashboard "New Investigation" (objetivo + tipo + START), progreso por collector, resumen
(target, Exposure Score, confidence, nº findings/entidades/relaciones, fuentes) y tabla de findings.

## Dependencias (fases previas y contratos que usa)
- Fase 8: endpoints `/auth/*`, `/investigations*`, `/targets`, `/findings`, `/scores`, `/collectors`,
  OpenAPI en `/api/v1/openapi.json`, CSRF por cabecera `X-CSRF-Token`, `Problem` (RFC 9457).
- Fase 1: `frontend/` mínimo (Vite 8, React 19, TypeScript 7) con proxy `/api`.

## Archivos a crear o modificar (rutas exactas)
- `frontend/package.json`: añadir `@mantine/core @mantine/hooks @mantine/notifications @mantine/form`,
  `@tanstack/react-query`, `react-router`, `@tabler/icons-react`; dev: `openapi-typescript`, `vitest`,
  `@testing-library/react`, `@testing-library/user-event`, `jsdom`, `msw`, `eslint` + `typescript-eslint`,
  `postcss-preset-mantine`. Scripts `test`, `lint`, `gen:api`.
- `frontend/postcss.config.cjs`, `frontend/eslint.config.js`, `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`.
- `frontend/src/types/openapi.d.ts` (generado con `npm run gen:api`; commitear el generado).
- `frontend/src/services/{http.ts,auth.ts,investigations.ts,findings.ts,scores.ts,collectors.ts}`.
- `frontend/src/hooks/{useAuth.ts,useInvestigation.ts,useProgress.ts,useFindings.ts}`.
- `frontend/src/components/{AppLayout.tsx,DemoBanner.tsx,ProvenanceBadge.tsx,SeverityBadge.tsx,
  ConfidenceMeter.tsx,ScoreGauge.tsx,CollectorProgressList.tsx,FindingsTable.tsx,ErrorState.tsx,EmptyState.tsx}`.
- `frontend/src/pages/{LoginPage.tsx,DashboardPage.tsx,InvestigationListPage.tsx,InvestigationPage.tsx,
  SummaryTab.tsx,FindingsTab.tsx}`; `frontend/src/App.tsx` (router + providers), `frontend/src/main.tsx`.
- Tests: `frontend/src/**/*.test.tsx`, mocks MSW en `frontend/src/test/handlers.ts`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-009: Mantine v8, TanStack Query, React Router, tipos generados desde OpenAPI.
- Progreso por *polling* cada `progress_poll_interval_seconds` (2 s) mientras el estado sea `queued|running`.
- Un único cliente HTTP (`services/http.ts`): `credentials: "same-origin"`, añade `X-CSRF-Token` en métodos
  no seguros, convierte `Problem` en `ApiError` tipado; ningún componente llama a `fetch` directamente.
- Lenguaje llano en modo simple: "¿Qué quieres analizar?", sin jerga (DNS, JSON, API) en la vista simple.
- `ProvenanceBadge`: OBSERVED "Observado", DERIVED "Derivado", INFERRED/CORRELATED "Inferencia" (color distinto).
- `DemoBanner` visible y fijo si `is_synthetic` en la investigación o la API indica modo demo.

## Interfaces y firmas clave (código)
```ts
// services/http.ts
export class ApiError extends Error { status: number; problem: Problem }
export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T>;

// hooks/useProgress.ts
export function useProgress(investigationId: string): {
  status: InvestigationStatus; collectors: CollectorProgress[]; isRunning: boolean;
};

// components/FindingsTable.tsx — columnas SPECS.md §14: Type, Value, Source, Confidence, Timestamp, Severity (+ Provenance)
export interface FindingsTableProps {
  investigationId: string;
  initialFilters?: { type?: FindingType[]; minConfidence?: number; provenance?: ProvenanceKind[] };
  onSelect?: (findingId: string) => void;
}

// pages/DashboardPage.tsx — flujo simple
// 1 objetivo → 2 tipo (autodetectado y editable) → 3 START → navegar a /investigations/:id (progreso + resumen)
export function detectTargetType(value: string): TargetType | null;
```
Rutas: `/login`, `/` (dashboard), `/investigations`, `/investigations/:id/(summary|findings)`; las de 9b
(`graph|timeline|evidence|exposure|reports`, `/settings/collectors`) se registran vacías aquí.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- `detectTargetType`: dominio, IP v4/v6, email, URL, teléfono, username, nombre de persona.
- `http.ts`: añade CSRF en POST/PATCH/DELETE y no en GET; mapea 401 ⇒ redirección a login; `Problem` ⇒ `ApiError`.
- Dashboard (MSW): crear investigación + target + scan; muestra validación de input vacío/inválido.
- Progreso: estados ✓/barra/○ por collector; deja de hacer polling al terminar; `COMPLETED_WITH_WARNINGS`
  muestra aviso con los collectors fallidos sin bloquear resultados.
- Resumen: muestra score, confidence media, conteos y fuentes; `DemoBanner` si `is_synthetic`.
- FindingsTable: ordenar, filtrar por tipo/confianza/provenance, paginación servidor; badge "Inferencia".
- Accesibilidad: tablas con cabeceras, formularios con `label`, foco visible (`@testing-library` por rol).

## Criterios de aceptación verificables (comandos concretos)
```bash
cd frontend
npm ci
npm run gen:api            # requiere backend en :8000; el fichero generado se commitea
npm run lint && npm run typecheck && npm test -- --run && npm run build
# manual: cd backend && uv run uvicorn app.main:app ; cd frontend && npm run dev → http://localhost:5173
```

## Fuera de alcance
Grafo, timeline, evidencias, desglose de exposición, informes y modo avanzado (Fase 9b).
i18n completo (textos en inglés en código, centralizados en `src/i18n/en.ts` para traducir después).

## Riesgos y trampas conocidas
- Mantine v8 requiere `postcss-preset-mantine` e importar `@mantine/core/styles.css`.
- TypeScript 7 / Vite 8 son recientes: si una dependencia no declara compatibilidad, fijar versión y anotarlo.
- No guardar tokens en `localStorage` (sesión por cookie HttpOnly; el frontend no ve el token).
- Mostrar `value` de findings siempre como texto (React escapa); nunca `dangerouslySetInnerHTML`.
- Polling: cancelar en `unmount` y al cambiar de investigación (TanStack Query `refetchInterval` condicional).
