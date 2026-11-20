# GTA VI ClaudeCode — vendored source snapshot

This directory preserves the text source files of the GTA VI ClaudeCode plugin so Money-Geta does not need to fetch the original repository at runtime.

## Provenance

- Original project: https://github.com/Bodila51/gtavi-claudecode
- Recovery source: https://github.com/Acefake/gtavi (public fork of the original project)
- Pinned source commit: `67acdb4391fa491821b908bb7c455cf8148ad515`
- Snapshot tree: `36daaf981b4f3a9b96f4a2a8e5f6d7ad46e6957b`
- Original author attribution in source history: Bodila51
- License: MIT; see [LICENSE](LICENSE).

## Scope

The snapshot includes the plugin metadata, requirements, all Python scripts, all skill instructions, and text references present in the pinned source tree. The upstream README and `docs/logo.png` were intentionally omitted: the root README remains withheld until Money-Geta integration is complete, and the binary logo is not required for operation.

The vendored code is preserved as upstream source, not yet treated as a trusted executable. Review dependencies and network/file operations before enabling each capability. Money-Geta should invoke these scripts through its own controlled adapter and session paths; do not assume the upstream plugin's Claude Code environment is available.

## Update policy

Never pull `main` implicitly. Review a proposed upstream revision, compare it against this pinned snapshot, preserve the MIT notice, run security and regression checks, then update this directory deliberately.
