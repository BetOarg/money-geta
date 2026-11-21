# Radar de investigación por campaña

El comando `research` consulta los proveedores web configurados y guarda leads de descubrimiento en el proyecto/campaña local. No incorpora resultados automáticamente al ledger de fuentes autorizadas ni al ledger de afirmaciones.

## Uso

También existe una pestaña **Investigación** en la GUI. Selecciona proyecto y campaña, escribe consultas (una por línea) y usa **Buscar señales**. La GUI solo permite ejecutar cuando el proveedor, API key y opt-in de red están configurados en el entorno; no busca al abrirse. Antes de enviar, muestra una confirmación con el proveedor, cantidad de consultas y posible consumo/cargo.


Desde la carpeta del repositorio:

```powershell
python -m scripts.money_geta research --project mi-proyecto --campaign mi-campana --query "tema novedades" --query "tema fuente oficial"
```

Se aceptan 1–10 consultas únicas de hasta 600 caracteres. Cada consulta genera una solicitud al proveedor elegido. El resultado se guarda en `projects/<project>/campaigns/<campaign>/research/` con nombre único, fecha de recuperación, evidencia normalizada y ranking.

## Score de descubrimiento

El score transparente combina:
- cobertura de consultas: 2 puntos por consulta distinta que encontró la URL;
- puntuación del proveedor: limitada al rango 0–1;
- bonus de frescura: hasta 2 puntos, calculado solo con fecha explícita y dentro de 60 días.

Este score **no** es popularidad, volumen de visualizaciones, tendencia social, veracidad, permiso de reutilización ni recomendación editorial. No se deben inventar métricas ausentes.

## Protección de costos y datos

- Las solicitudes externas solo funcionan si el proveedor, API key y `MONEY_GETA_SEARCH_ALLOW_REQUESTS=true` están configurados.
- No se activa ni se ejecuta la búsqueda al abrir la GUI o crear campañas.
- Las claves no se guardan en los informes.
- URLs con credenciales embebidas o parámetros de apariencia secreta se excluyen.
- Se quitan parámetros de tracking conocidos y fragmentos al agrupar URLs; se preservan parámetros no identificados.
- Errores por consulta se guardan como `partial` si hay resultados y `failed` si no hay ninguno.
- Los leads se guardan separados de `source_ledger.jsonl` y `claim_ledger.jsonl`. Antes de usar una fuente, leer su contenido, fecha y contexto, y registrar derechos por separado.
