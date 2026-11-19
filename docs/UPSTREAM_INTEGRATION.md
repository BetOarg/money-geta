# Upstream integration ledger

This workspace keeps upstream projects separate. Patches are overlays and are not applied to upstream repositories by this project.

## GTA VI ClaudeCode

Repository: https://github.com/Bodila51/gtavi-claudecode

Audited source revisions on 2026-11-19:

| File | Blob SHA | Finding | Local response |
|---|---|---|---|
| `scripts/live.py` | `c8208b6a0d9d0e4ddc93cfcd1ee123baeb0bb50a` | Deletes existing segments, chat logs and segment index in shared `jobs/<id>/live/` at startup. | `patches/gtavi-claudecode/live-session-isolation.patch` |
| `scripts/check.py` | `c71ad730e009e4a5b5aea113a34e20dabd37620b` | Missing campaign file is recorded as PASS; partial rules silently fall back to defaults. | `patches/gtavi-claudecode/campaign-check-fail-closed.patch` |
| `skills/live-mode/SKILL.md` | `6843df58b9818b252cc3d59f62929a3717c7c982` | Permission is treated as a later request, after recording. | `skills/live-recording-safety/SKILL.md` |
| `skills/rule-check/SKILL.md` | `8fc4895114888f5ced6b51e4b4b1f84375788c68` | Script scope does not prove rights, credits or audiovisual compliance. | `skills/campaign-publication-gate/SKILL.md` |

The live-recording and secrets-map overlays are pinned to audited blobs. Campaign validation is implemented and tested in Money-Geta itself; the experimental upstream `check.py` patch was removed after repeated context failures. Before applying any overlay to a newer upstream revision, inspect the diff and rebase; do not force-apply stale patches.

### Manual application

From a local clone of the upstream repository, verify the relevant blob/revision, then:

```bash
git apply --check /path/to/money-geta/patches/gtavi-claudecode/live-session-isolation.patch
git apply /path/to/money-geta/patches/gtavi-claudecode/live-session-isolation.patch
git apply --check /path/to/money-geta/patches/gtavi-claudecode/campaign-check-fail-closed.patch
git apply /path/to/money-geta/patches/gtavi-claudecode/campaign-check-fail-closed.patch
```

Run upstream tests and the regression tests after patching. This repository has not applied patches to your PC or upstream.

## MoneyPrinterTurbo

Repository: https://github.com/harry0703/MoneyPrinterTurbo

Audited upstream commit on 2026-11-19: `bdd8d328cc366fe70d9fa67ffd0443ba34b4a3e1` (MoneyPrinterTurbo 1.3.10). The `cli.py` blob at that commit is `e7dbda8e41de4a632e15392ae317e18aa0f30cca`; Money-Geta calls the supported `cli.py` interface rather than importing MPT internals.

The current upstream example config includes OpenAI Codex device-code authentication and a separate Codex image source, in addition to API-key based providers. It also defaults its listener to `0.0.0.0`; for a single-user local Windows installation, prefer `127.0.0.1` unless LAN access is intentionally required.

Keep local `config.toml`, auth storage, keys and generated media outside this repository. Do not commit credentials.

## Remaining integration work

- Pin exact upstream commit IDs for both dependencies.
- Build a repeatable Windows bootstrap that installs dependencies without overwriting existing user data.
- Test the two upstream patches against clean clones of their exact audited revisions.
- Adapt selected skills only after inspecting each script's arguments and outputs.
- Verify MoneyPrinterTurbo's Codex text/image paths on the user's machine; no local execution is claimed here.
