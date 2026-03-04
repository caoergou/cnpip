import sys
import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """清除影响环境检测的环境变量，并将 sys.prefix 重置为 sys.base_prefix（模拟系统环境）。"""
    for var in ('UV_TOOL_DIR', 'CONDA_PREFIX', 'PIPX_HOME'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sys, 'prefix', sys.base_prefix)


@pytest.fixture
def fake_pip_config_path(tmp_path, monkeypatch):
    """将 get_pip_config_path_for_scope 重定向到 tmp_path，避免修改真实配置文件。"""
    import cnpip.cnpip as module

    def _fake_get_path(scope):
        return tmp_path / 'pip' / ('pip.ini' if scope == 'global' else 'pip.conf')

    monkeypatch.setattr(module, 'get_pip_config_path_for_scope', _fake_get_path)
    return tmp_path / 'pip'


@pytest.fixture
def fake_uv_config_path(tmp_path, monkeypatch):
    """将 get_uv_config_path 重定向到 tmp_path，避免修改真实 uv 配置文件。"""
    import cnpip.cnpip as module

    uv_toml = tmp_path / 'uv' / 'uv.toml'
    monkeypatch.setattr(module, 'get_uv_config_path', lambda: uv_toml)
    return uv_toml
