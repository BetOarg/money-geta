# Contratos de conectores

## Interfaz conceptual común
Cada conector declara `id`, `version`, `capabilities`, `required_config`, `cost_model`, `rate_limits` y `health_check`. Las operaciones deben ser idempotentes cuando sea posible y devolver un resultado estructurado con estado, artefacto/referencia, fecha, identificador externo y uso/coste cuando aplique.

Nunca incluir credenciales en argumentos de línea de comandos, manifests, logs, excepciones o resultados. Cargar secretos desde almacén local/variables de entorno y redactarlos.

## Buffer distribution adapter
Responsabilidad: listar destinos/canales conectados, validar que un medio/copy/formato sea compatible, crear borrador o elemento programado solo tras aprobación, recuperar URL/estado y métricas que el plan/API permita.

Operaciones previstas:
- `health_check()`
- `list_destinations()`
- `validate_post(destination, media, copy, schedule)`
- `create_draft(approved_artifact)`
- `schedule(approved_artifact, approved_schedule)`
- `get_post_status(external_id)`
- `get_analytics(external_id, date_range)`

Reglas: no asumir que un canal acepta cualquier duración, códec, ratio o tipo de post; consultar capacidades. El adaptador no decide derechos ni aprueba contenido. En primera versión, crear borrador es el comportamiento predeterminado; programar requiere aprobación específica.

## X Research adapter (X API)
Responsabilidad: buscar posts/conversaciones y recuperar datos públicos permitidos por el producto contratado. No confundir investigación con distribución.

Operaciones previstas:
- `search_posts(query, time_range, max_results)`
- `get_post(post_id)`
- `get_public_metrics(post_ids)`

Guardrails: límite configurable por campaña y por día; presupuesto máximo; caché por consulta; deduplicación; paginación acotada; retención mínima necesaria; registro de endpoint, fecha, resultados y coste estimado/real. Si no se conoce el precio/uso aplicable, la operación queda deshabilitada. No hacer scraping para evadir límites, autenticación o políticas.

## X Publishing adapter
Primera etapa: Buffer cuando el canal y el formato estén disponibles para la cuenta. Fase posterior: X API directa, solo tras validar documentación oficial y autorización de coste/permisos.

Operaciones previstas: validar copy/medios, crear borrador, publicar, consultar estado y métricas. Toda operación de escritura requiere un token de aprobación humano ligado a campaña, plataforma, contenido y hash de medios. No hay autopublicación.

## Proveedor de IA
Contrato desacoplado para `research`, `draft_script`, `rewrite`, `translate` y, si el proveedor lo soporta, `generate_image`. Diferenciar ChatGPT web/suscripción de OpenAI API: una cuenta ChatGPT gratuita no aporta por sí misma créditos ni una API key. Gemini u otros proveedores pueden configurarse por separado. Los proveedores no reciben medios privados salvo configuración explícita y consentimiento.

## Adaptador MPT
Money-Geta construye una solicitud de render validada y llama el CLI fijado. El adaptador comprueba versión/flags, archivos de entrada, campaña y resultado MP4. Debe mantener deshabilitada la publicación automática de MPT. La lógica de perfil, QC, derechos y aprobación vive en Money-Geta, no en MPT.

## Estados de error
- `UNAVAILABLE`: conector o endpoint no disponible.
- `UNAUTHORIZED`: falta permiso/token.
- `RATE_LIMITED`: cuota agotada; respetar retry-after.
- `COST_LIMIT_REACHED`: presupuesto agotado; no reintentar automáticamente.
- `INVALID_MEDIA`: formato no admitido.
- `APPROVAL_REQUIRED`: falta aprobación humana.
- `INCOMPLETE_EVIDENCE`: faltan fuentes/derechos/metadatos.
- `REMOTE_FAILURE`: proveedor rechazó la operación; preservar el artefacto local.
