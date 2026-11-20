# Registro y evaluación de afirmaciones

El ledger factual es independiente del ledger de derechos de assets. Se alimenta únicamente de evidencias capturadas en `source_ledger.jsonl` y guarda eventos append-only en `claim_ledger.jsonl`.

## Uso

```powershell
money-geta-claims add --project mi-proyecto --campaign mi-campana --claim "La empresa anunció el producto el 10 de mayo" --evidence ID_EVIDENCIA_1 --evidence ID_EVIDENCIA_2
money-geta-claims assess --project mi-proyecto --campaign mi-campana --claim-id ID_CLAIM --status supported --rationale "Ambas fuentes primarias coinciden en fecha y contexto." --independence-attested
money-geta-claims list --project mi-proyecto --campaign mi-campana
```

## Estados

- `unverified`: estado inicial; no hay evaluación humana suficiente.
- `supported`: exige dos hostnames distintos y declaración explícita del operador de que las fuentes son independientes.
- `contradicted`: exige dos hostnames distintos y una descripción concreta del conflicto.
- `unsupported`: el operador documenta por qué la evidencia no respalda la afirmación.

Cada evaluación registra actor `operator`, fecha, referencias y fundamento. Las evaluaciones nuevas agregan eventos; no sobrescriben el historial.

## Límites

El sistema no determina la verdad ni calcula independencia editorial automáticamente. Hostnames distintos no garantizan independencia; la atestación sigue siendo humana. El modelo de lenguaje no puede cambiar el estado. El gate de campaña está conectado al ledger: si la campaña tiene `factual_claims_required: true`, exige al menos una afirmación y bloquea si alguna no está evaluada como `supported`. Cualquier afirmación registrada en el ledger también debe estar `supported`, aunque la campaña no exija afirmaciones. Un ledger malformado o una referencia a evidencia inexistente bloquea. El control se ejecuta en `campaign-check` y antes de iniciar el render MPT.

Las campañas de perfiles `news` y `education` se crean con `factual_claims_required: true`; `gaming` y `viral` no lo exigen por defecto. Para estas últimas, si se registran afirmaciones, todas deben quedar respaldadas antes del render. Esta revisión factual no sustituye la inspección humana del video final, la verificación de derechos ni la aprobación de publicación.
