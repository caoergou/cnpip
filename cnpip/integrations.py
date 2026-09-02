"""pdm / poetry / conda 镜像源配置。

统一通过各工具自身的 CLI 修改配置，避免自行解析配置文件格式：
- pdm:    pdm config pypi.url <url>            （用户级全局配置）
- poetry: poetry source add cnpip <url>        （项目级 pyproject.toml，poetry 不支持全局镜像）
- conda:  conda config --append/--set/...      （用户级 ~/.condarc）
"""
import shutil
import subprocess
from pathlib import Path

# poetry 项目中由 cnpip 管理的 source 名称，unset 时按此名称移除
POETRY_SOURCE_NAME = "cnpip"

# 提供 anaconda 镜像的源（与 pip 镜像列表独立维护，仅收录实测可用的）
CONDA_MIRRORS = {
    "tuna": "https://mirrors.tuna.tsinghua.edu.cn/anaconda",
    "ustc": "https://mirrors.ustc.edu.cn/anaconda",
    "nju": "https://mirrors.nju.edu.cn/anaconda",
    "sustech": "https://mirrors.sustech.edu.cn/anaconda",
}


def _run(cmd):
    """执行命令并捕获输出，返回 CompletedProcess。"""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='replace',
        check=False,
    )


def _which(name, install_hint):
    """查找可执行文件，找不到返回 (None, 错误信息)。"""
    binary = shutil.which(name)
    if not binary:
        return None, f"错误: 未检测到 {name}，请先安装 {name} ({install_hint})"
    return binary, None


# === pdm ===

def set_pdm_mirror(mirror_url):
    """设置 pdm 用户级镜像源。返回 (success, message)。"""
    pdm, err = _which('pdm', 'https://pdm-project.org')
    if not pdm:
        return False, err
    result = _run([pdm, 'config', 'pypi.url', mirror_url])
    if result.returncode != 0:
        return False, f"设置 pdm 镜像源失败: {result.stderr.strip()}"
    return True, f"成功设置 pdm 镜像源为 '{mirror_url}'（用户级配置）"


def unset_pdm_mirror():
    """移除 pdm 用户级镜像源配置。返回 (success, message)。"""
    pdm, err = _which('pdm', 'https://pdm-project.org')
    if not pdm:
        return False, err
    result = _run([pdm, 'config', '--delete', 'pypi.url'])
    if result.returncode != 0:
        # 未设置过时 pdm 会报错，视为无需操作
        return True, "pdm 未设置镜像源，无需操作"
    return True, "成功移除 pdm 镜像源配置，已恢复为默认源"


def get_pdm_mirror():
    """读取 pdm 当前镜像源，未安装或读取失败返回 None。"""
    pdm = shutil.which('pdm')
    if not pdm:
        return None
    result = _run([pdm, 'config', 'pypi.url'])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


# === poetry ===

def set_poetry_mirror(mirror_url):
    """在当前 poetry 项目中设置镜像源（项目级）。返回 (success, message)。"""
    poetry, err = _which('poetry', 'https://python-poetry.org')
    if not poetry:
        return False, err
    if not Path('pyproject.toml').exists():
        return False, ("错误: 当前目录没有 pyproject.toml。\n"
                       "poetry 的镜像源是项目级配置，请在 poetry 项目根目录下运行。")
    result = _run([poetry, 'source', 'add', '--priority=primary',
                   POETRY_SOURCE_NAME, mirror_url])
    if result.returncode != 0:
        return False, f"设置 poetry 镜像源失败: {result.stderr.strip()}"
    return True, (f"成功设置 poetry 镜像源为 '{mirror_url}'\n"
                  f"已写入当前项目 pyproject.toml（source 名称: {POETRY_SOURCE_NAME}）")


def unset_poetry_mirror():
    """移除当前 poetry 项目中由 cnpip 设置的镜像源。返回 (success, message)。"""
    poetry, err = _which('poetry', 'https://python-poetry.org')
    if not poetry:
        return False, err
    if not Path('pyproject.toml').exists():
        return True, "当前目录没有 pyproject.toml，无需操作"
    result = _run([poetry, 'source', 'remove', POETRY_SOURCE_NAME])
    if result.returncode != 0:
        # source 不存在时 poetry 会报错，视为无需操作
        return True, f"poetry 项目中未找到 cnpip 设置的镜像源（source: {POETRY_SOURCE_NAME}），无需操作"
    return True, "成功移除 poetry 镜像源配置，已恢复为默认源"


# === conda ===

def conda_set_commands(conda_bin, base_url):
    """生成配置 conda 镜像的命令序列（default_channels + conda-forge/pytorch 社区源）。"""
    base = base_url.rstrip('/')
    return [
        [conda_bin, 'config', '--set', 'show_channel_urls', 'yes'],
        [conda_bin, 'config', '--append', 'default_channels', f'{base}/pkgs/main'],
        [conda_bin, 'config', '--append', 'default_channels', f'{base}/pkgs/r'],
        [conda_bin, 'config', '--append', 'default_channels', f'{base}/pkgs/msys2'],
        [conda_bin, 'config', '--set', 'custom_channels.conda-forge', f'{base}/cloud'],
        [conda_bin, 'config', '--set', 'custom_channels.pytorch', f'{base}/cloud'],
    ]


def set_conda_mirror(base_url):
    """设置 conda 镜像源（写入 ~/.condarc）。返回 (success, message)。"""
    conda, err = _which('conda', 'https://docs.conda.io')
    if not conda:
        return False, err
    # 先清空旧的 default_channels，避免不同镜像源混杂（key 不存在时报错可忽略）
    _run([conda, 'config', '--remove-key', 'default_channels'])
    for cmd in conda_set_commands(conda, base_url):
        result = _run(cmd)
        if result.returncode != 0:
            return False, f"设置 conda 镜像源失败: {result.stderr.strip()}\n命令: {' '.join(cmd)}"
    return True, (f"成功设置 conda 镜像源为 '{base_url}'（写入 ~/.condarc）\n"
                  "已配置 default_channels 及 conda-forge/pytorch 社区源")


def unset_conda_mirror():
    """移除 conda 镜像源配置。返回 (success, message)。"""
    conda, err = _which('conda', 'https://docs.conda.io')
    if not conda:
        return False, err
    # key 不存在时 conda 会报错，均视为无需操作
    for key in ('default_channels', 'custom_channels'):
        _run([conda, 'config', '--remove-key', key])
    return True, "成功移除 conda 镜像源配置，已恢复为默认源"
