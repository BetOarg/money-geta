# Composer de preview de timeline

## Estado de esta etapa
Composer local de preview MP4 para borradores. Requiere FFmpeg instalado y accesible por PATH.

- Compone imágenes y videos locales en segmentos normalizados (1080x1920, 30 fps por defecto).
- Aplica subtítulos SRT por escena cuando el texto y el intervalo son válidos.
- Une segmentos por cortes con concat demuxer.
- El output debe ser nuevo: no sobrescribe previews existentes.
- Rechaza entradas remotas, medios ausentes, symlinks y transiciones distintas de corte (aún no renderizadas).

## Uso desde Python
```python
from pathlib import Path
from scripts.timeline_composer import compose_preview

compose_preview(timeline_draft, Path("preview.mp4"))
```

No habilita ni inicia render final, publicación o programación. El composer no mezcla pistas de audio ni aplica transiciones visuales; esos componentes quedan para etapas posteriores.
