# Control técnico de calidad audiovisual

Money-Geta incorpora `money-geta-qc`, una comprobación técnica local basada en FFprobe.

## Uso

```powershell
money-geta-qc --file ".\ruta\video.mp4" --aspect 9:16 --min-duration 5 --require-audio --report ".\qc\video.json"
```

Parámetros:
- `--file`: archivo local que se inspeccionará.
- `--aspect`: relación esperada opcional: `9:16`, `16:9` o `1:1`.
- `--min-duration` / `--max-duration`: límites de duración en segundos.
- `--require-audio`: exige una pista de audio.
- `--report`: guarda el informe JSON.
- `--ffprobe`: permite indicar la ruta al ejecutable si no está en PATH.

El comando devuelve 0 cuando pasa y 2 cuando falla. La ausencia de FFprobe, archivo, metadatos o streams válidos bloquea el control.

## Alcance y límites

Comprueba existencia y tamaño, lectura de contenedor, presencia de video, dimensiones, códec, duración, relación de aspecto opcional y audio opcional. No reproduce el video ni evalúa sincronización perceptual, legibilidad de subtítulos, calidad visual, exactitud factual, derechos, licencias, música, políticas de plataforma ni calidad editorial.

**No es todavía un gate conectado a `publication-check`.** El operador debe revisar el informe y el video. La integración automática con el registro de artefactos es una fase posterior; nunca se interpreta un QC técnico como autorización de publicación.
