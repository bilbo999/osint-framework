# Fase 9b: Frontend avanzado — grafo, timeline, evidencias, exposición, informes y modo avanzado

## Objetivo
Completar las vistas de SPECS.md §14 y §16: grafo interactivo (filtros por tipo y confianza,
expansión, camino más corto), timeline cronológica, evidencias y provenance, desglose del Exposure
Score clicable hasta los findings, informes y modo avanzado (collectors, API keys, timeouts, rate
limits, ejecución individual, logs de ejecución, export JSON).

## Dependencias (fases previas y contratos que usa)
- Fase 9a: `AppLayout`, `services/http.ts`, hooks, `ProvenanceBadge`, `FindingsTable`, rutas registradas.
- Fase 8: `/graph/*`, `/scores/*`, `/evidence/{id}`, `/findings/{id}`, `/reports*`, `/collectors*`,
  `/collectors/runs`, `/investigations/{id}/export`.
- Fase 11 (para generar/descargar informes reales; mientras tanto la UI maneja el 501).

## Archivos a crear o modificar (rutas exactas)
- `frontend/package.json`: `cytoscape`, `react-cytoscapejs`, `cytoscape-fcose` (+ tipos `@types/cytoscape`).
- `frontend/src/components/graph/{GraphView.tsx,GraphFilters.tsx,GraphLegend.tsx,NodeDetails.tsx,graphStyle.ts}`.
- `frontend/src/components/{Timeline.tsx,EvidenceViewer.tsx,ProvenanceTrail.tsx,ExposureBreakdown.tsx,
  ContributionsDrawer.tsx,ReportGenerator.tsx}`.
- `frontend/src/pages/{GraphTab.tsx,TimelineTab.tsx,EvidenceTab.tsx,ExposureTab.tsx,ReportsTab.tsx,
  CollectorsSettingsPage.tsx,CollectorRunsPage.tsx}`.
- `frontend/src/services/{graph.ts,evidence.ts,reports.ts}`; ampliar `collectors.ts`, `scores.ts`.
- `frontend/src/hooks/{useGraph.ts,useExposure.ts,useMode.ts}` (modo simple/avanzado persistido en `localStorage`).
- Tests: `frontend/src/**/*.test.tsx` correspondientes.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-009: Cytoscape.js con layout `fcose`; el backend entrega `elements` en formato Cytoscape (Fase 6).
- ADR-008: el desglose viene de `/scores/{id}`; cada categoría abre `ContributionsDrawer` con sus
  contribuciones (regla, explicación, puntos, finding enlazado). Si `capped`, mostrar "limitado a N".
- §A.1: aristas INFERRED/CORRELATED con línea discontinua y etiqueta "posible"; nunca igual que OBSERVED.
- La vista de evidencia muestra `content` como texto preformateado (JSON con indentación), nunca HTML.
- Modo avanzado oculto por defecto; un interruptor en la cabecera lo activa (preferencia local, no seguridad).
- Las acciones de admin se ocultan si `me.role !== "admin"`, pero la autorización real es del backend.

## Interfaces y firmas clave (código)
```ts
export interface GraphViewProps {
  investigationId: string;
  filters: { types: EntityType[]; minConfidence: number };
  onNodeSelect?: (entityId: string) => void;
}
export function useGraph(investigationId: string, filters: GraphFilters): UseQueryResult<CytoscapeGraph>;
export async function expandNode(investigationId: string, entityId: string, depth?: number): Promise<CytoscapeGraph>;
export async function shortestPath(investigationId: string, from: string, to: string): Promise<CytoscapeGraph | null>;

export interface ExposureBreakdownProps { score: ExposureScore; onCategoryClick: (category: string) => void }
export interface TimelineItem { timestamp: string; findingId: string; type: FindingType; value: string;
                                source: string; provenance: ProvenanceKind }
```
Timeline: findings ordenados por `timestamp` + hitos de certificados/registro (`not_before`, `created`)
marcados como "fecha en la fuente" frente a "fecha de obtención".

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- `graphStyle`: un estilo por `EntityType`; aristas no-OBSERVED discontinuas.
- `GraphView` (Cytoscape mockeado o `headless: true`): aplica filtros (min confianza, tipos), expande nodo
  fusionando elementos sin duplicados, muestra aviso si `truncated`.
- `ExposureBreakdown`: 7 categorías con `score/max_points`; clic ⇒ drawer con contribuciones y enlaces a findings.
- `EvidenceViewer`: muestra sha256, fuente, fecha, `request_summary`; contenido con `<script>` se ve como texto.
- `ProvenanceTrail`: finding INFERRED muestra la cadena `derived_from` hasta las evidencias.
- Collectors settings (MSW): activar/desactivar, editar timeout/rate limit (validación), API key enmascarada
  (`••••1234`), nunca se rellena el campo con la clave existente; ejecutar un collector individual.
- Reports: elegir formato, generar, descargar; maneja 501 con mensaje claro.
- Export JSON: descarga `GET /investigations/{id}/export` con nombre `investigation-<id>.json`.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd frontend
npm run lint && npm run typecheck && npm test -- --run && npm run build
# manual con demo (Fase 12) o datos locales: grafo filtrable, clic en categoría ⇒ findings contribuyentes
```

## Fuera de alcance
Edición manual de entidades/relaciones, colaboración en tiempo real, grafos de más de
`settings.graph.max_nodes_returned` nodos (se muestra aviso de truncado).

## Riesgos y trampas conocidas
- `react-cytoscapejs` no está mantenido activamente: si falla con React 19, envolver `cytoscape` directamente
  en un componente propio con `useRef` + `useEffect` (misma interfaz `GraphViewProps`).
- Rendimiento: no re-crear la instancia de Cytoscape en cada render; actualizar `elements` con `cy.json()`.
- jsdom no tiene canvas: mockear Cytoscape en tests unitarios.
- No mostrar valores de API keys ni en el DOM ni en mensajes de error.
