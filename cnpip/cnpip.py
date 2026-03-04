import subprocess
import sys
import os
import re
import argparse
import time
import socket
import platform
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from .mirrors import MIRRORS, update_mirrors_from_remote
from . import __version__

MIN_PYTHON_VERSION = (3, 7)
if sys.version_info < MIN_PYTHON_VERSION:
    sys.stderr.write(f"错误: cnpip需要 Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 或更高版本。\n")
    sys.exit(1)


def measure_mirror_speed(name, url):
    """测速函数"""
    try:
        start_time = time.monotonic()
        # Use a short timeout to fail fast
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5) as response:
            if 200 <= response.status < 400:
                end_time = time.monotonic()
                duration = round((end_time - start_time) * 1000, 2)
                return name, duration, url, None
            else:
                return name, float('inf'), url, f"Status {response.status}"
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if isinstance(e.reason, socket.timeout):
             reason = "Timeout"
        return name, float('inf'), url, reason or "Error"
    except socket.timeout:
        return name, float('inf'), url, "Timeout"
    except Exception as e:
        return name, float('inf'), url, str(e) or "Error"


def list_mirrors():
    """展示镜像源列表并测速"""
    start_time = time.monotonic()
    print("正在测速，请稍候...")

    with ThreadPoolExecutor(max_workers=len(MIRRORS)) as executor:
        futures = [executor.submit(measure_mirror_speed, name, url) for name, url in MIRRORS.items()]
        results = [f.result() for f in futures]

    total_time = round((time.monotonic() - start_time) * 1000, 2)
    # sort by speed (None last)
    results.sort(key=lambda x: x[1])
    print_mirror_results(results)
    print(f"\n测速总耗时: {total_time} ms")
    return results


def print_mirror_results(results):
    name_width = max(len(name) for name in MIRRORS.keys()) + 2
    time_width = 20
    url_width = max(len(url) for url in MIRRORS.values()) + 2

    header = f"{'镜像名称':<{name_width}}\t{'耗时/状态':<{time_width}}\t{'地址':<{url_width}}"
    print(header)
    print("-" * (name_width + time_width + url_width))

    for name, speed, url, error in results:
        if error is None:
            speed_str = f"{speed:.2f} ms"
            print(f"{name:<{name_width}}\t{speed_str:<{time_width}}\t{url:<{url_width}}")
        else:
            # Truncate error if too long
            error_msg = (error[:17] + '..') if len(error) > 19 else error
            print(f"{name:<{name_width}}\t{error_msg:<{time_width}}\t{url:<{url_width}}")


def is_pip_installed():
    """检查 pip 是否安装"""
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--version'],
                       check=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def detect_windows_python_source():
    """
    Windows 专用：根据 sys.executable 路径特征检测 Python 安装方式。
    返回: 'store' | 'uv' | 'conda' | 'pyenv' | 'scoop' | 'official' | 'unknown'
    """
    exe = sys.executable.replace('\\', '/').lower()
    if 'microsoft/windowsapps' in exe or '/windowsapps/' in exe:
        return 'store'
    if '/uv/python/' in exe:
        return 'uv'
    if 'conda' in exe or 'miniconda' in exe or 'anaconda' in exe:
        return 'conda'
    if '.pyenv' in exe or 'pyenv-win' in exe:
        return 'pyenv'
    if '/scoop/' in exe:
        return 'scoop'
    if 'appdata/local/programs/python' in exe:
        return 'official'
    return 'unknown'


WINDOWS_PYTHON_SOURCE_NAMES = {
    'store':    'Windows 商店 (Microsoft Store)',
    'uv':       'uv 管理的 Python',
    'conda':    'Conda/Miniconda',
    'pyenv':    'pyenv-win',
    'scoop':    'Scoop',
    'official': '官方安装包 (python.org)',
    'unknown':  '未知',
}


def detect_environment():
    """
    检测当前 Python 环境类型。
    返回: 'uvx' | 'uv_venv' | 'conda' | 'pipx' | 'venv' | 'system'
    """
    exe = sys.executable.replace('\\', '/')

    # 1. uvx 临时工具环境（uv tool run / uvx）
    uv_tool_dir = os.environ.get('UV_TOOL_DIR', '')
    if uv_tool_dir and uv_tool_dir.replace('\\', '/') in exe:
        return 'uvx'
    if '/uv/tools/' in exe:
        return 'uvx'

    # 2. conda 环境（优先于 venv，因为 conda 也会改 sys.prefix）
    if os.environ.get('CONDA_PREFIX'):
        return 'conda'

    # 3. pipx 隔离环境
    if platform.system() == 'Windows':
        localappdata = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        default_pipx_home = str(Path(localappdata) / 'pipx')
    else:
        default_pipx_home = str(Path.home() / '.local' / 'pipx')
    pipx_home = os.environ.get('PIPX_HOME', default_pipx_home).replace('\\', '/')
    if pipx_home in exe:
        return 'pipx'

    # 4. 虚拟环境
    if sys.prefix != sys.base_prefix:
        # 检测是否由 uv 创建（pyvenv.cfg 中含有 uv = ...）
        pyvenv_cfg = Path(sys.prefix) / 'pyvenv.cfg'
        if pyvenv_cfg.exists():
            try:
                cfg_content = pyvenv_cfg.read_text(encoding='utf-8', errors='replace')
                if re.search(r'^uv\s*=', cfg_content, re.MULTILINE):
                    return 'uv_venv'
            except Exception:
                pass
        return 'venv'

    return 'system'


ENV_DESCRIPTIONS = {
    'uvx':     'uvx 临时工具环境',
    'uv_venv': 'uv 管理的虚拟环境',
    'conda':   'Conda 环境',
    'pipx':    'pipx 隔离环境',
    'venv':    '虚拟环境',
    'system':  '系统环境',
}


def get_pip_config():
    """
    获取当前 pip 配置 (index-url 和 trusted-host)
    """
    try:
        # 使用 subprocess 获取 pip config list 输出
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'config', 'list'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        if result.returncode != 0:
            return None, None

        output = result.stdout
        index_url = None
        trusted_host = None

        for line in output.splitlines():
            # 格式: [section].index-url='...'，前缀可能是 global/user/site/install 等
            if '.index-url' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip().strip("'\"")
                    if val:
                        index_url = val
            elif '.trusted-host' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip().strip("'\"")
                    if val:
                        trusted_host = val

        return index_url, trusted_host
    except Exception:
        return None, None


def get_scope_args(args):
    """
    根据用户标志和环境确定 pip 配置参数。
    """
    if args.global_:
        return ['--global']
    elif args.user:
        return ['--user']
    elif args.venv:
        return ['--site']

    # 自动检测
    env = detect_environment()
    if env in ('venv', 'uv_venv', 'conda'):
        return ['--site']
    else:
        return ['--user']


def get_scope_description(scope_args):
    """
    返回配置范围的中文描述
    """
    if not scope_args:
        return "自动"
    if '--global' in scope_args:
        return "系统全局配置"
    if '--user' in scope_args:
        return "当前用户配置"
    if '--site' in scope_args:
        return "虚拟环境配置"
    return " ".join(scope_args)


def get_global_scope_hint():
    """根据平台返回 --global 权限不足时的针对性提示"""
    system = platform.system()
    if system in ('Linux', 'Darwin'):
        return "请尝试使用 sudo 运行: sudo cnpip set --global"
    elif system == 'Windows':
        source = detect_windows_python_source()
        if source == 'store':
            return ("检测到 Windows 商店版 Python，全局配置受沙盒限制。\n"
                    "建议改用 --user: cnpip set --user")
        else:
            return "请以管理员身份运行 PowerShell 或命令提示符后重试"
    return "请检查是否有足够的文件系统权限"


# === uv 相关 ===

def detect_uv_binary():
    """查找 uv 可执行文件路径，找不到返回 None。"""
    return shutil.which('uv')


def get_uv_config_path():
    """
    返回 uv 用户级配置文件路径（跨平台）。
    Linux/macOS: ~/.config/uv/uv.toml（遵循 XDG_CONFIG_HOME）
    Windows:     %APPDATA%/uv/uv.toml
    """
    system = platform.system()
    if system == 'Windows':
        appdata = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
        return Path(appdata) / 'uv' / 'uv.toml'
    else:
        xdg_config = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        return Path(xdg_config) / 'uv' / 'uv.toml'


def get_uv_index_url():
    """
    读取 uv 配置文件中的 default index url。
    不引入外部 TOML 依赖，使用正则解析（格式固定）。
    """
    config_path = get_uv_config_path()
    if not config_path.exists():
        return None
    try:
        content = config_path.read_text(encoding='utf-8', errors='replace')
        in_index_block = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == '[[index]]':
                in_index_block = True
                continue
            if in_index_block:
                if stripped.startswith('['):
                    break  # 进入了下一个块
                match = re.match(r'^url\s*=\s*["\'](.+)["\']', stripped)
                if match:
                    return match.group(1)
        return None
    except Exception:
        return None


def update_uv_config(mirror_url):
    """
    写入 uv 配置文件中的 index url。
    不引入外部依赖，直接操作文本。
    - 若文件不存在 → 创建并写入
    - 若存在但无 [[index]] → 追加
    - 若存在且有 [[index]] → 移除旧块再追加（支持多个 [[index]]）
    返回 (success: bool, message: str)
    """
    config_path = get_uv_config_path()
    new_block = f'[[index]]\nurl = "{mirror_url}"\ndefault = true\n'
    try:
        if config_path.exists():
            content = config_path.read_text(encoding='utf-8', errors='replace')
            if '[[index]]' in content:
                # 移除所有现有 [[index]] 块
                lines = content.splitlines(keepends=True)
                new_lines = []
                i = 0
                while i < len(lines):
                    if lines[i].strip() == '[[index]]':
                        i += 1
                        while i < len(lines):
                            if lines[i].strip().startswith('['):
                                break
                            i += 1
                    else:
                        new_lines.append(lines[i])
                        i += 1
                clean = ''.join(new_lines).rstrip('\n')
                new_content = (clean + '\n\n' + new_block) if clean else new_block
            else:
                new_content = content.rstrip('\n') + '\n\n' + new_block
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            new_content = new_block

        config_path.write_text(new_content, encoding='utf-8')
        return True, f"成功设置 uv 镜像源为 '{mirror_url}'\n配置文件: {config_path}"
    except PermissionError:
        return False, f"权限不足，无法写入 {config_path}"
    except Exception as e:
        return False, f"写入 uv 配置失败: {e}"


def unset_uv_config():
    """
    从 uv 配置文件中移除所有 [[index]] 块。
    返回 (success: bool, message: str)
    """
    config_path = get_uv_config_path()
    if not config_path.exists():
        return True, "uv 配置文件不存在，无需操作"
    try:
        content = config_path.read_text(encoding='utf-8', errors='replace')
        if '[[index]]' not in content:
            return True, "uv 配置中未设置 index，无需操作"

        lines = content.splitlines(keepends=True)
        new_lines = []
        i = 0
        while i < len(lines):
            if lines[i].strip() == '[[index]]':
                i += 1
                while i < len(lines):
                    if lines[i].strip().startswith('['):
                        break
                    i += 1
            else:
                new_lines.append(lines[i])
                i += 1

        config_path.write_text(''.join(new_lines), encoding='utf-8')
        return True, f"成功移除 uv 镜像源配置\n配置文件: {config_path}"
    except Exception as e:
        return False, f"移除 uv 配置失败: {e}"


def get_pip_config_path_for_scope(scope):
    """
    返回指定作用域的 pip 配置文件写入路径（跨平台）。
    scope: 'user' | 'global'
    pip 配置文件是普通 INI 文件，无需 pip 命令即可直接读写。
    """
    system = platform.system()
    if scope == 'user':
        if system == 'Windows':
            appdata = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
            return Path(appdata) / 'pip' / 'pip.ini'
        elif system == 'Darwin':
            return Path.home() / 'Library' / 'Application Support' / 'pip' / 'pip.conf'
        else:
            xdg = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
            return Path(xdg) / 'pip' / 'pip.conf'
    elif scope == 'global':
        if system == 'Windows':
            programdata = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
            return Path(programdata) / 'pip' / 'pip.ini'
        elif system == 'Darwin':
            return Path('/Library/Application Support/pip/pip.conf')
        else:
            return Path('/etc/pip.conf')
    return None


def write_pip_config_directly(mirror_url, scope):
    """
    不依赖 pip 命令，直接用 configparser 写入 pip 配置文件。
    适用于 uvx 等无 pip 的环境中用户明确指定了 --user / --global。
    scope: 'user' | 'global'
    返回 (success: bool, message: str)
    """
    import configparser
    config_path = get_pip_config_path_for_scope(scope)
    if config_path is None:
        return False, f"不支持的作用域: {scope}"

    host = urlparse(mirror_url).netloc
    config = configparser.ConfigParser()
    if config_path.exists():
        config.read(config_path, encoding='utf-8')
    if not config.has_section('global'):
        config.add_section('global')
    config.set('global', 'index-url', mirror_url)
    config.set('global', 'trusted-host', host)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
        return True, f"成功设置 pip 镜像源为 '{mirror_url}'\n配置文件: {config_path}"
    except PermissionError:
        hint = get_global_scope_hint() if scope == 'global' else ''
        return False, f"权限不足，无法写入 {config_path}" + (f"\n{hint}" if hint else '')
    except Exception as e:
        return False, f"写入失败: {e}"


def unset_pip_config_directly(scope):
    """
    不依赖 pip 命令，直接从 pip 配置文件中移除镜像源配置。
    scope: 'user' | 'global'
    返回 (success: bool, message: str)
    """
    import configparser
    config_path = get_pip_config_path_for_scope(scope)
    if config_path is None:
        return False, f"不支持的作用域: {scope}"
    if not config_path.exists():
        return True, "pip 配置文件不存在，无需操作"

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    changed = False
    for key in ('index-url', 'trusted-host'):
        if config.has_option('global', key):
            config.remove_option('global', key)
            changed = True

    if not changed:
        return True, "pip 配置中未设置镜像源，无需操作"

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
        return True, f"成功移除 pip 镜像源配置\n配置文件: {config_path}"
    except PermissionError:
        return False, f"权限不足，无法写入 {config_path}"
    except Exception as e:
        return False, f"移除失败: {e}"


def update_pip_config(mirror_url, scope_args):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    scope_str = " ".join(scope_args) if scope_args else "auto"
    scope_desc = get_scope_description(scope_args)

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip（可能是 uvx 环境）。")
        if '--venv' in scope_args:
            print("错误: --venv 在 uvx 临时环境中无意义，配置会随环境消失。")
            print("建议改用 --user 写入用户级 pip 配置，或 --uv 配置 uv 镜像源。")
            return
        elif '--user' in scope_args or '--global' in scope_args:
            direct_scope = 'global' if '--global' in scope_args else 'user'
            print(f"正在直接写入 pip {scope_desc}（无需 pip 命令）...")
            success, msg = write_pip_config_directly(mirror_url, direct_scope)
            print(msg)
        else:
            # 自动模式兜底：优先配置 uv
            uv = detect_uv_binary()
            if uv:
                print("检测到 uv 已安装，自动配置 uv 镜像源...")
                success, msg = update_uv_config(mirror_url)
                print(msg)
            else:
                print(f"请复制以下命令在终端运行以生效配置 ({scope_desc}):")
                print(f"pip config set {scope_str} global.index-url {mirror_url}")
                print(f"pip config set {scope_str} global.trusted-host {host}")
        return

    print(f"\n正在修改 [{scope_desc}] ...", flush=True)

    # 获取修改前配置
    old_index, old_host = get_pip_config()
    print(f"修改前配置: index-url='{old_index or '默认'}', trusted-host='{old_host or '未设置'}'", flush=True)

    try:
        # 注意: 这里的 subprocess output 被默认显示出来了，可能需要隐藏，或者保留以显示 pip 的反馈
        # 用户的需求是清晰的输出，pip config set 会输出 "Writing to ..."
        # 我们保留它，因为它告诉用户文件位置
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set'] + scope_args + ['global.index-url', mirror_url], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set'] + scope_args + ['global.trusted-host', host], check=True)

        # 获取修改后配置
        new_index, new_host = get_pip_config()
        print(f"修改后配置: index-url='{new_index or '默认'}', trusted-host='{new_host or '未设置'}'")

        print(f"成功设置 pip 镜像源为 '{mirror_url}'")
    except subprocess.CalledProcessError:
        print(f"\n警告: 无法自动修改 pip 配置文件 (可能是权限问题)。")
        if '--global' in scope_args:
            print(get_global_scope_hint())
        print(f"\n请尝试手动运行以下命令:")
        print(f"pip config set {scope_str} global.index-url {mirror_url}")
        print(f"pip config set {scope_str} global.trusted-host {host}")


def unset_pip_mirror(scope_args) -> None:
    """取消pip镜像源设置"""
    scope_str = " ".join(scope_args) if scope_args else "auto"

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip（可能是 uvx 环境）。")
        if '--venv' in scope_args:
            print("错误: --venv 在 uvx 临时环境中无意义。")
            return
        elif '--user' in scope_args or '--global' in scope_args:
            direct_scope = 'global' if '--global' in scope_args else 'user'
            success, msg = unset_pip_config_directly(direct_scope)
            print(msg)
        else:
            print(f"请复制以下命令在终端运行以取消配置:")
            print(f"pip config unset {scope_str} global.index-url")
            print(f"pip config unset {scope_str} global.trusted-host")
        return

    try:
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset'] + scope_args + ['global.index-url'], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset'] + scope_args + ['global.trusted-host'], check=True)
        print("成功取消 pip 镜像源设置，已恢复为默认源")
    except subprocess.CalledProcessError as e:
         print(f"取消 pip 镜像源设置时出错: {e}")


def get_pip_config_files():
    """
    通过 pip config list -v 获取实际配置文件路径列表。
    适用于所有平台和 Python 安装方式。
    """
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'config', 'list', '-v'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        # pip -v 输出配置文件路径到 stderr
        output = result.stderr + result.stdout
        files = []
        for line in output.splitlines():
            # 格式: "For variant 'global', will try loading '/path/to/pip.conf'"
            match = re.search(r"will try loading '([^']+)'", line)
            if match:
                files.append(match.group(1))
        return files
    except Exception:
        return []


def show_info():
    """显示诊断信息"""
    system = platform.system()

    print(f"cnpip 版本: v{__version__}")
    print(f"Python 路径: {sys.executable}")
    print(f"操作系统: {system} {platform.release()}")

    # Windows 额外显示 Python 安装来源
    if system == 'Windows':
        source = detect_windows_python_source()
        source_name = WINDOWS_PYTHON_SOURCE_NAMES.get(source, '未知')
        print(f"Python 安装来源: {source_name}")

    try:
        pip_ver_result = subprocess.run(
            [sys.executable, '-m', 'pip', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace'
        )
        pip_ver = pip_ver_result.stdout.strip()
        print(f"Pip 版本: {pip_ver}")
    except Exception as e:
        print(f"Pip 版本: 错误 ({e})")

    env_type = detect_environment()
    env_desc = ENV_DESCRIPTIONS.get(env_type, env_type)
    print(f"环境类型: {env_desc}")

    print("\n--- 当前 Pip 配置 ---")
    index_url, trusted_host = get_pip_config()
    print(f"当前镜像源: {index_url or '默认 (https://pypi.org/simple)'}")
    print(f"信任主机: {trusted_host or '未设置'}")

    # 显示实际配置文件路径
    config_files = get_pip_config_files()
    if config_files:
        print("配置文件路径:")
        for f in config_files:
            print(f"  {f}")

    # uv 信息
    print("\n--- uv 信息 ---")
    uv_bin = detect_uv_binary()
    if uv_bin:
        try:
            uv_ver_result = subprocess.run(
                [uv_bin, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace'
            )
            uv_ver = uv_ver_result.stdout.strip()
            print(f"uv 版本: {uv_ver}")
        except Exception:
            print("uv 版本: 获取失败")

        uv_config_path = get_uv_config_path()
        print(f"uv 配置文件: {uv_config_path}")

        uv_index = get_uv_index_url()
        print(f"uv 镜像源: {uv_index or '默认 (https://pypi.org/simple)'}")
    else:
        print("uv: 未安装")


def main():
    """主函数，解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(description="轻松管理 pip 镜像源。")
    parser.add_argument("command", choices=["list", "set", "unset", "info", "update"], help="要执行的命令")
    parser.add_argument("mirror", nargs="?", help="要设置的镜像源名称 (仅用于 'set' 命令)")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--global", dest="global_", action="store_true", help="设置全局系统配置")
    group.add_argument("--user", action="store_true", help="设置当前用户配置")
    group.add_argument("--venv", "--site", dest="venv", action="store_true", help="设置当前虚拟环境配置")
    group.add_argument("--uv", dest="uv", action="store_true", help="配置 uv 镜像源 (写入 uv.toml，不修改 pip)")

    args = parser.parse_args()

    if args.command == "list":
        list_mirrors()
    elif args.command == "set":
        # 解析镜像名（set/unset 共用）
        if args.mirror is None:
            print("未指定镜像源，即将测速并选择最快的镜像源...")
            results = list_mirrors()
            fastest_mirror = next((name for name, speed, url, error in results if error is None), None)
            if fastest_mirror is None:
                print("错误: 无法连接到任何镜像源")
                sys.exit(1)
            mirror_name = fastest_mirror
            print(f"自动选择最快的镜像源: {mirror_name}")
        else:
            mirror_name = args.mirror

        if mirror_name not in MIRRORS:
            print(f"错误: 未找到镜像源 '{mirror_name}'")
            sys.exit(1)

        mirror_url = MIRRORS[mirror_name]

        if args.uv:
            # 显式配置 uv
            if not detect_uv_binary():
                print("错误: 未检测到 uv，请先安装 uv (https://docs.astral.sh/uv/)")
                sys.exit(1)
            success, msg = update_uv_config(mirror_url)
            print(msg)
            if not success:
                sys.exit(1)
        else:
            env = detect_environment()
            if env == 'uvx' and not args.global_ and not args.user and not args.venv:
                # uvx 环境：自动走 uv 配置路径
                uv = detect_uv_binary()
                if uv:
                    print("检测到 uvx 环境，自动配置 uv 镜像源...")
                    success, msg = update_uv_config(mirror_url)
                    print(msg)
                    if not success:
                        sys.exit(1)
                else:
                    print("检测到 uvx 环境但未找到 uv 可执行文件，请手动配置")
                    sys.exit(1)
            else:
                scope_args = get_scope_args(args)
                update_pip_config(mirror_url, scope_args)
    elif args.command == "unset":
        if args.uv:
            success, msg = unset_uv_config()
            print(msg)
            sys.exit(0 if success else 1)
        else:
            scope_args = get_scope_args(args)
            unset_pip_mirror(scope_args)
            sys.exit(0)
    elif args.command == "info":
        show_info()
    elif args.command == "update":
        print("正在从远程获取最新的镜像源列表...")
        success, msg = update_mirrors_from_remote()
        print(msg)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
