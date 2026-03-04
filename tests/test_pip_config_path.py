"""测试 get_pip_config_path_for_scope() 的跨平台路径逻辑。"""
import platform
import pytest
from pathlib import Path

import cnpip.cnpip as module
from cnpip.cnpip import get_pip_config_path_for_scope


def fake_system(name):
    """工厂函数：返回一个总是返回 name 的 platform.system 替代函数。"""
    return lambda: name


class TestPipConfigPathLinux:
    def test_user_scope_uses_xdg_config_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(module.platform, 'system', fake_system('Linux'))
        monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
        path = get_pip_config_path_for_scope('user')
        assert path == tmp_path / 'pip' / 'pip.conf'

    def test_user_scope_fallback_to_home_config(self, monkeypatch, tmp_path):
        monkeypatch.setattr(module.platform, 'system', fake_system('Linux'))
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        path = get_pip_config_path_for_scope('user')
        assert path.name == 'pip.conf'
        assert 'pip' in str(path)

    def test_global_scope_is_etc_pip_conf(self, monkeypatch):
        monkeypatch.setattr(module.platform, 'system', fake_system('Linux'))
        path = get_pip_config_path_for_scope('global')
        assert path == Path('/etc/pip.conf')

    def test_invalid_scope_returns_none(self, monkeypatch):
        monkeypatch.setattr(module.platform, 'system', fake_system('Linux'))
        path = get_pip_config_path_for_scope('invalid')
        assert path is None


class TestPipConfigPathWindows:
    def test_user_scope_uses_appdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(module.platform, 'system', fake_system('Windows'))
        monkeypatch.setenv('APPDATA', str(tmp_path))
        path = get_pip_config_path_for_scope('user')
        assert path == tmp_path / 'pip' / 'pip.ini'

    def test_global_scope_uses_programdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(module.platform, 'system', fake_system('Windows'))
        monkeypatch.setenv('PROGRAMDATA', str(tmp_path))
        path = get_pip_config_path_for_scope('global')
        assert path == tmp_path / 'pip' / 'pip.ini'


class TestPipConfigPathMacOS:
    def test_user_scope_path(self, monkeypatch):
        monkeypatch.setattr(module.platform, 'system', fake_system('Darwin'))
        path = get_pip_config_path_for_scope('user')
        assert path is not None
        assert path.name == 'pip.conf'
        assert 'Library' in str(path)

    def test_global_scope_path(self, monkeypatch):
        monkeypatch.setattr(module.platform, 'system', fake_system('Darwin'))
        path = get_pip_config_path_for_scope('global')
        assert path is not None
        # 使用 'Library' 而非 '/Library'，避免 Windows 路径分隔符差异
        assert 'Library' in str(path)


class TestPipConfigPathActualPlatform:
    """在实际运行平台上验证路径合理性（不 mock platform.system）。"""

    def test_user_scope_returns_path(self):
        path = get_pip_config_path_for_scope('user')
        assert path is not None
        assert isinstance(path, Path)
        system = platform.system()
        if system == 'Windows':
            assert path.suffix == '.ini'
        else:
            assert path.suffix == '.conf'

    def test_global_scope_returns_path(self):
        path = get_pip_config_path_for_scope('global')
        assert path is not None
        assert isinstance(path, Path)
