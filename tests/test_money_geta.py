from pathlib import Path

from scripts.money_geta import PATCHES, verify_patches


def test_patch_manifest_is_complete():
    assert set(PATCHES) == {"live.py", "check.py", "secrets_map.py"}
    for _, (_, blob, patch) in PATCHES.items():
        assert len(blob) == 40
        assert patch.is_file()


def test_upstream_check_rejects_non_git_directory(tmp_path):
    assert verify_patches(tmp_path) == 2
