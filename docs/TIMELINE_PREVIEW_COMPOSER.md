# Composer de preview de timeline

## Estado de esta etapa
Composer local de preview MP4 para borradores. Requiere FFmpeg instalado y accesible por PATH.

- Compone imágenes y videos locales en segmentos normalizados (1080x1920, 30 fps por defecto).
- Aplica subtítulos SRT por escena.
- Video trim; clips cortos se completan congelando el último fotograma.
- Une escenas consecutivas con corte y grupos con transición usando FFmpeg xfade (fade, dissolve, slide).
- Mezcla audio local: volumen, fades de entrada/salida y retraso.
- El output debe ser nuevo: no sobrescribe previews existentes.
- Rechaza medios ausentes, symlinks, transiciones inválidas y timelines autorizados para render/publicación.

## Uso desde Python
```python
from pathlib import Path
from scripts.timeline_composer import compose_preview

compose_preview(timeline_draft, Path("preview.mp4"))
```

La preview es una salida local de revisión. No autoriza ni inicia render final, publicación o programación. CI valida la construcción de comandos; la revisión audiovisual real requiere FFmpeg y material local en Windows.
