# Evaluación inicial del catálogo de herramientas

Este documento clasifica los 20 proyectos del inventario aportado. Es una decisión de arquitectura preliminar, no una auditoría de licencias, seguridad, mantenimiento ni compatibilidad de versiones. Antes de instalar o distribuir, revisar el repositorio upstream, licencia, releases, dependencias y avisos de cada versión fijada.

| # | Proyecto | Licencia declarada por GitHub API | Última actividad (pushed_at) | Clasificación | Decisión |
|---:|---|---|---|---|---|
| 1 | Remotion Skills | No declarada | 2026-11-18 | Adaptable / pendiente legal | Consultar como guía; no redistribuir ni copiar hasta verificar licencia |
| 2 | ClipsAI | MIT | 2024-01-17 | Adaptable / mantenimiento a revisar | Benchmark opcional; actividad upstream relativamente antigua |
| 3 | FunClip | MIT | 2026-11-01 | Adaptable | Evaluar contra el selector de momentos actual |
| 4 | yt-dlp | Unlicense | 2026-11-19 | Universal | Ya existe integración; revisar términos y permisos de cada plataforma/fuente |
| 5 | TwitchDownloader | MIT | 2026-11-15 | Adaptable | Conector Twitch opcional; validar autorización de VOD/chat |
| 6 | Streamlink | BSD-2-Clause | 2026-11-18 | Adaptable | Captura de streams propios/autorizados; no evadir controles |
| 7 | OBS Studio | GPL-2.0 | 2026-11-20 | Adaptable / licencia copyleft | Mantener como aplicación externa; no incorporar código/binarios al paquete sin revisión GPL |
| 8 | PySceneDetect | BSD-3-Clause | 2026-11-20 | Universal | Ya existe como extra media |
| 9 | Auto-Editor | Unlicense | 2026-11-20 | Adaptable | Evaluar como etapa opcional, con revisión de cortes |
| 10 | faster-whisper | MIT | 2026-11-12 | Universal | Ya existe como extra media |
| 11 | WhisperX | BSD-2-Clause | 2026-11-12 | Adaptable | Evaluar alineación de palabra; comprobar licencias de modelos/dependencias |
| 12 | Silero VAD | MIT | 2026-11-20 | Universal / opcional | Añadir solo si benchmark demuestra mejora |
| 13 | MediaPipe | Apache-2.0 | 2026-11-20 | Adaptable | Tracking opcional; privacidad/localidad por defecto |
| 14 | OpenCV | Apache-2.0 | 2026-11-20 | Universal | Base común; evitar duplicar procesamiento |
| 15 | Subtitle Edit | MIT | 2026-11-20 | Adaptable | Herramienta auxiliar de revisión, no motor obligatorio |
| 16 | LosslessCut | GPL-2.0 | 2026-11-14 | Adaptable / licencia copyleft | Mantener como herramienta externa; no integrar código sin revisión GPL |
| 17 | MoviePy | MIT | 2026-08-26 | Adaptable | Solo para composición específica; evitar solapar FFmpeg |
| 18 | OpenCut | MIT | 2026-09-24 | Adaptable | Editor externo opcional; no automatizar GUI en núcleo |
| 19 | Remotion | No declarada por GitHub API | 2026-11-20 | Adaptable / BLOQUEADO legal | Revisar licencia comercial/uso de Remotion antes de adoptar |
| 20 | FFmpeg | No declarada por GitHub API | 2026-11-20 | Universal / revisión de build | Usar instalación externa; revisar configuración LGPL/GPL y codecs de cada binario |

## Evidencia y límites de esta auditoría
- Se consultó la metadata de los 20 repositorios en GitHub el 20-11-2026: licencia SPDX declarada por GitHub, rama por defecto, estado archivado y `pushed_at`.
- `pushed_at` indica actividad del repositorio, no garantiza releases estables, seguridad ni mantenimiento de cada dependencia.
- “No declarada” / `NOASSERTION` no significa que el proyecto carezca de licencia. Antes de redistribuir, inspeccionar el archivo LICENSE, avisos, licencias de dependencias, modelos y binarios.
- OBS Studio y LosslessCut figuran como GPL-2.0: no se integran ni redistribuyen dentro del paquete de Money-Geta sin una revisión específica de obligaciones copyleft. Su uso como programas externos se evalúa por separado.
- FFmpeg no tiene una única licencia de binario: la configuración de compilación y bibliotecas habilitadas puede cambiar las obligaciones. No empaquetar un binario sin auditar su build configuration.
- Remotion y Remotion Skills requieren verificar sus condiciones/licencia antes de adoptarlos, redistribuirlos o usarlos comercialmente.
- ClipsAI mantiene licencia MIT declarada, pero su última actividad visible es antigua frente al resto del catálogo; exigir prueba de compatibilidad antes de incorporarlo.

La clasificación es una recomendación de arquitectura, no una aprobación legal definitiva. No se instalaron los 20 proyectos ni se añadieron como dependencias del paquete.

## Módulos GTA VI exclusivos
La copia fijada de GTA VI ClaudeCode permanece en `vendor/gtavi-claudecode/`. Sus scripts/skills de tendencias, streams, cheats, payouts, mapas, preguntas, reacción Twitch, traducción y análisis de juego se consideran especializados. No se convierten en dependencias globales ni se exponen sin adaptadores y revisión de seguridad.

## Riesgos / bloqueos iniciales
- La captura de directos y VODs depende de derechos, permisos, autenticación y términos de cada plataforma.
- Tracking facial/biométrico puede implicar datos sensibles; mantener local y opcional, y no activarlo por defecto.
- No incorporar paquetes duplicados si FFmpeg, OpenCV o faster-whisper ya resuelven el caso con calidad suficiente.
- No instalar los 20 proyectos a la vez. Realizar benchmarks reproducibles de calidad, velocidad, memoria, tamaño y licencia.
- Los binarios, modelos y dependencias pueden tener licencias separadas de las del repositorio principal.
