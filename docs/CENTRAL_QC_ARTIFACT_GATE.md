# Gate QC central vinculado a artefactos

Se registra un informe consolidado que debe corresponder al MP4 registrado, a su hash SHA-256 y al estado `READY_FOR_HUMAN_REVIEW`. El informe `REVIEW_REQUIRED` o `FAILED` no permite continuar.

## Flujo

1. Ejecutar QC técnico y perceptual sobre el MP4.
2. Ejecutar QC de subtítulos si hay archivo de subtítulos.
3. Consolidar los reportes mediante `money-geta-qc-review`.
4. Registrar el informe central contra ID y hash exactos del artefacto.
5. Revisar el MP4 y aprobar manualmente después de registrar el QC central.
6. Ejecutar `publication-check`, que verifica campaña, aprobación, QC técnico, QC central exacto y orden temporal de aprobación.

## Registrar informe

```powershell
money-geta-artifact-review --campaign .\campaign.json central-qc-record --artifact-id ID --sha256 HASH --report .\reports\review.json
```

## Gate

`publication-check` bloquea si falta un QC técnico exitoso, falta un QC central, el último QC central no está `READY_FOR_HUMAN_REVIEW`, el hash no coincide o la aprobación humana no fue registrada después del QC central.

Esto es un gate de revisión, no un comando de publicación. No se conecta ni envía contenido a plataformas.
