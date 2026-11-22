# QC de previews locales

El composer de timeline se puede revisar con \`scripts.timeline_preview_qc.review_preview\`.

- FFprobe valida duración, video, codec, y aspect ratio 9:16.
- Si el timeline tiene pistas de audio, QC exige que el preview contenga audio.
- FFmpeg detecta segmentos negros, congelados y silencio como **observaciones** (no defectos automáticos).
- Estado PASS/REVIEW_REQUIRED depende de QC técnico; observaciones perceptuales requieren interpretación humana.
- Reporte JSON local, atómico, no sobrescribe informes existentes.

El QC de preview no autoriza render final ni publicación.
