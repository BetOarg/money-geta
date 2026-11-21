# Editor de timeline local (MVP)

El editor inicial de timeline trabaja sobre un plan visual de escenas generado desde un guion aprobado.

## Alcance

- Convierte el plan visual en una secuencia editable, sin modificar el guion original.
- Cada escena conserva su ID de timeline, referencia de escena, descripción visual, recurso local aprobado, narración, texto de subtítulo y duración.
- Permite ordenar escenas y ajustar duración, narración y subtítulos.
- Guarda el borrador JSON de forma atómica en la carpeta de la campaña.
- Mantiene el estado `draft`; no autoriza render, publicación ni programación.

## Límites de esta etapa

- No es todavía un reproductor de timeline ni un editor audiovisual con preview en tiempo real.
- No corta ni mezcla clips, no sincroniza audio externo ni aplica transiciones.
- El render se mantiene separado y requiere los gates actuales de QC y aprobación humana.
- La duración inicial por escena es 5 segundos y puede editarse entre 0.25 y 180 segundos.

## Persistencia

El archivo se guarda en `<projects>/<project_id>/campaigns/<campaign_id>/timelines/` con nombre basado en el script ID y su SHA-256. No se reemplaza el guion ni se da permiso automático de render/publicación.
