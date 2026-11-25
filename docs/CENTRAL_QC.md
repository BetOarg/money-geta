# QC centralizado con integridad por hash

Los reportes QC se vinculan a los archivos de origen mediante SHA-256. El agregador verifica el hash actual del MP4 para los reportes técnicos/perceptuales y el hash actual del archivo SRT/VTT para el informe de subtítulos. Un reporte viejo, aunque apunte al mismo nombre/ruta, queda rechazado si el archivo cambió. El reporte perceptual es obligatorio por defecto; `--perceptual-optional` permite omitirlo explícitamente.

```bash
money-geta-qc --file output/final.mp4 --require-audio --detect-black --detect-silence --detect-clipping --report reports/technical.json
money-geta-subtitle-qc --file output/final.srt --report reports/subtitles.json
money-geta-perceptual-qc --file output/final.mp4 --report reports/perceptual.json
money-geta-qc-review --file output/final.mp4 --technical-report reports/technical.json --subtitle-report reports/subtitles.json --perceptual-report reports/perceptual.json --subtitle-required --report reports/review.json
```

Estados: `FAILED` (obligatorio faltante/fallido), `REVIEW_REQUIRED` (alertas), `READY_FOR_HUMAN_REVIEW` (sin alertas, no implica aprobación/publicación). El QC técnico puede comprobar streams, duración, ratio y metadatos; con `--detect-black` y `--detect-silence` ejecuta además detectores FFmpeg de segmentos negros (duración mínima 0,5 s) y silencios (umbral -50 dB, duración mínima 1 s) y muestras de audio recortadas mediante `astats`. Los hallazgos se guardan como observaciones y exigen revisión humana: no se clasifican automáticamente como defectos ni como aprobación. Estas exploraciones son opt-in. Si FFmpeg no está disponible o falla una exploración solicitada, el reporte técnico falla de forma cerrada. El reporte consolidado no publica ni programa contenido.
