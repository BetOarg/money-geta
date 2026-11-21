# MoneyPrinterTurbo integration

Upstream: https://github.com/harry0703/MoneyPrinterTurbo

## Local configuration

The current upstream `config.example.toml` supports an OpenAI Codex device-code provider and a separate Codex image model selection. It also defaults `listen_host` to `0.0.0.0`. For a single-PC workflow, use the partial overlay at `config/moneyprinterturbo.local.example.toml` and merge the values into your existing `config.toml`; do not replace the full upstream config.

Keep `config.toml`, `storage/auth`, OAuth tokens, API keys and generated files out of Git. The overlay intentionally contains no credentials.

## Runtime data directory

Money-Geta honors the upstream `MPT_HOME` environment variable. When it is set, Money-Geta reads the active `config.toml` from that runtime directory and only registers generated MP4 files from its `storage/tasks` subtree. When it is not set, the source checkout directory is used as the runtime root. Keep the runtime directory outside Git.

## Text and image generation

- Authenticate the Codex provider through the supported device-code flow in the installed MoneyPrinterTurbo version.
- Choose a text model from the models actually offered by the installed version.
- Configure the separate Codex image model only if the selected model exposes the required image tool.
- Do not assume ChatGPT subscription access means API Platform credits, or that every Codex model supports image generation.
- Keep rendering, stock/media retrieval and TTS as separately configured subsystems. A working text provider does not prove the entire video pipeline works.

## Pexels fallback

If Pexels key issuance is unavailable, do not make Pexels a required dependency. Select an available source supported by the installed MoneyPrinterTurbo build, or use locally licensed media. Record source and rights for every asset.

## Network exposure

Use `127.0.0.1` for a local single-user installation. Only bind to `0.0.0.0` when LAN exposure is intentional and the API is protected. Never expose the service publicly without authentication and a security review.
