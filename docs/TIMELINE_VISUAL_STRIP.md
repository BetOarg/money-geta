# Editor de timeline local

## Alcance del MVP
El editor de timeline parte del plan visual de escenas derivado de un guion aprobado. La interfaz de escritorio permite:
- Abrir un timeline de borrador, o cargar uno guardado para el mismo ID y hash de guion.
- Reordenar escenas (subir/bajar).
- Editar duración (0,25–180 segundos), narración y texto de subtítulos por escena.
- Guardar de forma atómica en la carpeta de campaña local.

Cada escena mantiene descripción visual y recurso local aprobado seleccionado en el plan visual. El timeline está vinculado al ID y SHA-256 del guion; los cambios no alteran el guion aprobado.

## Persistencia
`<projects>/<project_id>/campaigns/<campaign_id>/timelines/timeline_<script_id>_<sha12>.json`

## Gates
Los borradores tienen `status=draft`, `render_authorized=false` y `publishing_authorized=false`. Guardar o editar no inicia un render ni publica/programa contenido.

## Fuera de alcance
- Preview/playback audiovisual real.
- Recorte/mezcla de clips, pistas de audio, transiciones o sincronización de voz automática.
- Exportación a MPT; eso requiere un adaptador explícito y validación de QC en una etapa posterior.

## Vista visual (siguiente increment)

El editor ahora incorpora una franja horizontal desplazable de bloques de escenas. El ancho de cada bloque representa proporcionalmente su duración (con un mínimo visual para escenas cortas), muestra número, descripción y duración. Al seleccionar un bloque se sincroniza la selección con la tabla y el editor de escena. La franja es un resumen visual, no un preview de video ni una representación de frames.
