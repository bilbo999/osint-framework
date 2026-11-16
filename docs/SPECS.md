# Desarrollo de un framework OSINT modular de análisis de exposición digital

## 1. Objetivo

Desarrolla una aplicación OSINT completa, modular y extensible cuyo objetivo sea recopilar, normalizar, correlacionar y analizar información pública sobre un objetivo, permitiendo identificar su huella digital y calcular un nivel de exposición.

El sistema debe estar diseñado como un proyecto profesional y mantenible, no como un script monolítico.

Debe permitir investigar, como mínimo:

- Personas.
- Organizaciones.
- Dominios.
- Direcciones IP.
- Direcciones de correo electrónico.
- Nombres de usuario.
- Números de teléfono.
- URLs.
- Infraestructura relacionada.

El sistema debe poder descubrir relaciones entre estos elementos y representar los resultados mediante un grafo.

IMPORTANTE: el framework debe utilizar únicamente información obtenida de fuentes públicas y APIs legítimas. No debe realizar intrusión, explotación de vulnerabilidades, bypass de autenticación, credential stuffing, evasión de controles, acceso a información privada ni ninguna actividad ofensiva.

---

# 2. Stack tecnológico obligatorio

Utiliza:

### Backend
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- asyncio cuando sea apropiado

### Frontend
- React
- TypeScript
- Vite
- Una librería de componentes moderna y accesible

### Bases de datos
- PostgreSQL para datos estructurados
- Neo4j para relaciones y grafos

### Infraestructura
- Docker
- Docker Compose

### Testing
- pytest
- pytest-asyncio
- tests unitarios e integración

### Calidad
- Ruff
- Black
- MyPy

### Gestión
- Git
- `.gitignore`
- `.env` para secretos
- `.env.example` sin secretos reales

No hardcodees API keys, contraseñas ni credenciales.

---

# 3. Arquitectura

Utiliza una arquitectura modular y por capas.

La estructura debe ser aproximadamente:

```text
osint-framework/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── collectors/
│   │   ├── analyzers/
│   │   ├── scoring/
│   │   ├── graph/
│   │   ├── reports/
│   │   └── main.py
│   │
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── App.tsx
│
├── collectors/
├── docs/
├── scripts/
├── docker/
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

La arquitectura debe permitir añadir nuevos collectors sin modificar el núcleo de la aplicación.

---

# 4. Sistema de plugins / collectors

Implementa un sistema de plugins.

Cada fuente OSINT debe ser un módulo independiente.

Define una interfaz abstracta similar a:

```python
class Collector(ABC):

    name: str
    description: str
    supported_targets: list[str]

    async def collect(
        self,
        target: Target
    ) -> list[Finding]:
        ...
```

Cada collector debe declarar:

- Nombre.
- Descripción.
- Tipo de objetivo soportado.
- Fuente.
- Requisitos.
- API key necesaria o no.
- Rate limits.
- Tipo de información obtenida.

Los collectors no deben escribir directamente en la base de datos.

Deben devolver objetos normalizados `Finding`.

Posteriormente una capa independiente se encargará de persistirlos.

---

# 5. Collectors iniciales

Implementa inicialmente collectors seguros y legítimos para:

### Dominio

- DNS.
- WHOIS/RDAP.
- Registros MX.
- Registros NS.
- Registros TXT.
- Registros SPF.
- DMARC.
- Certificados TLS públicos.
- Certificate Transparency.
- Subdominios mediante fuentes públicas autorizadas.

### IP

- Reverse DNS.
- ASN.
- Organización.
- País/ubicación aproximada.
- Información pública de infraestructura.

### Email

- Validación sintáctica.
- Dominio.
- Registros MX.
- Gravatar cuando esté disponible públicamente.
- Fuentes públicas de exposición de credenciales mediante APIs legítimas, sin intentar autenticarse.

### Username

Permite comprobar la existencia pública de un username en servicios que permitan consultas automatizadas legítimas.

No realices login ni scraping que viole controles de acceso o términos del servicio.

### Persona

Permite introducir:

- Nombre.
- Apellidos.
- Username.
- Email.
- Dominio relacionado.

El sistema debe utilizar esos datos únicamente como semillas para pivots sobre fuentes públicas.

### URL

Extrae y analiza:

- Dominio.
- Subdominio.
- IP.
- TLD.
- Tecnologías únicamente cuando puedan obtenerse legítimamente.

---

# 6. Modelo de datos

Define entidades normalizadas.

Como mínimo:

```text
Investigation
Target
Person
Organization
Domain
Subdomain
IPAddress
Email
Username
URL
Certificate
Finding
Source
Evidence
Relationship
Score
Report
```

Cada `Finding` debe contener:

```text
id
type
value
normalized_value
source
source_url
timestamp
confidence
collector
investigation_id
evidence_id
metadata
```

Nunca pierdas la fuente original del dato.

---

# 7. Provenance y evidencias

Todo hallazgo debe ser trazable.

Debe ser posible responder:

- ¿Qué dato se encontró?
- ¿De dónde procede?
- ¿Cuándo se obtuvo?
- ¿Qué collector lo obtuvo?
- ¿Cuál era el valor original?
- ¿Cómo fue normalizado?
- ¿Qué nivel de confianza tiene?
- ¿Qué otros hallazgos lo corroboran?

Implementa un sistema de provenance.

No permitas que un dato obtenido por inferencia se presente como un hecho directamente observado.

Distingue claramente:

```text
OBSERVED
DERIVED
INFERRED
CORRELATED
```

---

# 8. Entity Resolution

Implementa un sistema para detectar cuándo diferentes findings podrían representar la misma entidad.

Ejemplo:

```text
John Smith
john.smith@gmail.com
johnsmith
example.com
```

pueden generar relaciones potenciales, pero el sistema no debe asumir automáticamente que todos pertenecen a la misma persona.

Utiliza:

- coincidencia exacta;
- normalización;
- similitud;
- contexto;
- fuente;
- múltiples evidencias.

Cada relación debe tener:

```text
relationship_type
confidence
evidence
```

---

# 9. Grafo

Utiliza Neo4j.

Los nodos deben representar entidades.

Ejemplo:

```text
Person
 ├── OWNS → Domain
 ├── USES → Username
 ├── HAS_EMAIL → Email
 └── ASSOCIATED_WITH → Organization

Domain
 ├── RESOLVES_TO → IP
 ├── HAS_SUBDOMAIN → Subdomain
 └── HAS_CERTIFICATE → Certificate
```

Implementa:

- creación de nodos;
- creación de relaciones;
- búsqueda de vecinos;
- shortest paths;
- expansión de entidades;
- visualización del grafo;
- filtrado por tipo de entidad;
- filtrado por confianza.

---

# 10. Motor de correlación

Crea un servicio independiente encargado de correlacionar findings.

Debe detectar:

- entidades coincidentes;
- relaciones potenciales;
- duplicados;
- evidencias corroborantes;
- conflictos entre fuentes.

No debe convertir automáticamente una correlación en una afirmación factual.

---

# 11. Exposure Score

Implementa un sistema transparente de puntuación de exposición.

El score debe estar entre:

```text
0 - 100
```

Divide el score en categorías independientes:

```text
Identity Exposure
Contact Exposure
Credential Exposure
Social Exposure
Infrastructure Exposure
Historical Exposure
Correlation Exposure
```

Cada categoría debe tener:

- peso configurable;
- puntuación;
- findings que contribuyen;
- explicación.

Ejemplo:

```text
Exposure Score: 67/100

Identity:       14/20
Contact:        12/15
Credentials:    18/25
Social:          8/15
Infrastructure:  7/10
Historical:      5/10
Correlation:     3/5
```

IMPORTANTE:

El score debe ser explicable.

El usuario debe poder pulsar sobre cualquier componente y ver exactamente qué findings han contribuido a la puntuación.

Todos los pesos deben estar definidos en configuración, no hardcodeados.

---

# 12. Confidence Score

No confundas `Exposure Score` con `Confidence`.

Cada finding debe tener un confidence score independiente.

Por ejemplo:

```text
confidence = 0.0 - 1.0
```

La confianza debe depender de:

- fiabilidad de la fuente;
- calidad de la evidencia;
- coincidencia de entidades;
- corroboración;
- antigüedad del dato.

Nunca utilices confidence como sustituto del Exposure Score.

---

# 13. Sistema de investigaciones

El usuario debe poder crear:

```text
Investigation
```

Una investigación debe contener:

- nombre;
- descripción;
- objetivos;
- findings;
- entidades;
- relaciones;
- evidencias;
- timeline;
- score;
- informes.

Debe ser posible:

- crear;
- duplicar;
- abrir;
- cerrar;
- exportar;
- eliminar investigaciones.

---

# 14. Interfaz gráfica

La interfaz debe estar pensada para usuarios técnicos y no técnicos.

Dashboard principal:

```text
┌─────────────────────────────────────────┐
│ OSINT Framework                         │
├─────────────────────────────────────────┤
│ New Investigation                       │
│                                         │
│ Target: ____________________            │
│ Type: [Domain ▼]                        │
│                                         │
│              [ START ]                  │
└─────────────────────────────────────────┘
```

Después de iniciar una investigación mostrar:

### Resumen

- Target.
- Exposure Score.
- Confidence.
- Número de findings.
- Número de entidades.
- Número de relaciones.
- Fuentes consultadas.

### Findings

Tabla con:

```text
Type
Value
Source
Confidence
Timestamp
Severity
```

### Graph

Grafo interactivo.

### Timeline

Orden cronológico de los hallazgos.

### Evidence

Fuentes y evidencias.

### Exposure

Desglose del score.

### Reports

Generación de informes.

---

# 15. Modo usuario no técnico

Debe existir un flujo simplificado:

```text
1. Introducir objetivo
2. Seleccionar tipo
3. Ejecutar investigación
4. Esperar resultados
5. Mostrar resumen
6. Mostrar exposición
7. Mostrar principales hallazgos
8. Permitir profundizar
```

No obligues al usuario a conocer:

- APIs;
- HTTP;
- DNS;
- JSON;
- CLI;
- bases de datos.

El sistema debe esconder la complejidad cuando sea posible.

---

# 16. Modo avanzado

Los usuarios técnicos deben poder:

- activar/desactivar collectors;
- configurar API keys;
- establecer timeouts;
- establecer rate limits;
- seleccionar fuentes;
- ejecutar collectors individualmente;
- consultar logs;
- exportar JSON;
- utilizar CLI;
- utilizar API REST.

---

# 17. API REST

Implementa endpoints claramente versionados:

```text
/api/v1/investigations
/api/v1/targets
/api/v1/findings
/api/v1/entities
/api/v1/relationships
/api/v1/graph
/api/v1/scores
/api/v1/reports
/api/v1/collectors
```

Documenta automáticamente la API mediante OpenAPI/Swagger.

---

# 18. CLI

Implementa una CLI mediante Typer.

Ejemplos:

```bash
osint investigation create
osint target add
osint scan
osint collectors list
osint findings list
osint graph export
osint report generate
```

La CLI debe utilizar la misma API y servicios que la interfaz web.

No dupliques lógica.

---

# 19. Informes

Permite generar informes:

- HTML.
- JSON.
- CSV.
- PDF.

El informe debe incluir:

1. Información de la investigación.
2. Objetivos.
3. Metodología.
4. Fuentes consultadas.
5. Findings.
6. Entidades.
7. Relaciones.
8. Evidencias.
9. Exposure Score.
10. Confidence.
11. Timeline.
12. Limitaciones.
13. Timestamp de recopilación.

Distingue claramente entre hechos observados e inferencias.

---

# 20. Seguridad y privacidad

Implementa:

- autenticación;
- autorización;
- gestión de sesiones;
- almacenamiento seguro de credenciales;
- variables de entorno;
- validación de inputs;
- rate limiting;
- logs de auditoría.

Nunca almacenes API keys en el código.

No registres secretos en logs.

Añade mecanismos para eliminar completamente una investigación y sus evidencias.

---

# 21. Rate limiting y resiliencia

Cada collector debe implementar:

- timeout;
- retry limitado;
- exponential backoff;
- rate limiting;
- manejo de errores;
- circuit breaker cuando sea apropiado.

Un fallo de un collector nunca debe detener toda la investigación.

Ejemplo:

```text
Collector A → SUCCESS
Collector B → SUCCESS
Collector C → TIMEOUT
Collector D → SUCCESS

Investigation → COMPLETED_WITH_WARNINGS
```

---

# 22. Ejecución asíncrona

Las investigaciones pueden contener muchos collectors.

No ejecutes todos secuencialmente.

Utiliza tareas asíncronas y/o workers para ejecutar collectors independientes en paralelo respetando sus respectivos rate limits.

El frontend debe mostrar progreso:

```text
Investigation: running

DNS                 ✓
WHOIS               ✓
Certificates        ✓
Subdomains          ███████░░░
Username checks     ███░░░░░░░
Breach intelligence ○
```

---

# 23. Logging

Implementa logging estructurado.

Cada ejecución debe permitir conocer:

```text
timestamp
investigation_id
collector
target
status
duration
number_of_findings
error
```

No almacenar información sensible innecesaria.

---

# 24. Configuración

Toda configuración no sensible debe estar centralizada.

Por ejemplo:

```text
config/
 ├── collectors.yaml
 ├── scoring.yaml
 └── settings.yaml
```

El sistema de scoring debe poder modificarse sin cambiar código.

---

# 25. Testing

Incluye:

### Unit tests

Para:

- collectors;
- normalizadores;
- entity resolution;
- scoring;
- provenance;
- API;
- modelos.

### Integration tests

Para:

- PostgreSQL;
- Neo4j;
- API;
- pipeline completo.

### End-to-end

Debe existir al menos un escenario:

```text
Create investigation
       ↓
Add target
       ↓
Run collectors
       ↓
Generate findings
       ↓
Correlate
       ↓
Calculate score
       ↓
Generate report
```

Los tests no deben depender de APIs externas reales.

Utiliza mocks/fixtures.

---

# 26. Datos de demostración

Incluye un modo demo completamente offline.

Debe ser posible ejecutar:

```bash
docker compose up
```

y posteriormente cargar datos ficticios.

Los datos de demo deben estar claramente marcados como:

```text
DEMO / SYNTHETIC DATA
```

No utilices datos personales reales.

---

# 27. Docker

Crea:

```text
docker-compose.yml
```

con servicios como:

```text
frontend
backend
postgres
neo4j
redis
```

Debe existir un único comando para iniciar el entorno:

```bash
docker compose up --build
```

Documenta los puertos y credenciales de desarrollo.

Utiliza credenciales de desarrollo únicamente para el entorno local y deja claro que deben cambiarse en producción.

---

# 28. Documentación

Crea un README completo que explique:

- propósito;
- arquitectura;
- instalación;
- configuración;
- ejecución;
- Docker;
- collectors;
- API;
- CLI;
- scoring;
- Neo4j;
- PostgreSQL;
- desarrollo de nuevos plugins;
- testing;
- seguridad;
- limitaciones.

Añade también:

```text
docs/
├── architecture.md
├── collectors.md
├── scoring.md
├── api.md
├── development.md
└── security.md
```

---

# 29. Desarrollo de nuevos collectors

La documentación debe explicar cómo crear un nuevo collector.

Idealmente añadir una fuente nueva debería requerir únicamente:

```text
1. Crear collector
2. Implementar interfaz
3. Registrar collector
4. Añadir tests
```

No debería ser necesario modificar el núcleo.

---

# 30. Observabilidad

Incluye métricas básicas:

- investigaciones ejecutadas;
- duración;
- collectors ejecutados;
- éxito/error;
- número de findings;
- número de fuentes;
- número de entidades.

---

# 31. Diseño del sistema

Prioriza:

1. Modularidad.
2. Extensibilidad.
3. Trazabilidad.
4. Reproducibilidad.
5. Seguridad.
6. Explicabilidad.
7. Usabilidad.
8. Rendimiento.

No sacrifiques trazabilidad por velocidad.

No sacrifiques seguridad por facilidad de uso.

---

# 32. Principios de OSINT

El framework debe diferenciar entre:

```text
Raw data
↓
Normalized data
↓
Finding
↓
Entity
↓
Relationship
↓
Inference
↓
Risk/Exposure
```

Nunca presentes una inferencia como si fuera un dato directamente obtenido de una fuente.

Cada conclusión debe poder remontarse a sus evidencias.

---

# 33. Limitaciones y ética

Incluye en la documentación una sección específica indicando que el framework está destinado a:

- investigación OSINT;
- threat intelligence;
- análisis de exposición;
- auditorías autorizadas;
- investigación académica;
- análisis de activos propios o autorizados.

No implementar:

- explotación de vulnerabilidades;
- robo de credenciales;
- bypass de autenticación;
- credential stuffing;
- malware;
- persistencia;
- evasión de detección;
- acceso a sistemas privados;
- doxxing;
- recopilación deliberada de información privada no pública.

---

# 34. Criterios de aceptación

El proyecto se considerará terminado cuando:

- pueda ejecutarse mediante Docker;
- tenga frontend y backend funcionales;
- permita crear investigaciones;
- permita introducir diferentes tipos de objetivos;
- disponga de sistema de collectors;
- ejecute múltiples collectors;
- normalice resultados;
- almacene findings;
- conserve provenance;
- genere entidades;
- genere relaciones;
- almacene el grafo en Neo4j;
- visualice el grafo;
- calcule Exposure Score;
- explique el Exposure Score;
- calcule Confidence;
- permita consultar evidencias;
- genere informes;
- disponga de API REST;
- disponga de CLI;
- tenga tests;
- tenga documentación;
- tenga datos sintéticos de demostración;
- no dependa de credenciales reales para funcionar en modo demo.

---

# 35. Forma de trabajar

No generes todo el proyecto como un único archivo.

Construye el proyecto incrementalmente.

Orden obligatorio:

### Fase 1
Arquitectura y estructura del repositorio.

### Fase 2
Backend + modelos + PostgreSQL.

### Fase 3
Sistema de collectors/plugins.

### Fase 4
Collectors iniciales.

### Fase 5
Entity resolution + correlación.

### Fase 6
Neo4j + grafo.

### Fase 7
Exposure Score + Confidence.

### Fase 8
API completa.

### Fase 9
Frontend.

### Fase 10
CLI.

### Fase 11
Reports.

### Fase 12
Testing.

### Fase 13
Docker + documentación.

Después de cada fase:

1. Ejecuta los tests.
2. Comprueba que el proyecto sigue arrancando.
3. Corrige errores.
4. No continúes si la fase anterior está rota.

No inventes APIs externas ni credenciales.

Cuando una fuente externa requiera una API key, implementa el adaptador y proporciona un mock/demo para que el sistema siga funcionando sin ella.

Prioriza siempre código funcional sobre código de demostración.

El resultado final debe ser un framework OSINT modular, extensible y reproducible que pueda utilizarse tanto mediante interfaz gráfica como mediante API/CLI, y que combine recopilación, correlación, grafo, evidencias, scoring de exposición y generación de informes en una única plataforma.