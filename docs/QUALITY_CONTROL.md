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

**No es todavía un gate conectado a `publication-check`.** El operador debe revisar el video y el estado QC. La integración automática con el registro de artefactos es una fase posterior; nunca se interpreta un QC técnico como autorización de publicación.


## QC vinculado al artefacto (gate de distribución)

La rama de integración agrega el subcomando `money-geta-artifact-review --campaign campaign.json qc --artifact-id ID --sha256 HASH`. Ejecuta FFprobe sobre el MP4 registrado y append-only registra el resultado (`artifact_qc`) ligado a su ID y SHA-256. La opción admite límites de duración, relación de aspecto, audio requerido, ejecutable FFprobe y timeout.

`publication-check` ahora exige un QC registrado y exitoso para el hash exacto del MP4. Si falta, falla, o el archivo cambia y su hash no coincide, el gate bloquea. Un QC fallido posterior también bloquea porque se usa la última evaluación.

El QC es técnico solamente; no acredita derechos, legalidad, exactitud, calidad editorial, políticas de plataforma ni reemplaza la aprobación humana. Este cambio se propone en un PR separado apilado sobre el PR #5 pendiente de merge.

## QC automático tras render MPT

El flujo `money-geta render` registra cada MP4 y ejecuta QC técnico automáticamente usando la relación de aspecto solicitada. Si FFprobe no está disponible o el archivo no cumple los controles, el comando devuelve código 2 y la sesión queda marcada como `technical_qc_failed`; no se considera listo para publicación. Para repetir una evaluación manual, usa la acción `qc` del registro de artefactos.

Ejemplo manual:

```powershell
money-geta-artifact-review --campaign .\campaign.json qc --artifact-id ID --sha256 HASH --aspect 9:16 --require-audio
money-geta-artifact-review --campaign .\campaign.json publication-check --artifact-id ID --sha256 HASH
``

El gate combina validación de campaña, aprobación humana del artefacto, integridad/hash y QC técnico exitoso para el mismo hash.
