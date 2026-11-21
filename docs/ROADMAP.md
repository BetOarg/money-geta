# Roadmap de implementación de Money-Geta

## Criterio de finalización
Money-Geta se considera centro operativo cuando un usuario puede crear un proyecto, elegir un perfil, investigar con evidencia, preparar un guion, incorporar medios autorizados, editar/renderizar, ejecutar controles de calidad, aprobar un artefacto concreto, distribuirlo por un conector compatible y registrar resultados; todo desde el control plane local, con secretos fuera del repositorio y sin publicación no autorizada.

## Fase 0 — Fundación y arquitectura
- [x] Preservar pipeline local, GUI, CLI, MPT adapter y snapshot GTA VI.
- [x] Documentar arquitectura multipropósito y límites de componentes.
- [x] Crear matriz de capacidades, perfiles y plataformas.
- [x] Registrar contratos de conectores.
- [x] Crear registro declarativo Gaming/Viral/Noticias/Educación.
- [x] Añadir CLI para listar e inspeccionar perfiles.
- [x] Auditar metadata de licencia/actividad de los 20 proyectos candidatos.
- [x] Documentar reglas de distribución Buffer/X/YouTube/Instagram/TikTok.
- [ ] Verificar CI del último HEAD y revisar todos los cambios antes de marcar la fase cerrada.

## Fase 1 — Modelo operativo y proyectos
- [x] Añadir modelo versionado de proyecto/campaña común independiente del perfil.
- [ ] Definir esquema versionado para brief, guion, fuentes, medios, derechos, render, QC, aprobación y publicación.
- [ ] Añadir migraciones/versionado de manifests sin romper sesiones anteriores.
- [ ] Añadir estados de pipeline y recuperación tras fallo.
- [x] Añadir GUI para crear proyectos, elegir perfil y revisar campañas/estado.

## Fase 2 — Servicios de capacidad comunes
- [ ] Extraer interfaces de research, scriptwriting, claim-check, transcription, moment detection, subtitles, reframing, translation y render.
- [x] Implementar adaptador LLM intercambiable compatible con Chat Completions (Gemini/OpenAI API/gateways compatibles), con credenciales locales y opt-in explícito de red.
- [x] Separar ChatGPT web de OpenAI API; nunca asumir API incluida en plan ChatGPT.
- [x] Añadir adaptadores de búsqueda Brave/Tavily con resultados normalizados, URL, extracto, fecha disponible, puntuación e instante de recuperación (separados del LLM).
- [x] Añadir lectura limitada de fuentes originales HTML/XHTML/texto y ledger JSONL versionado por campaña, con opt-in de red y defensas SSRF.
- [x] Añadir radar de descubrimiento web por campaña con consultas múltiples, deduplicación, score transparente y guardado local; no representa popularidad ni valida verdad/derechos.
- [x] Añadir ledger append-only de afirmaciones, referencias a evidencias capturadas y evaluación humana supported/contradicted/unsupported/unverified.
- [ ] Añadir corroboración asistida con revisión humana, detección de contradicciones y controles de independencia; el modelo no puede adjudicar verdad.
- [ ] Añadir proveedor de imágenes configurable; Pexels no será requisito.
- [ ] Añadir TTS configurable, sin acoplarlo a un proveedor.
- [ ] Benchmarks antes de incorporar ClipsAI, FunClip, WhisperX, Silero VAD, MediaPipe, Auto-Editor o MoviePy.

## Fase 3 — Perfiles temáticos
- [ ] Completar Gaming general, manteniendo GTA VI como subperfil.
- [ ] Crear subperfiles Minecraft, Fortnite, Roblox y otros juegos sin duplicar motores.
- [ ] Implementar Viral con verificación de afirmaciones y derechos.
- [ ] Implementar Noticias con fuentes primarias, corroboración, timestamps y correcciones.
- [ ] Implementar Educación con referencias, precisión y revisión de ejemplos.
- [ ] Añadir pruebas de aislamiento para demostrar que reglas de GTA VI no afectan otros perfiles.

## Fase 4 — Control de calidad y derechos
- [ ] Validar integridad de audio/video, duración, ratio, resolución, FPS, códec y subtítulos.
- [ ] Detectar pantalla negra, audio ausente, clipping, silencios y errores de render.
- [ ] Crear revisión editorial/factual específica por perfil.
- [ ] Crear ledger de licencias, permisos, atribuciones y procedencia por asset.
- [ ] Ligar aprobación humana al hash exacto del guion, medios y render.
- [ ] Bloquear distribución si falta cualquier evidencia o aprobación.

## Fase 5 — Distribución y analítica
- [ ] Implementar Buffer API GraphQL en modo borrador primero.
- [ ] Listar canales reales de la cuenta y validar capacidades antes de preparar un post.
- [ ] Añadir aprobación explícita para programar; deshabilitar publicación inmediata en primera versión.
- [ ] Implementar formatos y validaciones específicas por canal.
- [ ] Implementar X Research API solo con presupuesto, límite diario, caché y autorización.
- [ ] Evaluar X Publishing directo solo si Buffer no cubre un requisito.
- [ ] Añadir YouTube, Instagram y TikTok a través de canales compatibles con Buffer.
- [ ] Registrar ID, URL, estado y métricas devueltas; no inventar métricas faltantes.

## Fase 6 — End-to-end y release
- [ ] Probar flujo completo con medios propios/autorizados y perfiles distintos.
- [ ] Probar fallo de proveedor, límite de API, credenciales ausentes, archivo corrupto y reanudación.
- [ ] Probar que no se publica ante falta de aprobación y que no se sobrescriben archivos.
- [ ] Verificar instalación Windows, GUI, diagnóstico, render MPT real y conectores con cuentas de prueba.
- [ ] Revisar dependencias, licencias, secretos, permisos y empaquetado.
- [ ] Solo al terminar todas las fases, redactar README raíz completo.
- [ ] Publicación/release solo con aprobación explícita del propietario.

## Gates que no se automatizan
No se autoriza por sí solo: comprar créditos, aceptar términos comerciales, activar X API de pago, usar material sin permiso, publicar/programar, borrar ramas/archivos, fusionar PR o publicar una release. Requieren aprobación explícita.
