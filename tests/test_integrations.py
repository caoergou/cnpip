"""测试 pdm / poetry / conda 镜像源配置（mock 外部 CLI，不真正执行）。"""
import sys
from types import SimpleNamespace

import pytest

import cnpip.cnpip as cli_module
import cnpip.integrations as module
from cnpip.integrations import (
    CONDA_MIRRORS,
    POETRY_SOURCE_NAME,
    conda_set_commands,
    set_conda_mirror,
    set_pdm_mirror,
    set_poetry_mirror,
    unset_conda_mirror,
    unset_pdm_mirror,
    unset_poetry_mirror,
)

MIRROR_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'


def fake_run_factory(calls, returncode=0, stdout='', stderr=''):
    def _fake_run(cmd):
        calls.append(cmd)
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _fake_run


@pytest.fixture
def tool_installed(monkeypatch, tmp_path):
    """模拟所有外部工具均已安装。"""
    monkeypatch.setattr(module.shutil, 'which', lambda name: f'/usr/bin/{name}')
    conda_path = tmp_path / '.condarc'
    conda_path.write_text('channels:\n  - defaults\n', encoding='utf-8')
    monkeypatch.setattr(module, 'get_conda_config_path', lambda: conda_path)


@pytest.fixture
def tool_missing(monkeypatch):
    """模拟外部工具均未安装。"""
    monkeypatch.setattr(module.shutil, 'which', lambda name: None)


class TestPdm:
    def test_set_runs_pdm_config(self, tool_installed, monkeypatch):
        calls = []
        monkeypatch.setattr(module, '_run', fake_run_factory(calls))
        values = iter([None, MIRROR_URL])
        monkeypatch.setattr(module, 'get_pdm_mirror', lambda: next(values))
        success, msg = set_pdm_mirror(MIRROR_URL)
        assert success
        assert calls == [['/usr/bin/pdm', 'config', 'pypi.url', MIRROR_URL]]
        assert MIRROR_URL in msg

    def test_set_fails_when_pdm_missing(self, tool_missing):
        success, msg = set_pdm_mirror(MIRROR_URL)
        assert not success
        assert 'pdm' in msg

    def test_set_reports_cli_error(self, tool_installed, monkeypatch):
        monkeypatch.setattr(module, '_run', fake_run_factory([], returncode=1, stderr='boom'))
        monkeypatch.setattr(module, 'get_pdm_mirror', lambda: None)
        success, msg = set_pdm_mirror(MIRROR_URL)
        assert not success
        assert 'boom' in msg

    def test_unset_deletes_config_key(self, tool_installed, monkeypatch):
        calls = []
        monkeypatch.setattr(module, '_run', fake_run_factory(calls))
        module.record_managed_value("pdm:user", None, MIRROR_URL)
        monkeypatch.setattr(module, 'get_pdm_mirror', lambda: MIRROR_URL)
        success, msg = unset_pdm_mirror()
        assert success
        assert calls == [['/usr/bin/pdm', 'config', '--delete', 'pypi.url']]

    def test_unset_graceful_when_not_set(self, tool_installed, monkeypatch):
        calls = []
        monkeypatch.setattr(module, '_run', fake_run_factory(calls, returncode=1))
        monkeypatch.setattr(module, 'get_pdm_mirror', lambda: None)
        success, msg = unset_pdm_mirror()
        assert success
        assert calls == []


class TestPoetry:
    def test_set_requires_pyproject(self, tool_installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        success, msg = set_poetry_mirror(MIRROR_URL)
        assert not success
        assert 'pyproject.toml' in msg

    def test_set_adds_primary_source(self, tool_installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / 'pyproject.toml'
        config.write_text('[tool.poetry]\n', encoding='utf-8')
        calls = []
        def fake_run(cmd):
            calls.append(cmd)
            config.write_text(
                '[tool.poetry]\n[[tool.poetry.source]]\n'
                f'name = "{POETRY_SOURCE_NAME}"\nurl = "{MIRROR_URL}"\n',
                encoding='utf-8',
            )
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        monkeypatch.setattr(module, '_run', fake_run)
        success, msg = set_poetry_mirror(MIRROR_URL)
        assert success
        assert calls == [['/usr/bin/poetry', 'source', 'add', '--priority=primary',
                          POETRY_SOURCE_NAME, MIRROR_URL]]

    def test_set_fails_when_poetry_missing(self, tool_missing):
        success, msg = set_poetry_mirror(MIRROR_URL)
        assert not success

    def test_unset_restores_original_project_file(self, tool_installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / 'pyproject.toml'
        original = b'# comment\n[tool.poetry]\n'
        config.write_bytes(original)
        calls = []
        def fake_run(cmd):
            calls.append(cmd)
            config.write_text(
                '[tool.poetry]\n[[tool.poetry.source]]\n'
                f'name = "{POETRY_SOURCE_NAME}"\nurl = "{MIRROR_URL}"\n',
                encoding='utf-8',
            )
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        monkeypatch.setattr(module, '_run', fake_run)
        success, msg = set_poetry_mirror(MIRROR_URL)
        assert success, msg
        success, msg = unset_poetry_mirror()
        assert success
        assert config.read_bytes() == original

    def test_unset_graceful_without_pyproject(self, tool_installed, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        success, msg = unset_poetry_mirror()
        assert success


class TestConda:
    def test_mirror_table_is_https(self):
        assert CONDA_MIRRORS
        for url in CONDA_MIRRORS.values():
            assert url.startswith('https://')

    def test_set_commands_cover_channels(self):
        base = 'https://mirrors.example.edu.cn/anaconda'
        cmds = conda_set_commands('/usr/bin/conda', base)
        joined = [' '.join(c) for c in cmds]
        assert any(f'{base}/pkgs/main' in c for c in joined)
        assert any(f'{base}/pkgs/r' in c for c in joined)
        assert any(f'{base}/pkgs/msys2' in c for c in joined)
        assert any(f'custom_channels.conda-forge {base}/cloud' in c for c in joined)
        assert any(f'custom_channels.pytorch {base}/cloud' in c for c in joined)

    def test_set_commands_strip_trailing_slash(self):
        cmds = conda_set_commands('/usr/bin/conda', 'https://example.com/anaconda/')
        for cmd in cmds:
            assert not any('anaconda//' in part for part in cmd)

    def test_set_does_not_remove_existing_default_channels(self, tool_installed, monkeypatch):
        calls = []
        config = module.get_conda_config_path()
        def fake_run(cmd):
            calls.append(cmd)
            config.write_text(f'default_channels:\n  - {CONDA_MIRRORS["tuna"]}/pkgs/main\n', encoding='utf-8')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        monkeypatch.setattr(module, '_run', fake_run)
        success, msg = set_conda_mirror(CONDA_MIRRORS['tuna'])
        assert success
        assert all('--remove-key' not in cmd for cmd in calls)
        assert calls[1][2:4] == ['--prepend', 'default_channels']

    def test_set_fails_when_conda_missing(self, tool_missing):
        success, msg = set_conda_mirror(CONDA_MIRRORS['tuna'])
        assert not success

    def test_unset_restores_original_conda_file(self, tool_installed, monkeypatch):
        config = module.get_conda_config_path()
        original = config.read_bytes()
        calls = []
        def fake_run(cmd):
            calls.append(cmd)
            config.write_text(
                f'default_channels:\n  - {CONDA_MIRRORS["tuna"]}/pkgs/main\n',
                encoding='utf-8',
            )
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        monkeypatch.setattr(module, '_run', fake_run)
        success, msg = set_conda_mirror(CONDA_MIRRORS['tuna'])
        assert success, msg
        success, msg = unset_conda_mirror()
        assert success
        assert config.read_bytes() == original


class TestCliIntegration:
    """CLI 分发层：确认 flag 正确路由到对应工具（mock 掉真实配置函数）。"""

    def test_set_pdm_flag_routes_to_pdm(self, monkeypatch):
        received = {}
        monkeypatch.setattr(cli_module, 'set_pdm_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--pdm'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0
        assert received['url'] == cli_module.MIRRORS['tuna']

    def test_set_poetry_flag_routes_to_poetry(self, monkeypatch):
        received = {}
        monkeypatch.setattr(cli_module, 'set_poetry_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--poetry'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0
        assert received['url'] == cli_module.MIRRORS['tuna']

    def test_set_conda_flag_uses_conda_mirror_table(self, monkeypatch):
        received = {}
        monkeypatch.setattr(cli_module, 'set_conda_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--conda'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0
        assert received['url'] == CONDA_MIRRORS['tuna']

    def test_set_conda_rejects_non_conda_mirror(self, monkeypatch, capsys):
        # aliyun 提供 pypi 镜像但不提供 conda 镜像
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'aliyun', '--conda'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert 'conda' in captured.out

    def test_unset_conda_flag(self, monkeypatch):
        called = []
        monkeypatch.setattr(cli_module, 'unset_conda_mirror',
                            lambda: called.append(True) or (True, 'ok'))
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'unset', '--conda'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0
        assert called

    def test_uv_and_pdm_flags_are_mutually_exclusive(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--uv', '--pdm'])
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code != 0
