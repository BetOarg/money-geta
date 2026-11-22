# Preview de escena en timeline

El editor de timeline muestra una vista previa del recurso local de la escena seleccionada:
- Imágenes: miniatura con Pillow, si está instalado.
- Videos: fotograma inicial extraído mediante FFmpeg, si está disponible.
- Si falta Pillow/FFmpeg, el recurso no existe o el formato no es compatible, se informa sin detener el editor.

La vista previa trabaja con rutas locales ya asignadas; no descarga ni solicita recursos. La función resolver rechaza enlaces simbólicos. La extracción de video tiene un timeout y no autoriza render, publicación o distribución.
