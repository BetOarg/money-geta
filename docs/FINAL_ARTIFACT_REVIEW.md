# Revisión del artefacto final

Money-Geta registra cada MP4 que MoneyPrinterTurbo devuelve como resultado final. El registro no aprueba el video ni publica nada.

## Registro automático después del render

Cuando `money-geta render` termina correctamente:
- comprueba que cada archivo informado por MPT exista;
- registra el MP4 en `artifact_ledger.jsonl`, dentro de la carpeta de la campaña;
- calcula SHA-256 y tamaño del archivo;
- guarda ruta, proyecto, campaña, motor, formato, ID de tarea y fecha UTC;
- muestra `ARTIFACT_ID` y `ARTIFACT_SHA256`;
- deja la sesión en `rendered_pending_human_review`.

Si el registro no puede completarse de forma segura, el render queda marcado como `artifact_registration_failed` y el comando devuelve error. El archivo puede existir, pero no se considera revisable ni publicable.

## Revisar y aprobar un archivo exacto

Instala el proyecto con sus dependencias y usa los valores emitidos al terminar el render:

```powershell
money-geta-artifact-review --campaign ".\projects\<project>\campaigns\<campaign>\campaign.json" list
money-geta-artifact-review --campaign ".\projects\<project>\campaigns\<campaign>\campaign.json" approve --artifact-id "<ARTIFACT_ID>" --sha256 "<ARTIFACT_SHA256>" --reviewer "operador" --notes "Video revisado"
money-geta-artifact-review --campaign ".\projects\<project>\campaigns\<campaign>\campaign.json" check --artifact-id "<ARTIFACT_ID>" --sha256 "<ARTIFACT_SHA256>"
money-geta-artifact-review --campaign ".\projects\<project>\campaigns\<campaign>\campaign.json" publication-check --artifact-id "<ARTIFACT_ID>" --sha256 "<ARTIFACT_SHA256>"
```

Para rechazar un archivo, agrega `--decision rejected` y una nota. Una decisión posterior reemplaza a la anterior a efectos del gate.

## Reconocer observaciones del QC central

Si el reporte central devuelve `REVIEW_REQUIRED`, el operador debe inspeccionar las observaciones y registrarlas explícitamente antes de aprobar el artefacto:

```powershell
money-geta-artifact-review --campaign ".\\projects\\<project>\\campaigns\\<campaign>\\campaign.json" central-qc-acknowledge --artifact-id "<ARTIFACT_ID>" --sha256 "<ARTIFACT_SHA256>" --reviewer "operador" --notes "Observaciones revisadas; no impiden la aprobación"
money-geta-artifact-review --campaign ".\\projects\\<project>\\campaigns\\<campaign>\\campaign.json" approve --artifact-id "<ARTIFACT_ID>" --sha256 "<ARTIFACT_SHA256>" --reviewer "operador" --notes "Aprobado después de revisar el QC"
```

La aceptación queda ligada al SHA-256 y al evento exacto de QC central. Si se genera un nuevo reporte central, se necesita una nueva revisión. `FAILED` no puede reconocerse como aprobado; los bloqueos técnicos deben corregirse. La confirmación no certifica derechos ni exactitud factual.

## Condiciones de bloqueo

- El ID y SHA-256 deben corresponder a un artefacto registrado para esa campaña.
- El MP4 debe seguir en la ruta registrada y conservar exactamente el mismo contenido.
- Los archivos fuera de la carpeta de salida autorizada, las rutas con symlinks y los archivos que no sean MP4 se rechazan.
- Una aprobación corresponde únicamente al SHA-256 exacto revisado. Si el archivo cambia, la aprobación deja de servir.
- Los hallazgos `REVIEW_REQUIRED` necesitan reconocimiento humano explícito y una nueva aprobación posterior al reconocimiento; `FAILED` nunca se puede reconocer para saltar bloqueos.
- El ledger es append-only y un historial malformado bloquea la operación.

## Límites

La aprobación acredita que un operador revisó ese archivo concreto; no prueba derechos, exactitud factual ni cumplimiento legal. `publication-check` combina el control de campaña con la aprobación del artefacto, pero **no publica ni programa**. La autorización humana de publicación y los controles específicos de cada plataforma siguen siendo obligatorios.
