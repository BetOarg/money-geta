# Upstream integration ledger

Money-Geta preserves third-party source snapshots under `vendor/` and keeps upstream updates explicit. Patches are overlays and are not applied to external repositories by this project.

## GTA VI ClaudeCode

Repository: https://github.com/Bodila51/gtavi-claudecode

Audited upstream commit on 2026-11-19: `dd95d393c6f74fe2ac14b0239f8826691e5dcb0e`.

| File | Blob SHA | Finding | Local response |
|---|---|---|---|
| `scripts/live.py` | `c8208b6a0d9d0e4ddc93cfcd1ee123baeb0bb50a` | Deletes existing segments, chat logs and segment index in shared `jobs/<id>/live/` at startup. | `patches/gtavi-claudecode/live-session-isolation.patch` |
| `scripts/check.py` | `c71ad730e009e4a5b5aea113a34e20dabd37620b` | Missing campaign file is recorded as PASS; partial rules silently fall back to defaults. | Replaced by Money-Geta's own tested fail-closed campaign gate; no upstream patch is shipped. |
| `skills/live-mode/SKILL.md` | `6843df58b9818b252cc3d59f62929a3717c7c982` | Permission is treated as a later request, after recording. | `skills/live-recording-safety/SKILL.md` |
| `skills/rule-check/SKILL.md` | `8fc4895114888f5ced6b51e4b4b1f84375788c68` | Script scope does not prove rights, credits or audiovisual compliance. | `skills/campaign-publication-gate/SKILL.md` |

A text snapshot of GTA VI ClaudeCode is now preserved under `vendor/gtavi-claudecode/`, pinned to source commit `67acdb4391fa491821b908bb7c455cf8148ad515`; see `SOURCE_SNAPSHOT.md` and the retained MIT license. The snapshot was recovered from the public fork `Acefake/gtavi` after the original repository's API began returning 404. Money-Geta uses the vendored `moments.py` and `cut.py` by default; analysis and cutting no longer depend on an external checkout. The original README and binary logo were intentionally omitted. Live recording remains disabled unless an external Git checkout is configured and the session-isolation patch is verified. The experimental upstream `check.py` and `secrets_map.py` patches were removed rather than shipping overlays that did not pass exact-blob application checks. Before applying any overlay to a newer upstream revision, inspect the diff and rebase; do not force-apply stale patches.

### Manual application

From a local clone of the upstream repository, verify the relevant blob/revision, then:

```bash
git apply --check /path/to/money-geta/patches/gtavi-claudecode/live-session-isolation.patch
git apply /path/to/money-geta/patches/gtavi-claudecode/live-session-isolation.patch
```

Run upstream tests and the regression tests after patching. This repository has not applied patches to your PC or upstream.

## MoneyPrinterTurbo

Repository: https://github.com/harry0703/MoneyPrinterTurbo

Audited upstream commit on 2026-11-19: `bdd8d328cc366fe70d9fa67ffd0443ba34b4a3e1` (MoneyPrinterTurbo 1.3.10). The `cli.py` blob at that commit is `e7dbda8e41de4a632e15392ae317e18aa0f30cca`; CI fetches this exact commit and checks the CLI help contract. Money-Geta calls the supported `cli.py` interface rather than importing MPT internals. The upstream `main` branch has since moved; the integration remains pinned to this audited revision until a new compatibility audit is completed.

The current upstream example config includes OpenAI Codex device-code authentication and a separate Codex image source, in addition to API-key based providers. It also defaults its listener to `0.0.0.0`; for a single-user local Windows installation, prefer `127.0.0.1` unless LAN access is intentionally required.

Keep local `config.toml`, auth storage, keys and generated media outside this repository. Do not commit credentials.

## Remaining integration work

- Run the new Windows bootstrap on the user's PC and confirm FFmpeg/FFprobe, Python runtimes and actual project paths.
- Verify the Codex/Gemini text/image paths and execute one real local-media render on the user's PC; no local execution is claimed here.
- Continue only with further adapters that have verified arguments, outputs and safe side-effect boundaries.
