"""测试 detect_environment() 和 detect_windows_python_source() 的各种场景。"""
import sys
import platform
import pytest

from cnpip.cnpip import detect_environment, detect_windows_python_source, ENV_DESCRIPTIONS


class TestDetectEnvironment:
    def test_returns_system_when_no_venv(self, clean_env):
        result = detect_environment()
        assert result == 'system'
        assert result in ENV_DESCRIPTIONS

    def test_returns_conda_when_conda_prefix_set(self, clean_env, monkeypatch):
        monkeypatch.setenv('CONDA_PREFIX', '/opt/conda/envs/test')
        result = detect_environment()
        assert result == 'conda'

    def test_returns_uvx_via_uv_tool_dir(self, clean_env, monkeypatch, tmp_path):
        tool_dir = str(tmp_path / 'uv' / 'tools')
        fake_exe = str(tmp_path / 'uv' / 'tools' / 'cnpip' / 'bin' / 'python')
        monkeypatch.setenv('UV_TOOL_DIR', tool_dir)
        monkeypatch.setattr(sys, 'executable', fake_exe)
        result = detect_environment()
        assert result == 'uvx'

    def test_returns_uvx_via_path_pattern(self, clean_env, monkeypatch):
        fake_exe = '/home/user/.local/share/uv/tools/cnpip/bin/python'
        monkeypatch.setattr(sys, 'executable', fake_exe)
        result = detect_environment()
        assert result == 'uvx'

    def test_returns_venv_for_plain_venv(self, clean_env, monkeypatch, tmp_path):
        # 创建一个不含 uv= 的 pyvenv.cfg
        pyvenv_cfg = tmp_path / 'pyvenv.cfg'
        pyvenv_cfg.write_text('home = /usr/bin\nversion = 3.10.0\n', encoding='utf-8')
        monkeypatch.setattr(sys, 'prefix', str(tmp_path))
        monkeypatch.setattr(sys, 'base_prefix', '/usr')
        result = detect_environment()
        assert result == 'venv'

    def test_returns_uv_venv_when_pyvenv_has_uv(self, clean_env, monkeypatch, tmp_path):
        # 创建含 uv= 的 pyvenv.cfg（uv 创建的虚拟环境标志）
        pyvenv_cfg = tmp_path / 'pyvenv.cfg'
        pyvenv_cfg.write_text('home = /usr/bin\nuv = 0.5.0\nversion = 3.10.0\n', encoding='utf-8')
        monkeypatch.setattr(sys, 'prefix', str(tmp_path))
        monkeypatch.setattr(sys, 'base_prefix', '/usr')
        result = detect_environment()
        assert result == 'uv_venv'

    def test_returns_venv_when_pyvenv_cfg_missing(self, clean_env, monkeypatch, tmp_path):
        # venv 存在但 pyvenv.cfg 不存在
        monkeypatch.setattr(sys, 'prefix', str(tmp_path))
        monkeypatch.setattr(sys, 'base_prefix', '/usr')
        result = detect_environment()
        assert result == 'venv'

    def test_returns_pipx_when_in_pipx_home(self, clean_env, monkeypatch, tmp_path):
        pipx_home = str(tmp_path / 'pipx')
        fake_exe = str(tmp_path / 'pipx' / 'venvs' / 'myapp' / 'bin' / 'python')
        monkeypatch.setenv('PIPX_HOME', pipx_home)
        monkeypatch.setattr(sys, 'executable', fake_exe)
        monkeypatch.setattr(sys, 'prefix', str(tmp_path / 'pipx' / 'venvs' / 'myapp'))
        monkeypatch.setattr(sys, 'base_prefix', '/usr')
        result = detect_environment()
        assert result == 'pipx'

    def test_all_env_types_have_descriptions(self):
        for env_type in ('uvx', 'uv_venv', 'conda', 'pipx', 'venv', 'system'):
            assert env_type in ENV_DESCRIPTIONS
            assert ENV_DESCRIPTIONS[env_type]


class TestDetectWindowsPythonSource:
    """测试 detect_windows_python_source() 的路径匹配逻辑（跨平台可测试）。"""

    def _detect_with_exe(self, monkeypatch, fake_exe):
        monkeypatch.setattr(sys, 'executable', fake_exe)
        return detect_windows_python_source()

    def test_store_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe'
        )
        assert result == 'store'

    def test_uv_managed_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\AppData\Local\uv\python\cpython-3.12.0\python.exe'
        )
        assert result == 'uv'

    def test_conda_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\miniconda3\python.exe'
        )
        assert result == 'conda'

    def test_pyenv_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\.pyenv\pyenv-win\versions\3.12.0\python.exe'
        )
        assert result == 'pyenv'

    def test_scoop_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\scoop\apps\python\current\python.exe'
        )
        assert result == 'scoop'

    def test_official_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe'
        )
        assert result == 'official'

    def test_unknown_python(self, monkeypatch):
        result = self._detect_with_exe(
            monkeypatch,
            r'C:\CustomPython\python.exe'
        )
        assert result == 'unknown'
