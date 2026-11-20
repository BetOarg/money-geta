# Proveedores LLM intercambiables

## Alcance

Money-Geta incorpora un adaptador HTTP para proveedores compatibles con **OpenAI Chat Completions**. Permite cambiar endpoint y modelo sin acoplar el resto del sistema a un SDK o proveedor. El adaptador no investiga por sí mismo ni verifica fuentes: solo transporta mensajes y devuelve la respuesta del modelo.

## Proveedores y configuración

Configurar las variables en el entorno local de Money-Geta, nunca en Git:

| Variable | Función |
|---|---|
| `MONEY_GETA_LLM_BASE_URL` | URL base del endpoint compatible |
| `MONEY_GETA_LLM_MODEL` | Identificador exacto del modelo habilitado |
| `MONEY_GETA_LLM_API_KEY` | Clave opcional para gateways locales; necesaria para servicios que la exijan |
| `MONEY_GETA_LLM_TIMEOUT` | Timeout en segundos (por defecto 45) |
| `MONEY_GETA_LLM_ALLOW_REQUESTS` | Debe ser `true` para permitir una llamada de red; por defecto desactivado |

Ejemplos de endpoints documentados por los proveedores:

- OpenAI: `https://api.openai.com/v1`
- Gemini API OpenAI-compatible: `https://generativelanguage.googleapis.com/v1beta/openai/`

El nombre del modelo debe corresponder a uno que el proveedor tenga habilitado en la cuenta. No se fija un modelo por defecto ni se presupone que una suscripción ChatGPT incluya crédito de API.

## Ejemplo de uso desde Python

```python
from scripts.providers.llm import LLMConfig, chat_completion, extract_text

config = LLMConfig.from_env()
response = chat_completion(
    [{"role": "user", "content": "Redacta tres enfoques de guion sobre este brief."}],
    config=config,
    max_tokens=800,
)
draft = extract_text(response)
```

## Controles

- Ninguna llamada de red ocurre si `MONEY_GETA_LLM_ALLOW_REQUESTS` no es exactamente `true`.
- Los endpoints remotos deben usar HTTPS. HTTP solo se acepta para localhost/127.0.0.1.
- No se guardan claves en archivos de proyecto, campañas, logs ni repositorio.
- Los errores no reproducen cuerpo de respuesta, encabezados ni secretos.
- La prueba automatizada simula la respuesta HTTP: no llama a OpenAI ni a Google y no consume créditos.
- La bandera de habilitación es una protección contra llamadas accidentales, no un límite de gasto. Antes de activarla, revisar facturación, cuota y límites del proveedor.

## Límites conocidos

Esta primera entrega cubre texto mediante Chat Completions compatible. No incluye aún búsqueda web, recuperación de fuentes, citas verificadas, streaming, herramientas, JSON estructurado ni medición de coste. Esas funciones se incorporarán como capacidades separadas y con sus propios contratos. Una respuesta del modelo nunca se considera evidencia factual por sí sola.
