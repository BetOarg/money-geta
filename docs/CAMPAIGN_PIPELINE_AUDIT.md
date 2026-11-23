# Auditoría de checkpoints de campaña

La auditoría de campañas es de solo lectura y puede ejecutarse sin conectarse a proveedores:

```powershell
money-geta campaigns audit --project mi-proyecto mi-campana
```

Reporta checkpoints locales de investigación, fuentes, claims, guion, revisión del guion, medios, derechos, plan visual, timeline, registro de render, QC y aprobación. `progress_ratio` es una proporción de checkpoints presentes, no un porcentaje de producción ni un indicador de calidad.

## Interpretación

- `complete`: checkpoint detectado por presencia/estado local; no implica frescura, integridad ni aprobación actual.
- `pending`: aún no se detecta el checkpoint.
- `blocked`: el gate de campaña no pasa o un ledger no puede leerse con seguridad.

El auditor no reproduce las revisiones hash-bound completas ni valida licencias, precisión factual, integridad audiovisual o la aprobación vigente de cada artefacto. Para esos controles deben utilizarse los comandos dedicados. No modifica manifests/ledgers, no descarga medios, no renderiza ni publica.
