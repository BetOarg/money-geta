# Matriz de capacidades e integraciones

Estados: **INTEGRADO** = existe implementación verificable en la rama actual; **PARCIAL** = existe parte del flujo/contrato; **PLANIFICADO** = falta implementación; **BLOQUEADO** = requiere seguridad, derechos, acceso o autorización previa.

## Capacidades comunes
| Capacidad | Implementación actual conocida | Objetivo | Estado |
|---|---|---|---|
| Sesiones y manifiestos locales | session_paths.py, ledger JSON | Trazabilidad de extremo a extremo | PARCIAL |
| Descarga autorizada | yt-dlp adapter con confirmación | Adaptadores por fuente, permisos y políticas | PARCIAL |
| Detección de momentos | GTA VI vendorizado | Motor genérico + plugins por tipo de fuente | PARCIAL |
| Escenas | PySceneDetect | Servicio común de detección | PARCIAL |
| Transcripción | faster-whisper | WhisperX opcional para alineación | PARCIAL |
| Subtítulos | SRT/VTT y burn-in FFmpeg | Edición, estilos, traducción y QC | PARCIAL |
| Reencuadre/seguimiento | cutter GTA VI; OpenCV en vendor | Motor de tracking genérico | PARCIAL |
| Edición/render | MPT CLI y FFmpeg | Adaptador común de motores | PARCIAL |
| Guion/LLM | Opt-in Chat Completions; evidence-bound draft generation; local GUI; hash-bound registration and human approve/reject/check ledger | Editing/versioning, style calibration, broader editorial review | PARCIAL |
| Búsqueda web e investigación | Brave/Tavily opt-in; `research` CLI y GUI por campaña, deduplicación URL y score de descubrimiento por consultas/frescura | Trend APIs sociales y métricas reales de plataformas | PARCIAL |
| Lectura de fuentes | scripts/providers/source_reader.py: HTML/XHTML/texto, DNS/IP seguro, límites y ledger JSONL por campaña | Extracción documental ampliada y captura de versiones | PARCIAL |
| Investigación y claims | Búsqueda, captura original y ledger de claims con evaluación humana | Corroboración multi-fuente, contradicciones y gate factual conectado a publicación | PARCIAL |
| Control de calidad | campaign-check + FFprobe; perceptual QC observacional con FFmpeg; QC de subtítulos; GUI QC tab runs technical/perceptual and optional subtitle checks, writes central report and hash-bound ledger event | QC factual, legal, platform preflight and full production-flow integration | PARCIAL |
| Aprobación humana | Registro append-only de MP4 final con SHA-256, QC técnico y QC central hash-bound; `publication-check` exige QC técnico + QC central listo + aprobación humana posterior al QC | Extender aprobación al guion y a los assets; integrar gate en conectores | PARCIAL |
| Analítica | ledger de sesiones | Métricas por plataforma/campaña | PLANIFICADO |

## Perfiles
| Perfil | Fuentes y enfoque | Capacidades | Estado |
|---|---|---|---|
| Gaming | Fuentes oficiales, VODs autorizados, streams propios/permitidos | trends, moments, clips, overlays, credits | PARCIAL: GTA VI específico |
| Viral | Fuentes trazables y reutilización autorizada | research, claim-check, hook, clips, formatos cortos | PLANIFICADO |
| Noticias | Fuentes primarias, agencias y documentos verificables | actualidad, corroboración, timestamps, correcciones | PLANIFICADO |
| Educación | Documentación, papers, fuentes institucionales | outline, explicación, gráficos/ejemplos, referencias | PLANIFICADO |

## Plataformas y conectores
| Plataforma/conector | Investigación | Publicación | Decisión |
|---|---|---|---|
| Buffer | No es fuente de tendencias universal | Sí: API GraphQL para canales conectados, borradores, cola/programación y métricas disponibles | Primera integración; usar API oficial y consultar capacidades del canal |
| X Research API | Sí, si el endpoint/producto contratado lo permite | No | Conector independiente, fase posterior y coste limitado |
| X Publishing API | No | Sí, sujeto a permisos/product tier y contrato vigente | No activar hasta autorización explícita |
| YouTube | Fuentes públicas mediante adaptadores separados | Buffer primero; API directa solo si hace falta | Destino prioritario |
| Instagram | No asumir búsqueda amplia | Buffer según soporte vigente | Destino |
| TikTok | No asumir búsqueda amplia | Buffer según soporte vigente | Destino |

La API actual de Buffer es GraphQL y permite gestionar canales conectados, posts y programación; los datos de métricas dependen de red/permisos. El soporte de video depende de cada canal y de límites de Buffer. Ver docs/PLATFORM_PUBLISHING_RULES.md. La API key de Buffer tiene alcance de cuenta y puede acceder a todas las organizaciones de esa cuenta; protegerla como secreto de alto impacto. Las capacidades y límites comerciales cambian: comprobar documentación oficial y capacidades reales antes de cada operación.

## Gates obligatorios
1. Fuente identificada y fecha de consulta.
2. Derechos/licencia y atribución documentados.
3. Guion y afirmaciones revisados según perfil.
4. Video final reproducible y validado técnicamente.
5. QC editorial y de plataforma completado.
6. Aprobación humana explícita ligada al hash/versión del artefacto.
7. Conector autorizado y publicación/programación confirmada por el operador.
8. Resultado, URL y métricas registrados sin secretos.
