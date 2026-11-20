# Modelo de proyectos y campañas — schema v1

## Proyecto
Cada proyecto es un espacio editorial persistente con un perfil temático. Se almacena como `<projects-root>/<project_id>/project.json`. El directorio raíz se configura con `MONEY_GETA_PROJECTS_DIR`; si no está definido se utiliza el directorio local de datos de la plataforma (LOCALAPPDATA en Windows o XDG_DATA_HOME en Linux/macOS).

Campos principales:
- `schema_version`: versión del contrato (actualmente 1).
- `project_id`: slug estable, normalizado y seguro.
- `name`, `profile_id`, `profile_name`: identidad y perfil seleccionado.
- `topic`, `brief`: contexto editorial.
- `status`: `draft` al crear; los estados posteriores se añadirán con el pipeline.
- `created_at`, `updated_at`: UTC ISO-8601.
- `campaigns`: reservado para referencias explícitas; el índice operativo se obtiene de los manifiestos de campaña.
- `workspace`: preservación de entradas y prohibición de sobrescritura.

## Campaña
Cada campaña se almacena en `<project>/campaigns/<campaign_id>/campaign.json`. Hereda el perfil del proyecto y comienza en estado `draft`.

El contrato conserva compatibilidad con `campaign_check.py`: `campaign_name`, `platform`, `sources`, `required_disclosures`, `permissions_confirmed` y `credits_confirmed`. Una campaña recién creada tiene fuentes vacías y ambas confirmaciones en false; por tanto, falla intencionalmente el gate hasta que se complete la evidencia y una persona confirme los permisos/créditos.

También reserva campos versionados para `source_evidence`, `rights_ledger`, `credit_records`, revisión editorial y distribución. No se aceptan aprobaciones implícitas. La distribución inicia en `draft_only` y exige aprobación humana.

## CLI
```powershell
money-geta projects create --name "Noticias de tecnología" --profile news --topic "IA" --brief "Explicar avances verificables"
money-geta projects list
money-geta projects show noticias-de-tecnologia
money-geta campaigns create --project noticias-de-tecnologia --name "Primer video" --platform "YouTube Shorts"
money-geta campaigns list --project noticias-de-tecnologia
money-geta campaigns show --project noticias-de-tecnologia primer-video
```

El root de proyectos puede cambiarse mediante `MONEY_GETA_PROJECTS_DIR`. Los comandos nunca publican, programan, compran créditos ni habilitan APIs pagas. La creación falla si el ID ya existe; no se sobrescribe ni reutiliza un proyecto/campaña anterior.

## Migración y compatibilidad
Schema v1 es aditivo y no altera las sesiones `money-geta.json` ni campañas antiguas. Los gates existentes siguen validando sus campos actuales. No se ejecutan migraciones destructivas. Cambios incompatibles requieren nueva versión de schema y migración explícita con copia de seguridad.

## Actualización y evidencia de campaña

Use `campaigns update` para agregar cada fuente junto con una referencia de evidencia de derechos. Las cantidades de `--source` y `--rights-evidence` deben coincidir. Las confirmaciones son explícitas: `--confirm-permissions` exige evidencia para todas las fuentes; `--confirm-credits` exige al menos un crédito o `--no-credits-required`. El gate schema v1 comprueba estos registros y atestaciones.

Ejemplo:

```powershell
money-geta campaigns update --project noticias-de-tecnologia primer-video --source "https://example.org/article" --rights-evidence "Permiso del editor archivado localmente" --credit "Fuente: Editor" --confirm-permissions --confirm-credits
money-geta campaign-check --campaign "RUTA\A\campaign.json"
```

Estas atestaciones registran lo declarado por el operador; no son dictamen legal ni sustituyen revisión humana del material final. La campaña sigue en draft y no puede publicarse desde estos comandos.
