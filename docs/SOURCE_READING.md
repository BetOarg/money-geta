# Lectura y registro de fuentes originales

Money-Geta permite leer páginas públicas HTML/XHTML y texto plano para investigación. No ejecuta JavaScript, no inicia sesión, no usa cookies ni acepta cabeceras arbitrarias.

## Uso

```powershell
money-geta-read-source --project mi-proyecto --campaign mi-campana --url https://example.org/articulo --allow-network
```

`--allow-network` es obligatorio y autoriza una solicitud saliente para esa ejecución. El registro se guarda en `projects/<project_id>/campaigns/<campaign_id>/source_ledger.jsonl`. Cada línea contiene schema_version, URLs solicitada/final, título, descripción, texto extraído limitado, hash SHA-256 del cuerpo, fecha UTC, MIME, código HTTP y redirecciones. La misma evidencia no se duplica; un ledger malformado bloquea nuevas escrituras.

## Controles

- Solo HTTP/HTTPS en puertos estándar; rechaza credenciales embebidas y parámetros de URL típicos de secretos.
- Bloquea localhost, dominios `.local`, IPs no globales y DNS que incluya cualquier IP no pública.
- Conecta directamente a una IP pública validada; TLS conserva SNI y validación del hostname original.
- Revalida cada redirección, máximo cinco, sin downgrade HTTPS→HTTP.
- Timeout máximo 30 s; cuerpo máximo 2 MiB; solo HTML, XHTML y texto plano.
- Elimina script/style/noscript/SVG/template; no ejecuta código ni descarga recursos secundarios.
- El ledger es local y append-only; no modifica fuentes de assets ni atestaciones de derechos.

## Límites

La extracción no demuestra que una afirmación sea verdadera. No resuelve paywalls, páginas dinámicas, PDFs, documentos ofimáticos, autenticación, captchas ni multimedia. No comprueba robots.txt, términos de servicio, copyright, permisos de uso ni independencia editorial. El operador debe respetar las condiciones del sitio y conservar evidencia de derechos por separado. No consume créditos de Brave/Tavily.

En los resultados de búsqueda, `published_at` solo se completa si el proveedor entrega una fecha explícita. Etiquetas relativas como `2 days ago` se guardan en `provider_age`.
