# QC perceptual (observacional)

Esta comprobación complementa el QC técnico de FFprobe y el QC de subtítulos. Detecta **posibles** tramos de negro, imagen congelada y silencio prolongado mediante filtros de FFmpeg.

## Instalar y usar

Requiere que `ffmpeg` esté instalado y accesible en PATH.

```bash
money-geta-perceptual-qc --file output/final.mp4
money-geta-perceptual-qc --file output/final.mp4 --black-min 1.5 --freeze-min 2.5 --silence-min 4 --report reports/perceptual-qc.json
```

Umbrales iniciales: negro 1 s (luma 0.10), congelado 2 s (ruido -60 dB), silencio 3 s (ruido -50 dB). Son configurables; no representan criterios universales.

## Alcance y cautela

- El reporte registra observaciones, **no falla el video por esos hallazgos**. Negro, una imagen fija o silencio pueden ser intencionales.
- No valida el significado del contenido, calidad artística, sincronización labial, derechos, licencia, factualidad ni reglas de plataformas.
- La inspección procesa el archivo local; no sube contenido.
- FFmpeg se ejecuta con timeout y se comprueba su código de salida.
- No se integra todavía con la aprobación/publicación: primero deben revisarse falsos positivos en videos reales.

