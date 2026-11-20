# Evaluación inicial del catálogo de herramientas

Este documento clasifica los 20 proyectos del inventario aportado. Es una decisión de arquitectura preliminar, no una auditoría de licencias, seguridad, mantenimiento ni compatibilidad de versiones. Antes de instalar o distribuir, revisar el repositorio upstream, licencia, releases, dependencias y avisos de cada versión fijada.

| # | Proyecto | Función | Clasificación | Decisión |
|---:|---|---|---|---|
| 1 | Remotion Skills | Guías/skills para video | Adaptable | Extraer instrucciones útiles; no duplicar el motor |
| 2 | ClipsAI | Convertir videos largos en clips | Adaptable | Evaluar como motor opcional detrás de adaptador |
| 3 | FunClip | Selección de clips por transcripción | Adaptable | Benchmark contra moment-finder/faster-whisper |
| 4 | yt-dlp | Adquisición de medios | Universal | Ya existe integración; permisos y términos por fuente |
| 5 | TwitchDownloader | VODs, clips y chat de Twitch | Adaptable | Conector Twitch opcional; validar permisos y uso |
| 6 | Streamlink | Captura de streams | Adaptable | Solo streams propios/autorizados; no evadir controles |
| 7 | OBS Studio | Grabación de pantalla/jugabilidad | Adaptable | Integración externa/local, no dependencia del núcleo |
| 8 | PySceneDetect | Detección de escenas | Universal | Ya existe como extra media |
| 9 | Auto-Editor | Edición por silencios/ritmo | Adaptable | Evaluar como etapa opcional, con revisión |
| 10 | faster-whisper | Transcripción local | Universal | Ya existe como extra media |
| 11 | WhisperX | Alineación temporal por palabra | Adaptable | Evaluar mejora de subtítulos; dependencias/recursos |
| 12 | Silero VAD | Detección de voz | Universal | Añadir si mejora detección de segmentos/audio |
| 13 | MediaPipe | Tracking y landmarks | Adaptable | Servicio de tracking opcional por dispositivo |
| 14 | OpenCV | Visión y recorte | Universal | Base común; aislar operaciones por adaptador |
| 15 | Subtitle Edit | Corrección/estilo de subtítulos | Adaptable | Herramienta auxiliar de revisión, no motor obligatorio |
| 16 | LosslessCut | Recorte sin recodificación | Adaptable | Exportación rápida cuando el formato lo permite |
| 17 | MoviePy | Edición programática | Adaptable | Solo para composición específica; evitar solapar FFmpeg |
| 18 | OpenCut | Editor de línea de tiempo | Adaptable | Integración externa opcional, no automatizar GUI en núcleo |
| 19 | Remotion | Plantillas de video programables | Adaptable | Motor de plantillas alternativo para motion graphics |
| 20 | FFmpeg | Procesamiento/codificación | Universal | Motor audiovisual base ya usado por el proyecto |

## Módulos GTA VI exclusivos
La copia fijada de GTA VI ClaudeCode permanece en `vendor/gtavi-claudecode/`. Sus scripts/skills de tendencias, streams, cheats, payouts, mapas, preguntas, reacción Twitch, traducción y análisis de juego se consideran especializados. No se convierten en dependencias globales ni se exponen sin adaptadores y revisión de seguridad.

## Riesgos / bloqueos iniciales
- La captura de directos y VODs depende de derechos, permisos, autenticación y términos de cada plataforma.
- Tracking facial/biométrico puede implicar datos sensibles; mantener local y opcional, y no activarlo por defecto.
- No incorporar paquetes duplicados si FFmpeg, OpenCV o faster-whisper ya resuelven el caso con calidad suficiente.
- No instalar los 20 proyectos a la vez. Realizar benchmarks reproducibles de calidad, velocidad, memoria, tamaño y licencia.
- Los binarios, modelos y dependencias pueden tener licencias separadas de las del repositorio principal.
