# Control de calidad de subtítulos

Money-Geta ofrece una validación local de archivos SRT y WebVTT:

- Detecta archivos sin cues, líneas demasiado largas, más de dos líneas por cue, solapamientos, tiempos no válidos, duración demasiado breve/larga y velocidad de lectura excesiva.
- Admite timestamps SRT y WebVTT, incluidos formatos WebVTT de minutos/segundos y horas/minutos/segundos.
- Reporte JSON opcional y código de salida 0 (pasa) / 2 (bloquea).

## Uso en Windows PowerShell

\`\`\`powershell
money-geta-subtitle-qc --file ".\\captions.srt" --report ".\\qc\\captions.json"
\`\`\`

Parámetros configurables: \`--max-line-chars\`, \`--max-lines\`, \`--max-cps\`, \`--min-cue-duration\`, \`--max-cue-duration\`.

## Límites

Es un control estructural y de legibilidad heurística. No compara el texto con el audio, no confirma transcripción ni traducción y no verifica sincronización perceptual, derechos o calidad editorial.
