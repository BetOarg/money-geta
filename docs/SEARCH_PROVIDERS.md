# Proveedores de búsqueda e investigación

## Alcance y criterio

El adaptador ofrece búsqueda web intercambiable y normaliza resultados como registros de evidencia con proveedor, consulta, título, URL, extracto, fecha publicada cuando el proveedor la informa, puntuación opcional e instante de recuperación UTC.

**Un resultado de búsqueda no demuestra por sí solo que una afirmación sea verdadera.** El extracto es material de referencia, no una cita textual validada ni una verificación factual. Antes de redactar noticias o afirmaciones sensibles, se debe abrir la fuente original, comprobar su fecha, autoría y contexto, y contrastar fuentes independientes.

## Proveedores implementados

- **Brave Search API:** Web Search GET, endpoint oficial `https://api.search.brave.com/res/v1/web/search`; autenticación por `X-Subscription-Token`.
- **Tavily Search API:** POST a `https://api.tavily.com/search`; autenticación Bearer.

Los endpoints y esquemas siguen las documentaciones oficiales enlazadas al final. No se fija proveedor obligatorio.

## Configuración local

Variables de entorno (no incluir en Git ni en manifiestos de campaña):

| Variable | Descripción |
|---|---|
| `MONEY_GETA_SEARCH_PROVIDER` | `brave` o `tavily` |
| `MONEY_GETA_SEARCH_API_KEY` | Clave del proveedor |
| `MONEY_GETA_SEARCH_ALLOW_REQUESTS` | Debe ser `true` para permitir solicitudes; por defecto desactivado |
| `MONEY_GETA_SEARCH_TIMEOUT` | Timeout, por defecto 30 segundos |
| `MONEY_GETA_SEARCH_COUNTRY` | País de Brave, por defecto `AR` |
| `MONEY_GETA_SEARCH_LANGUAGE` | Idioma de Brave, por defecto `es` |
| `MONEY_GETA_SEARCH_MAX_RESULTS` | Resultados solicitados, entre 1 y 20 |

Las llamadas pueden generar consumo/cargos según el plan del proveedor. No activar la variable de red hasta revisar la cuenta, el precio, la cuota y los límites.

## Uso Python

```python
from scripts.providers.search import SearchConfig, search_web

config = SearchConfig.from_env()
sources = search_web("documentación oficial de MoneyPrinterTurbo", config=config)
for source in sources:
    print(source.to_dict())
```

La función devuelve objetos `SearchEvidence`; `to_dict()` produce un registro serializable. La persistencia en el ledger versionado de campaña y la apertura/extracción de páginas originales son pasos posteriores, aún no implementados por este adaptador.

## Seguridad y límites

- No se realiza ninguna solicitud si `MONEY_GETA_SEARCH_ALLOW_REQUESTS` no es exactamente `true`.
- Solo se usan endpoints HTTPS fijos de los proveedores soportados; no se acepta una URL arbitraria suministrada por el usuario.
- Las claves se leen desde el entorno y no se escriben en resultados.
- Se filtran resultados que no tengan URL HTTP(S) válida o título, y URLs con credenciales embebidas.
- Se limita el número de resultados y el tiempo de espera.
- Los errores no reproducen cuerpos HTTP ni secretos.
- Las pruebas usan respuestas simuladas y no consumen cuota ni créditos.
- No hay scraping directo, descarga de páginas ni verificación automática de afirmaciones todavía.

## Referencias oficiales

- Brave Search API Web Search: https://api-dashboard.search.brave.com/api-reference/web/search/get
- Brave Search API Authentication: https://api-dashboard.search.brave.com/documentation/guides/authentication
- Tavily Search API: https://help.tavily.com/articles/4840311948-tavily-search-api
