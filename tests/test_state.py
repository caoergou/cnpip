"""测试配置所有权状态的精确恢复与安全写入。"""

import os
import stat

import cnpip.state as state_module


def test_missing_and_empty_files_have_different_fingerprints():
    assert state_module._fingerprint(None) != state_module._fingerprint(b"")


def test_state_file_is_private(tmp_path):
    path = tmp_path / "settings.conf"
    change, error = state_module.ManagedFileChange.begin("test:file", path)
    assert change, error
    state_module.atomic_write_bytes(path, b"updated")
    success, error = change.commit()
    assert success, error

    state_path = state_module.STATE_FILE
    if os.name == "nt":
        # Windows uses ACLs for privacy; st_mode does not expose Unix 700/600.
        assert state_path.exists()
        assert state_path.parent.exists()
    else:
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(state_path.parent.stat().st_mode) == 0o700


def test_restore_preserves_an_original_empty_file(tmp_path):
    path = tmp_path / "settings.conf"
    path.write_bytes(b"")
    change, error = state_module.ManagedFileChange.begin("test:empty", path)
    assert change, error
    state_module.atomic_write_bytes(path, b"updated")
    success, error = change.commit()
    assert success, error

    success, error = state_module.restore_managed_file("test:empty", path)
    assert success, error
    assert path.exists()
    assert path.read_bytes() == b""


def test_restore_removes_a_file_that_did_not_exist_before(tmp_path):
    path = tmp_path / "settings.conf"
    change, error = state_module.ManagedFileChange.begin("test:missing", path)
    assert change, error
    state_module.atomic_write_bytes(path, b"updated")
    success, error = change.commit()
    assert success, error

    success, error = state_module.restore_managed_file("test:missing", path)
    assert success, error
    assert not path.exists()
