# Recorte de clips de video en timeline

La etapa agrega metadatos de entrada/salida por escena:
- Entrada en segundos (≥ 0).
- Salida opcional, debe ser mayor que entrada.
- Los controles se aplican solo a recursos locales identificados como video.
- Un valor de salida vacío representa el final sin límite explícito.
- La preview busca un fotograma en el punto de entrada configurado.

No calcula la duración real del video ni aplica el recorte al render: el recorte queda como borrador local y aún requiere integración con el renderizador, validación de duración de fuente y aprobación humana.
