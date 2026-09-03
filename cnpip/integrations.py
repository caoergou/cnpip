"""pdm / poetry / conda 镜像源配置。

统一通过各工具自身的 CLI 修改配置，避免自行解析配置文件格式：
- pdm:    pdm config pypi.url <url>            （用户级全局配置）
- poetry: poetry source add cnpip <url>        （项目级 pyproject.toml，poetry 不支持全局镜像）
- conda:  conda config --prepend/--set/...     （用户级 ~/.condarc）
"""

import os
import shutil
import subprocess
from pathlib import Path

from .state import (
    ManagedFileChange,
    forget_managed_value,
    managed_value_to_restore,
    record_managed_value,
    restore_managed_file,
)

# poetry 项目中由 cnpip 管理的 source 名称
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
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _which(name, install_hint):
    """查找可执行文件，找不到返回 (None, 错误信息)。"""
    binary = shutil.which(name)
    if not binary:
        return None, f"错误: 未检测到 {name}，请先安装 {name} ({install_hint})"
    return binary, None


def _pdm_restore_command(pdm, value):
    return (
        [pdm, "config", "--delete", "pypi.url"]
        if value is None
        else [pdm, "config", "pypi.url", value]
    )


def _rollback_pdm_value(pdm, value):
    result = _run(_pdm_restore_command(pdm, value))
    if result.returncode != 0:
        return False, result.stderr.strip() or "命令执行失败"
    return True, None


# === pdm ===


def set_pdm_mirror(mirror_url):
    """设置 pdm 用户级镜像源。返回 (success, message)。"""
    pdm, err = _which("pdm", "https://pdm-project.org")
    if not pdm:
        return False, err
    before = get_pdm_mirror()
    result = _run([pdm, "config", "pypi.url", mirror_url])
    if result.returncode != 0:
        rollback_ok, rollback_error = _rollback_pdm_value(pdm, before)
        message = f"设置 pdm 镜像源失败: {result.stderr.strip() or '命令执行失败'}"
        if not rollback_ok:
            message += f"；回滚失败: {rollback_error}"
        return False, message
    after = get_pdm_mirror()
    if after != mirror_url:
        rollback_ok, rollback_error = _rollback_pdm_value(pdm, before)
        message = "设置 pdm 镜像源后验证失败，已尝试回滚"
        if not rollback_ok:
            message += f"；回滚失败: {rollback_error}"
        return False, message
    success, error = record_managed_value("pdm:user", before, after)
    if not success:
        rollback_ok, rollback_error = _rollback_pdm_value(pdm, before)
        message = error or "记录 pdm 镜像源的配置所有权失败"
        if not rollback_ok:
            message += f"；回滚失败: {rollback_error}"
        return False, message
    return True, f"成功设置 pdm 镜像源为 '{mirror_url}'（用户级配置）"


def unset_pdm_mirror():
    """移除 pdm 用户级镜像源配置。返回 (success, message)。"""
    current = get_pdm_mirror()
    success, previous, message = managed_value_to_restore("pdm:user", current)
    if not success or message:
        return success, message
    pdm, err = _which("pdm", "https://pdm-project.org")
    if not pdm:
        return False, err
    command = _pdm_restore_command(pdm, previous)
    result = _run(command)
    if result.returncode != 0:
        return False, f"恢复 pdm 镜像源失败: {result.stderr.strip()}"
    success, error = forget_managed_value("pdm:user")
    if not success:
        rollback_ok, rollback_error = _rollback_pdm_value(pdm, current)
        message = error or "清理 pdm 镜像源的配置所有权失败"
        if not rollback_ok:
            message += f"；回滚失败: {rollback_error}"
        return False, message
    return True, "已恢复 cnpip 修改前的 pdm 镜像源"


def get_pdm_mirror():
    """读取 pdm 当前镜像源，未安装或读取失败返回 None。"""
    pdm = shutil.which("pdm")
    if not pdm:
        return None
    result = _run([pdm, "config", "pypi.url"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


# === poetry ===


def set_poetry_mirror(mirror_url):
    """在当前 poetry 项目中设置镜像源（项目级）。返回 (success, message)。"""
    poetry, err = _which("poetry", "https://python-poetry.org")
    if not poetry:
        return False, err
    if not Path("pyproject.toml").exists():
        return False, (
            "错误: 当前目录没有 pyproject.toml。\n"
            "poetry 的镜像源是项目级配置，请在 poetry 项目根目录下运行。"
        )
    config_path = Path("pyproject.toml").resolve()
    change, error = ManagedFileChange.begin(f"poetry:{config_path}", config_path)
    if not change:
        return False, error
    result = _run(
        [poetry, "source", "add", "--priority=primary", POETRY_SOURCE_NAME, mirror_url]
    )
    if result.returncode != 0:
        change.abort()
        return False, f"设置 poetry 镜像源失败: {result.stderr.strip()}"
    try:
        content = config_path.read_bytes()
    except OSError as exc:
        change.abort()
        return False, f"设置 poetry 镜像源后无法读取配置: {exc}"
    if (
        POETRY_SOURCE_NAME.encode("utf-8") not in content
        or mirror_url.encode("utf-8") not in content
    ):
        change.abort()
        return False, "设置 poetry 镜像源后验证失败，已回滚"
    success, error = change.commit()
    if not success:
        return False, error
    return True, (
        f"成功设置 poetry 镜像源为 '{mirror_url}'\n"
        f"已写入当前项目 pyproject.toml（source 名称: {POETRY_SOURCE_NAME}）"
    )


def unset_poetry_mirror():
    """移除当前 poetry 项目中由 cnpip 设置的镜像源。返回 (success, message)。"""
    if not Path("pyproject.toml").exists():
        return True, "当前目录没有 pyproject.toml，无需操作"
    config_path = Path("pyproject.toml").resolve()
    return restore_managed_file(f"poetry:{config_path}", config_path)


# === conda ===


def conda_set_commands(conda_bin, base_url, config_path=None):
    """生成配置 conda 镜像的命令序列（default_channels + conda-forge/pytorch 社区源）。"""
    base = base_url.rstrip("/")
    config_args = ["--file", str(config_path)] if config_path is not None else []
    return [
        [conda_bin, "config", *config_args, "--set", "show_channel_urls", "yes"],
        [
            conda_bin,
            "config",
            *config_args,
            "--prepend",
            "default_channels",
            f"{base}/pkgs/main",
        ],
        [
            conda_bin,
            "config",
            *config_args,
            "--prepend",
            "default_channels",
            f"{base}/pkgs/r",
        ],
        [
            conda_bin,
            "config",
            *config_args,
            "--prepend",
            "default_channels",
            f"{base}/pkgs/msys2",
        ],
        [
            conda_bin,
            "config",
            *config_args,
            "--set",
            "custom_channels.conda-forge",
            f"{base}/cloud",
        ],
        [
            conda_bin,
            "config",
            *config_args,
            "--set",
            "custom_channels.pytorch",
            f"{base}/cloud",
        ],
    ]


def set_conda_mirror(base_url):
    """设置 conda 镜像源（写入 ~/.condarc）。返回 (success, message)。"""
    conda, err = _which("conda", "https://docs.conda.io")
    if not conda:
        return False, err
    config_path = get_conda_config_path()
    change, error = ManagedFileChange.begin("conda:user", config_path)
    if not change:
        return False, error
    # 使用 --prepend 保留用户已有 default_channels，同时让 cnpip 镜像优先。
    for cmd in conda_set_commands(conda, base_url, config_path):
        result = _run(cmd)
        if result.returncode != 0:
            change.abort()
            return (
                False,
                f"设置 conda 镜像源失败: {result.stderr.strip()}\n命令: {' '.join(cmd)}",
            )
    try:
        content = config_path.read_bytes()
    except OSError as exc:
        change.abort()
        return False, f"设置 conda 镜像源后无法读取配置: {exc}"
    if base_url.rstrip("/").encode("utf-8") not in content:
        change.abort()
        return False, "设置 conda 镜像源后验证失败，已回滚"
    success, error = change.commit()
    if not success:
        return False, error
    return True, (
        f"成功设置 conda 镜像源为 '{base_url}'（写入 ~/.condarc）\n"
        "已优先配置 default_channels，并配置 conda-forge/pytorch 社区源"
    )


def unset_conda_mirror():
    """移除 conda 镜像源配置。返回 (success, message)。"""
    return restore_managed_file("conda:user", get_conda_config_path())


def get_conda_config_path():
    """返回 conda 用户配置文件路径，尊重 CONDARC。"""
    configured = os.environ.get("CONDARC", "").strip()
    return Path(configured or (Path.home() / ".condarc")).expanduser().resolve()
