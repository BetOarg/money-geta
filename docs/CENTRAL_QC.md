# QC centralizado: resultado y estado de revisión

Consolida JSON de QC técnico (FFprobe), subtítulos y observaciones perceptuales para un MP4. Verifica que los reportes correspondan al mismo archivo mediante ruta resuelta y calcula SHA-256 del artefacto.

## Ejemplo

```bash
money-geta-qc --file output/final.mp4 --report reports/technical.json
money-geta-subtitle-qc --file output/final.srt --report reports/subtitles.json
money-geta-perceptual-qc --file output/final.mp4 --report reports/perceptual.json
money-geta-qc-review --file output/final.mp4 --technical-report reports/technical.json --subtitle-report reports/subtitles.json --perceptual-report reports/perceptual.json --subtitle-required --report reports/review.json
```

## Estados
- FAILED: reporte técnico ausente/fallido o subtítulos requeridos ausentes/fallidos.
- REVIEW_REQUIRED: QC técnico pasa, pero subtítulos opcionales tienen hallazgos o QC perceptual detecta alertas.
- READY_FOR_HUMAN_REVIEW: controles obligatorios pasan sin alertas reportadas. No significa aprobado ni publicable.
El QC de subtítulos es estructural/de legibilidad, no verifica transcripción ni sincronía. El QC perceptual es observacional: negros, congelamientos y silencio pueden ser intencionales. No decide derechos, factualidad ni contenido editorial.
El consolidado no modifica ni publica archivos, no programa posts, y no reemplaza publication-check con aprobación humana ligada al hash. No está integrado aún al registry de artefactos.