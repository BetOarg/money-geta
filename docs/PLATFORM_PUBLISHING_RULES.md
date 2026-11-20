# Reglas de publicación por plataforma — referencia verificada

Fecha de consulta: 20-11-2026. Estos valores son límites documentados por Buffer para su flujo de publicación, no promesas de que cualquier cuenta/canal tenga todas las funciones habilitadas. El adaptador debe consultar el canal y validar el archivo real antes de crear un post.

## Buffer API
- API GraphQL oficial en `https://api.buffer.com`.
- Permite consultar organizaciones/canales, crear y recuperar posts, guardar borradores, programar y consultar métricas disponibles.
- Los canales disponibles incluyen Instagram, X/Twitter, YouTube y TikTok, entre otros.
- La API key opera sobre la cuenta y puede acceder a todas las organizaciones de esa cuenta; no existe actualmente aislamiento por organización. Mantenerla solo en el entorno local, nunca en GUI web, repositorio o logs.
- Para evitar publicaciones accidentales, usar `saveToDraft`/modo borrador como valor inicial. Programar o publicar requiere aprobación humana ligada al contenido y al archivo final.

## X/Twitter a través de Buffer
- Video: MP4, MOV, AVI o M4V.
- Duración publicada por Buffer para herramientas de terceros: 0,5–140 segundos. Los videos más largos asociados a X Premium solo aplican a publicación nativa directa en X, no a terceros como Buffer.
- El límite de FPS documentado por Buffer es 60; las cargas de mayor FPS se convierten.
- Buffer documenta un límite de carga de hasta 1 GB en su flujo, mientras que su guía de X indica un límite de plataforma de 512 MB. Aplicar el límite más restrictivo de 512 MB para validación conservadora y revisar el error real del canal.
- X no reproduce automáticamente el video en timeline/perfil según la guía de Buffer; el usuario debe iniciar reproducción.
- Money-Geta debe generar una versión específica para X, no reutilizar automáticamente un video largo.

## TikTok a través de Buffer
- Video entre 3 segundos y 10 minutos.
- MP4, MOV, WEBM o MV4; hasta 1 GB.
- Resolución mínima de 360 px en alto y ancho; 23–60 FPS.
- Buffer documenta límite de descripción de 150 caracteres.

## YouTube Shorts a través de Buffer
- Video de hasta 3 minutos.
- Formatos indicados: MOV, MP4, MPG, MPEG, AVI, WebM y M4V.
- Buffer documenta hasta 10 GB para Shorts.

## Instagram a través de Buffer
- La guía general de Buffer documenta hasta 300 MB para videos en Instagram.
- Los formatos indicados en su guía general son MP4 y MOV.
- El formato (Reel, feed, story) y los límites concretos deben validarse con el canal y metadata del API; no asumir equivalencia entre ellos.

## X API directa — costos consultados
La tabla pública oficial de X Developer Platform consultada el 20-11-2026 muestra:
- Lectura de posts: USD 0,005 por recurso devuelto.
- Crear post: USD 0,015 por solicitud.
- Crear post con URL: USD 0,20 por solicitud.

Estas tarifas no son un presupuesto autorizado ni garantía de precio futuro. X Research debe permanecer deshabilitado hasta que el operador configure presupuesto y límite diario. El coste de lectura depende de los recursos devueltos, por lo que la paginación y el máximo de resultados son controles de coste obligatorios.

## Fuentes oficiales
- Buffer API overview: https://developers.buffer.com/guides/introduction.html
- Buffer API authentication and key scope: https://developers.buffer.com/guides/authentication.html
- Buffer posts, scheduling, channels and metrics: https://developers.buffer.com/guides/posts-and-scheduling.html
- Buffer video specs: https://support.buffer.com/articles/sharing-videos-through-buffer-LOe2p2rnAI
- Buffer X integration: https://support.buffer.com/en-us/articles/using-xtwitter-with-buffer-nA84XnWtuU
- X Developer Platform pricing: https://developer.twitter.com/

Antes de cada integración real, volver a comprobar estas páginas y el Developer Console de la cuenta. No incluir credenciales en documentación ni automatizar escrituras sin aprobación.
