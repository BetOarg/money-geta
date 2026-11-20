# Money-Geta — arquitectura objetivo v1.0

## Propósito
Money-Geta es el centro operativo local y multipropósito para investigar, producir, revisar y preparar la distribución de videos. No es un generador dedicado a GTA VI. El núcleo contiene capacidades reutilizables; los perfiles temáticos configuran esas capacidades sin duplicarlas.

## Principios no negociables
1. Local-first: los archivos de trabajo y las credenciales permanecen en el equipo del operador.
2. Proveedores intercambiables: investigación, LLM, voz, imágenes, captura y render se conectan mediante adaptadores.
3. Evidencia trazable: conservar fuentes, fecha de consulta, procedencia de medios y decisiones.
4. Derechos fail-closed: material sin autorización o licencia verificable no pasa a producción/publicación.
5. Revisión humana: ningún video o texto se publica o programa sin aprobación explícita.
6. Separación de responsabilidades: perfil ≠ motor; conector social ≠ perfil temático; MPT ≠ orquestador.
7. No sobrescribir ni borrar material de usuario automáticamente.
8. Los servicios pagos, cuotas API y créditos requieren configuración y autorización del operador.
9. No modificar repositorios upstream; fijar versiones y preservar licencias/avisos.
10. La CI prueba contratos y código; no certifica permisos, autenticidad editorial ni instalación local.

## Capas
- **Control plane / CLI / GUI**: proyectos, campañas, sesiones, estado, configuración y aprobaciones.
- **Project & profile registry**: perfiles, reglas editoriales, fuentes permitidas, formatos y controles.
- **Capability services**: research, trend radar, source verification, scriptwriting, asset acquisition, transcription, moment detection, scene detection, reframing, subtitles, translation, audio, render orchestration, QC, rights ledger, analytics.
- **Provider adapters**: LLM (OpenAI API, Gemini u otros), search, image, TTS, transcription, storage y render. Ningún proveedor queda codificado como requisito global.
- **Media engines**: FFmpeg y adaptadores opcionales para PySceneDetect, faster-whisper, WhisperX, OpenCV/MediaPipe, ClipsAI, FunClip, Auto-Editor, MoviePy, Remotion, LosslessCut, OpenCut y MPT.
- **Distribution connectors**: Buffer como primera integración de distribución; X, YouTube, Instagram y TikTok como destinos. X también puede actuar como fuente mediante un adaptador independiente de X API.
- **Evidence & audit**: manifests, fuentes, licencias, derechos, aprobaciones, hashes y resultados.

## Perfiles iniciales
- **Gaming**: GTA VI, Minecraft, Fortnite, Roblox y otros juegos. GTA VI ClaudeCode queda encapsulado como módulo especializado, nunca como regla global.
- **Viral**: curiosidades, historias, tendencias y momentos destacados con verificación reforzada.
- **Noticias**: actualidad, contraste de fuentes, fecha/hora, atribución y correcciones.
- **Educación**: tutoriales, explicaciones y divulgación con precisión, referencias y lenguaje adecuado.

Un perfil declara capacidades requeridas, fuentes, reglas, formatos y controles. Puede activar o desactivar capacidades existentes, pero no contiene implementaciones duplicadas.

## Pipeline canónico
Proyecto/perfil → investigación y tendencias → verificación de fuentes → brief → guion → adquisición de medios autorizados → transcripción/análisis → selección humana de momentos → edición/reencuadre/subtítulos/traducción → render local vía adaptador MPT → QC técnico/editorial/derechos → aprobación humana → envío a Buffer/conector → programación/publicación confirmada → analítica y aprendizaje.

Cada etapa produce un artefacto versionado y un estado: PASS, INCOMPLETE, FAIL o HUMAN REVIEW REQUIRED. La aprobación de publicación es un registro separado y explícito.

## MPT y motores
MoneyPrinterTurbo es un motor de render y ensamblado detrás de un adaptador. Money-Geta valida su contrato, prepara campañas y comprueba los archivos resultantes. MPT no controla perfiles, derechos ni aprobación final. Se bloquea cualquier ajuste upstream que habilite autopublicación.

## Redes sociales y X
Buffer es el conector inicial para destinos compatibles y funciones que realmente exponga la cuenta/API conectada. No asumir soporte idéntico para todas las plataformas ni para cada tipo de video.
X se modela como dos conectores independientes:
- X Research: lectura/búsqueda de posts y conversaciones mediante X API, sujeto a disponibilidad, límites y coste.
- X Publishing: publicación de texto/video/hilos, inicialmente evaluada a través de Buffer; X API directa solo en una fase posterior y con presupuesto autorizado.
No usar lectura de X API paga ni publicación directa sin consentimiento, límites de gasto y prueba de contrato. Consultas con caché, cuotas por campaña y registro de coste.

## Seguridad y publicación
Los secretos se guardan fuera del repositorio. Logs/manifests nunca deben incluir tokens, cookies, URL con query sensible ni datos de autenticación. Toda descarga exige confirmación de derechos; la confirmación es una declaración del operador, no prueba legal. El QC técnico no equivale a autorización legal. El sistema debe bloquear el envío cuando falte evidencia o aprobación.

## Alcance de implementación
La base actual ya contiene sesiones, adquisición autorizada, análisis/corte GTA VI, pipeline de medios, GUI y render MPT. Esta arquitectura es el destino de evolución, no una afirmación de que todas las capas estén implementadas. Ver docs/INTEGRATION_MATRIX.md y docs/TOOL_EVALUATION.md.
