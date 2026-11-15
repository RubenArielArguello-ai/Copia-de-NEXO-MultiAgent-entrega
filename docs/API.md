# API de NEXO

Base URL local: `http://127.0.0.1:8000`. Si `NEXO_API_TOKEN` está configurado, incluir `Authorization: Bearer <token>` en las solicitudes API. En `NEXO_ENV=production`, la API no arranca solicitudes sin un token configurado. CORS se limita a `NEXO_CORS_ORIGINS`; el backend restringe los cuerpos a 16 KiB y aplica límites por IP. FastAPI publica OpenAPI interactivo en `/docs`.

Todos los errores siguen el formato FastAPI `{"detail":"..."}`. Los campos Pydantic inválidos devuelven HTTP 422; falta de sesión HTTP 404; token faltante/inválido 401; token de producción no configurado 503; solicitudes excesivas 413 y rate limit 429.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `GET /health` | — | `status`, cantidad de sesiones en memoria. |
| `POST /sessions` | JSON `{"request":"..."}`; 1–10.000 caracteres | `session_id`, estado inicial y ruta de polling. Inicia misión en background. |
| `GET /sessions` | — | Sesiones vivas e historial durable reciente. |
| `GET /sessions/{id}` | ID de misión | Estado, plan, Skills/permisos, resultados, Harness, evaluación, métricas y errores. |
| `GET /sessions/{id}/messages` | `limit` opcional | Mensajes de agentes con payloads y evidencias. |
| `GET /sessions/{id}/tools` | — | Ejecuciones de herramientas persistidas. |
| `GET /sessions/{id}/coherence` | — | Eventos del monitor de coherencia. |
| `GET /agents/status` | `session_id` opcional | Estado/modelo/proveedor observable de Orchestrator y especialistas. |
| `GET /skills` | — | Skills registradas, permisos, agentes, dependencias e I/O. |
| `GET /tools` | — | Herramientas registradas y sus contratos. |
| `GET /models` | — | Conectividad Ollama y disponibilidad de modelos configurados. |
| `GET /dashboard/metrics` | — | Agregados calculados desde SQLite. |
| `GET /dashboard/logs` | `limit` opcional | Mensajes y errores recientes. |
| `POST /start_mission` | query `mission` | Alias heredado que crea una sesión. |

`GET /models` verifica tags mediante Ollama; no descarga modelos. `MockProvider` no se selecciona automáticamente. `/start_mission` se mantiene por compatibilidad. Los endpoints de solo lectura también requieren bearer token si se configuró uno. La página raíz y recursos estáticos son públicos; no contienen credenciales.
