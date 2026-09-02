"""使用真实 pdm / poetry / conda CLI 的隔离集成测试。

默认不执行，避免普通单元测试依赖外部工具。CI 的 real-cli workflow 会设置
``CNPIP_REAL_CLI_TESTS=1``，并在测试前安装并检查这些工具。
"""
import os
import shutil

import pytest

from cnpip.integrations import (
    CONDA_MIRRORS,
    POETRY_SOURCE_NAME,
    get_conda_config_path,
    get_pdm_mirror,
    set_conda_mirror,
    set_pdm_mirror,
    set_poetry_mirror,
    unset_conda_mirror,
    unset_pdm_mirror,
    unset_poetry_mirror,
)


pytestmark = pytest.mark.real_cli

if os.environ.get('CNPIP_REAL_CLI_TESTS') != '1':
    pytest.skip(
        '设置 CNPIP_REAL_CLI_TESTS=1 后才执行真实 CLI 测试',
        allow_module_level=True,
    )


PDM_MIRROR_URL = 'https://mirror.invalid/simple'
POETRY_MIRROR_URL = 'https://mirror.invalid/simple'


def require_tool(name):
    binary = shutil.which(name)
    if not binary:
        pytest.skip(f'未检测到真实 CLI: {name}')
    return binary


@pytest.fixture
def isolated_cli_environment(tmp_path, monkeypatch):
    """隔离用户目录和工具配置，真实 CLI 不得读写开发机配置。"""
    home = tmp_path / 'home'
    home.mkdir()
    appdata = home / 'AppData' / 'Roaming'
    local_appdata = home / 'AppData' / 'Local'
    xdg_config = home / '.config'
    xdg_cache = home / '.cache'

    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.setenv('APPDATA', str(appdata))
    monkeypatch.setenv('LOCALAPPDATA', str(local_appdata))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(xdg_config))
    monkeypatch.setenv('XDG_CACHE_HOME', str(xdg_cache))
    monkeypatch.setenv('POETRY_CONFIG_DIR', str(home / 'poetry-config'))
    monkeypatch.setenv('POETRY_CACHE_DIR', str(home / 'poetry-cache'))

    # 清除可能把真实用户配置重新带入测试进程的覆盖项。
    for variable in (
        'CONDARC',
        'PDM_CONFIG_FILE',
        'PDM_HOME',
        'PDM_PYPI_URL',
        'POETRY_HTTP_BASIC_CNPIP_USERNAME',
        'POETRY_HTTP_BASIC_CNPIP_PASSWORD',
    ):
        monkeypatch.delenv(variable, raising=False)

    condarc = tmp_path / 'condarc'
    condarc.write_bytes(b'channels:\n  - defaults\n')
    monkeypatch.setenv('CONDARC', str(condarc))
    monkeypatch.chdir(tmp_path)
    return condarc


def test_pdm_cli_set_and_unset_round_trip(isolated_cli_environment):
    require_tool('pdm')

    before = get_pdm_mirror()
    success, message = set_pdm_mirror(PDM_MIRROR_URL)
    assert success, message
    assert get_pdm_mirror() == PDM_MIRROR_URL

    success, message = unset_pdm_mirror()
    assert success, message
    assert get_pdm_mirror() == before


def test_poetry_cli_set_and_unset_restores_project(
        isolated_cli_environment, tmp_path, monkeypatch):
    require_tool('poetry')

    project = tmp_path / 'poetry-project'
    project.mkdir()
    monkeypatch.chdir(project)
    config = project / 'pyproject.toml'
    original = (
        b'[tool.poetry]\n'
        b'name = "cnpip-real-cli-test"\n'
        b'version = "0.1.0"\n'
        b'description = ""\n'
        b'authors = ["cnpip <cnpip@example.invalid>"]\n'
    )
    config.write_bytes(original)

    success, message = set_poetry_mirror(POETRY_MIRROR_URL)
    assert success, message
    content = config.read_text(encoding='utf-8')
    assert POETRY_SOURCE_NAME in content
    assert POETRY_MIRROR_URL in content

    success, message = unset_poetry_mirror()
    assert success, message
    assert config.read_bytes() == original


def test_conda_cli_set_and_unset_restores_condarc(
        isolated_cli_environment):
    require_tool('conda')
    config = isolated_cli_environment
    original = config.read_bytes()
    assert get_conda_config_path() == config.resolve()

    base_url = CONDA_MIRRORS['tuna']
    success, message = set_conda_mirror(base_url)
    assert success, message
    content = config.read_text(encoding='utf-8')
    base = base_url.rstrip('/')
    assert f'{base}/pkgs/main' in content
    assert f'{base}/pkgs/r' in content
    assert f'{base}/pkgs/msys2' in content
    assert f'{base}/cloud' in content
    assert 'show_channel_urls' in content

    success, message = unset_conda_mirror()
    assert success, message
    assert config.read_bytes() == original
