import subprocess
import sys
import os
import re
import json
import configparser
import argparse
import time
import statistics
import socket
import platform
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from .mirrors import MIRRORS, update_mirrors_from_remote
from .state import ManagedFileChange, atomic_write_text, restore_managed_file
from .integrations import (
    CONDA_MIRRORS,
    get_pdm_mirror,
    set_conda_mirror,
    set_pdm_mirror,
    set_poetry_mirror,
    unset_conda_mirror,
    unset_pdm_mirror,
    unset_poetry_mirror,
)
from . import __version__

MIN_PYTHON_VERSION = (3, 7)
MIRROR_PROBE_COUNT = 3
MIRROR_PROBE_PROJECT = "pip"
MIRROR_PROBE_USER_AGENT = f"cnpip/{__version__}"
CONDA_MIRROR_PROBE_PATH = "/pkgs/main/noarch/repodata.json"
if sys.version_info < MIN_PYTHON_VERSION:
    sys.stderr.write(f"错误: cnpip需要 Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 或更高版本。\n")
    sys.exit(1)


def measure_mirror_speed(name, url, probe_path=None):
    """对镜像的实际服务端点执行多次 GET，返回响应延迟中位数。"""
    probe_path = probe_path or f"/{MIRROR_PROBE_PROJECT}/"
    probe_url = f"{url.rstrip('/')}/{probe_path.lstrip('/')}"
    durations = []
    last_error = None
    for _ in range(MIRROR_PROBE_COUNT):
        try:
            start_time = time.monotonic()
            req = urllib.request.Request(
                probe_url,
                method='GET',
                headers={'Accept': 'text/html', 'User-Agent': MIRROR_PROBE_USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = response.read(64 * 1024)
                if not 200 <= response.status < 400:
                    last_error = f"Status {response.status}"
                    continue
                if not payload:
                    last_error = "Empty response"
                    continue
                durations.append((time.monotonic() - start_time) * 1000)
        except urllib.error.HTTPError as e:
            last_error = f"Status {e.code}"
        except urllib.error.URLError as e:
            last_error = "Timeout" if isinstance(e.reason, socket.timeout) else (str(e.reason) or "Error")
        except socket.timeout:
            last_error = "Timeout"
        except Exception as e:
            last_error = str(e) or "Error"
    if len(durations) < 2:
        return name, float('inf'), url, last_error or "Unstable"
    return name, round(statistics.median(durations), 2), url, None


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


def choose_fastest_mirror(mirrors, probe_path=None):
    """并发测速并返回最快的镜像名，全部失败返回 None。"""
    with ThreadPoolExecutor(max_workers=len(mirrors)) as executor:
        if probe_path is None:
            futures = [executor.submit(measure_mirror_speed, name, url)
                       for name, url in mirrors.items()]
        else:
            futures = [executor.submit(measure_mirror_speed, name, url, probe_path)
                       for name, url in mirrors.items()]
        results = [f.result() for f in futures]
    results.sort(key=lambda x: x[1])
    return next((name for name, _speed, _url, error in results if error is None), None)


def print_mirror_results(results):
    name_width = max(len(name) for name in MIRRORS.keys()) + 2
    time_width = 20
    url_width = max(len(url) for url in MIRRORS.values()) + 2

    header = f"{'镜像名称':<{name_width}}\t{'响应延迟/状态':<{time_width}}\t{'地址':<{url_width}}"
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


def needs_trusted_host(mirror_url):
    """trusted-host 会跳过 TLS 校验，只有 http 镜像才需要设置。"""
    return urlparse(mirror_url).scheme == 'http'


def redact_url(url):
    """诊断输出中隐藏 URL 内可能存在的用户名/密码。"""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if not parsed.username and not parsed.password:
            return url
        host = parsed.hostname or ''
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return parsed._replace(netloc=f"***@{host}").geturl()
    except (TypeError, ValueError):
        return "<已隐藏的无效 URL>"


def is_pip_installed():
    """检查 pip 是否安装"""
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--version'],
                       check=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, OSError):
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
        blocks = _get_uv_index_blocks(content)
        # 优先显示 cnpip 自己管理的 block；否则兼容旧版/用户配置中的默认 block。
        for block in blocks:
            if _uv_block_value(block, 'name') == 'cnpip':
                return _uv_block_value(block, 'url')
        for block in blocks:
            if _uv_block_value(block, 'default') == 'true':
                return _uv_block_value(block, 'url')
        return _uv_block_value(blocks[0], 'url') if blocks else None
    except Exception:
        return None


def _get_uv_index_blocks(content):
    """按文本边界提取 uv 的 [[index]] block，不解析或改写其他 TOML。"""
    lines = content.splitlines(keepends=True)
    blocks = []
    starts = [i for i, line in enumerate(lines) if line.strip() == '[[index]]']
    for start in starts:
        end = start + 1
        while end < len(lines) and not lines[end].strip().startswith('['):
            end += 1
        blocks.append(''.join(lines[start:end]))
    return blocks


def _uv_block_value(block, key):
    match = re.search(
        rf'^\s*{re.escape(key)}\s*=\s*(?:["\']([^"\']*)["\']|([^\s#]+))',
        block,
        re.MULTILINE,
    )
    return (match.group(1) if match and match.group(1) is not None
            else match.group(2) if match else None)


def _remove_cnpip_uv_blocks(content):
    """只移除带 name = \"cnpip\" 的 block，保留用户的其他 index。"""
    lines = content.splitlines(keepends=True)
    result = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != '[[index]]':
            result.append(lines[i])
            i += 1
            continue
        end = i + 1
        while end < len(lines) and not lines[end].strip().startswith('['):
            end += 1
        block = ''.join(lines[i:end])
        if _uv_block_value(block, 'name') != 'cnpip':
            result.extend(lines[i:end])
        i = end
    return ''.join(result)


def update_uv_config(mirror_url):
    """
    写入 uv 配置文件中的 index url。
    不引入外部依赖，直接操作文本。
    - 若文件不存在 → 创建并写入
    - 若存在但无 [[index]] → 追加
    - 只替换此前由 cnpip 写入的 named block，不删除用户的其他 index
    返回 (success: bool, message: str)
    """
    config_path = get_uv_config_path()
    change, error = ManagedFileChange.begin("uv:user", config_path)
    if not change:
        return False, error
    new_block = (f'[[index]]\nname = {json.dumps("cnpip")}\n'
                 f'url = {json.dumps(mirror_url)}\ndefault = true\n')
    try:
        if config_path.exists():
            content = config_path.read_text(encoding='utf-8', errors='replace')
            clean = _remove_cnpip_uv_blocks(content).lstrip('\n')
            new_content = new_block + ('\n' + clean if clean else '')
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            new_content = new_block

        atomic_write_text(config_path, new_content)
        success, error = change.commit()
        if not success:
            return False, error
        return True, f"成功设置 uv 镜像源为 '{mirror_url}'\n配置文件: {config_path}"
    except PermissionError:
        change.abort()
        return False, f"权限不足，无法写入 {config_path}"
    except Exception as e:
        change.abort()
        return False, f"写入 uv 配置失败: {e}"


def unset_uv_config():
    """
    恢复 cnpip 管理的 uv 配置，检测到用户漂移时拒绝覆盖。
    返回 (success: bool, message: str)
    """
    return restore_managed_file("uv:user", get_uv_config_path())


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
    elif scope == 'site':
        return Path(sys.prefix) / ('pip.ini' if system == 'Windows' else 'pip.conf')
    return None


def write_pip_config_directly(mirror_url, scope):
    """
    不依赖 pip 命令，直接用 configparser 写入 pip 配置文件。
    适用于 uvx 等无 pip 的环境中用户明确指定了作用域。
    scope: 'user' | 'global' | 'site'
    返回 (success: bool, message: str)
    """
    config_path = get_pip_config_path_for_scope(scope)
    if config_path is None:
        return False, f"不支持的作用域: {scope}"

    change, error = ManagedFileChange.begin(f"pip:{scope}", config_path)
    if not change:
        return False, error
    try:
        config = configparser.ConfigParser(interpolation=None)
        if config_path.exists():
            config.read(config_path, encoding='utf-8')
        if not config.has_section('global'):
            config.add_section('global')
        config.set('global', 'index-url', mirror_url)
        # trusted-host 会跳过 TLS 校验，仅对 http 镜像有必要；https 镜像应移除残留配置
        if needs_trusted_host(mirror_url):
            config.set('global', 'trusted-host', urlparse(mirror_url).netloc)
        elif config.has_option('global', 'trusted-host'):
            config.remove_option('global', 'trusted-host')
        config_path.parent.mkdir(parents=True, exist_ok=True)
        from io import StringIO
        stream = StringIO()
        config.write(stream)
        atomic_write_text(config_path, stream.getvalue())
        success, error = change.commit()
        if not success:
            return False, error
        return True, f"成功设置 pip 镜像源为 '{mirror_url}'\n配置文件: {config_path}"
    except PermissionError:
        change.abort()
        hint = get_global_scope_hint() if scope == 'global' else ''
        return False, f"权限不足，无法写入 {config_path}" + (f"\n{hint}" if hint else '')
    except Exception as e:
        change.abort()
        return False, f"写入失败: {e}"


def unset_pip_config_directly(scope):
    """
    不依赖 pip 命令，恢复 cnpip 管理的 pip 配置。
    scope: 'user' | 'global' | 'site'
    返回 (success: bool, message: str)
    """
    config_path = get_pip_config_path_for_scope(scope)
    if config_path is None:
        return False, f"不支持的作用域: {scope}"
    return restore_managed_file(f"pip:{scope}", config_path)


def update_pip_config(mirror_url, scope_args):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    set_trusted = needs_trusted_host(mirror_url)
    scope_str = " ".join(scope_args) if scope_args else "auto"
    scope_desc = get_scope_description(scope_args)

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip（可能是 uvx 环境）。")
        if '--venv' in scope_args:
            print("错误: --venv 在 uvx 临时环境中无意义，配置会随环境消失。")
            print("建议改用 --user 写入用户级 pip 配置，或 --uv 配置 uv 镜像源。")
            return False
        elif '--user' in scope_args or '--global' in scope_args or '--site' in scope_args:
            direct_scope = ('global' if '--global' in scope_args
                            else 'site' if '--site' in scope_args else 'user')
            print(f"正在直接写入 pip {scope_desc}（无需 pip 命令）...")
            success, msg = write_pip_config_directly(mirror_url, direct_scope)
            print(msg)
            return success
        else:
            # 自动模式兜底：优先配置 uv
            uv = detect_uv_binary()
            if uv:
                print("检测到 uv 已安装，自动配置 uv 镜像源...")
                success, msg = update_uv_config(mirror_url)
                print(msg)
                return success
            else:
                print(f"请复制以下命令在终端运行以生效配置 ({scope_desc}):")
                print(f"pip config set {scope_str} global.index-url {mirror_url}")
                if set_trusted:
                    print(f"pip config set {scope_str} global.trusted-host {host}")
        return False

    direct_scope = 'global' if '--global' in scope_args else ('site' if '--site' in scope_args else 'user')
    print(f"\n正在修改 [{scope_desc}] ...", flush=True)
    success, msg = write_pip_config_directly(mirror_url, direct_scope)
    print(msg)
    return success


def unset_pip_mirror(scope_args):
    """取消pip镜像源设置"""
    scope_str = " ".join(scope_args) if scope_args else "auto"

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip（可能是 uvx 环境）。")
        if '--venv' in scope_args:
            print("错误: --venv 在 uvx 临时环境中无意义。")
            return False
        elif '--user' in scope_args or '--global' in scope_args or '--site' in scope_args:
            direct_scope = ('global' if '--global' in scope_args
                            else 'site' if '--site' in scope_args else 'user')
            success, msg = unset_pip_config_directly(direct_scope)
            print(msg)
            return success
        else:
            print(f"请复制以下命令在终端运行以取消配置:")
            print(f"pip config unset {scope_str} global.index-url")
            print(f"pip config unset {scope_str} global.trusted-host")
        return False

    direct_scope = 'global' if '--global' in scope_args else ('site' if '--site' in scope_args else 'user')
    success, msg = unset_pip_config_directly(direct_scope)
    print(msg)
    return success


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
    print(f"当前镜像源: {redact_url(index_url) or '默认 (https://pypi.org/simple)'}")
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
        print(f"uv 镜像源: {redact_url(uv_index) or '默认 (https://pypi.org/simple)'}")
    else:
        print("uv: 未安装")

    # 其他包管理工具
    print("\n--- 其他包管理工具 ---")
    for tool in ('pdm', 'poetry', 'conda'):
        binary = shutil.which(tool)
        if not binary:
            print(f"{tool}: 未安装")
            continue
        try:
            ver_result = subprocess.run(
                [binary, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace'
            )
            print(f"{tool}: {ver_result.stdout.strip() or '已安装'}")
        except Exception:
            print(f"{tool}: 已安装 (版本获取失败)")
        if tool == 'pdm':
            pdm_mirror = get_pdm_mirror()
            if pdm_mirror:
                print(f"pdm 镜像源: {redact_url(pdm_mirror)}")


# === 交互式 set ===

def scan_available_tools():
    """扫描当前可配置镜像源的包管理工具，返回 (名称, 状态描述) 列表。"""
    tools = []
    if is_pip_installed():
        index_url, _ = get_pip_config()
        tools.append(('pip', f"当前源: {index_url or '默认'}"))
    if detect_uv_binary():
        tools.append(('uv', f"当前源: {get_uv_index_url() or '默认'}"))
    if shutil.which('pdm'):
        tools.append(('pdm', f"当前源: {get_pdm_mirror() or '默认'}"))
    if shutil.which('poetry') and Path('pyproject.toml').exists():
        tools.append(('poetry', '当前项目 (pyproject.toml)'))
    if shutil.which('conda'):
        tools.append(('conda', '用户级 (~/.condarc)'))
    return tools


def default_tool_selection(tool_names):
    """回车时的默认选择：与非交互行为一致（uvx 环境配 uv，否则配 pip）。"""
    if detect_environment() == 'uvx' and 'uv' in tool_names:
        return ['uv']
    if 'pip' in tool_names:
        return ['pip']
    return tool_names[:1]


def parse_tool_selection(raw, tool_names, default):
    """解析用户输入的工具选择（编号/a/回车），非法输入返回 None。"""
    raw = raw.strip().lower()
    if not raw:
        return list(default)
    if raw in ('a', 'all', '全部'):
        return list(tool_names)
    picked = []
    for token in re.split(r'[\s,，]+', raw):
        if not token.isdigit() or not 1 <= int(token) <= len(tool_names):
            return None
        name = tool_names[int(token) - 1]
        if name not in picked:
            picked.append(name)
    return picked or None


def apply_mirror_to_tool(tool, mirror_name, mirror_url, args):
    """将镜像源应用到单个工具，返回是否成功。"""
    if tool == 'pip':
        return update_pip_config(mirror_url, get_scope_args(args) if args else [])
    if tool == 'uv':
        success, msg = update_uv_config(mirror_url)
    elif tool == 'pdm':
        success, msg = set_pdm_mirror(mirror_url)
    elif tool == 'poetry':
        success, msg = set_poetry_mirror(mirror_url)
    elif tool == 'conda':
        # conda 镜像是独立服务，选中的 pypi 镜像不提供时单独测速
        conda_name = mirror_name if mirror_name in CONDA_MIRRORS else None
        if conda_name is None:
            print(f"镜像源 '{mirror_name}' 不提供 conda 镜像，正在对 conda 镜像单独测速...")
            conda_name = choose_fastest_mirror(
                CONDA_MIRRORS, probe_path=CONDA_MIRROR_PROBE_PATH)
            if conda_name is None:
                print("错误: 无法连接到任何 conda 镜像源")
                return False
            print(f"自动选择最快的 conda 镜像源: {conda_name}")
        success, msg = set_conda_mirror(CONDA_MIRRORS[conda_name])
    else:
        return False
    print(msg)
    return success


def run_interactive_set(args):
    """交互式 set：扫描已安装的包管理工具，让用户选择要配置哪些。"""
    tools = scan_available_tools()
    if not tools:
        print("错误: 未检测到任何可配置的包管理工具")
        sys.exit(1)

    tool_names = [name for name, _ in tools]
    print("检测到以下包管理工具:\n")
    for i, (name, desc) in enumerate(tools, 1):
        print(f"  {i}. {name:<8} {desc}")

    default = default_tool_selection(tool_names)
    default_str = ' '.join(str(tool_names.index(t) + 1) for t in default)
    prompt = (f"\n请选择要配置的工具（编号，空格分隔多个；a=全部；"
              f"回车={default_str} 即 {'/'.join(default)}）: ")
    try:
        while True:
            selection = parse_tool_selection(input(prompt), tool_names, default)
            if selection is not None:
                break
            print("输入无效，请输入列表中的编号（如: 1 3）、a 或直接回车")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(1)

    # 解析镜像名：未指定时测速选最快
    if args.mirror is None:
        results = list_mirrors()
        mirror_name = next((name for name, _speed, _url, error in results if error is None), None)
        if mirror_name is None:
            print("错误: 无法连接到任何镜像源")
            sys.exit(1)
        print(f"自动选择最快的镜像源: {mirror_name}")
    elif args.mirror not in MIRRORS:
        print(f"错误: 未找到镜像源 '{args.mirror}'")
        sys.exit(1)
    else:
        mirror_name = args.mirror

    mirror_url = MIRRORS[mirror_name]
    applied_tools = []
    for tool in selection:
        print(f"\n--- {tool} ---")
        if not apply_mirror_to_tool(tool, mirror_name, mirror_url, args):
            print("批量配置失败，正在回滚本次已完成的配置...")
            for applied_tool in reversed(applied_tools):
                success, message = rollback_mirror_from_tool(applied_tool, args)
                if not success:
                    print(f"回滚 {applied_tool} 失败: {message}")
            sys.exit(1)
        applied_tools.append(tool)
    sys.exit(0)


def rollback_mirror_from_tool(tool, args):
    """回滚交互式批量 set 中已经成功的单个工具。"""
    if tool == 'pip':
        return unset_pip_mirror(get_scope_args(args))
    if tool == 'uv':
        return unset_uv_config()
    if tool == 'pdm':
        return unset_pdm_mirror()
    if tool == 'poetry':
        return unset_poetry_mirror()
    if tool == 'conda':
        return unset_conda_mirror()
    return False, f"不支持回滚的工具: {tool}"


_COMMANDS = frozenset({"list", "set", "unset", "info", "sync", "update"})

_HELP_TEXT = """\
cnpip - 快速切换 pip 镜像源

用法:
  cnpip                   测速并自动换源
  cnpip <镜像源>          使用指定镜像（如 tuna, ustc, aliyun）
  cnpip list              测速所有镜像
  cnpip unset             恢复 cnpip 修改前的配置
  cnpip info              显示环境和配置信息
  cnpip sync              更新镜像源列表

选项:
  --uv                    配置 uv
  --pdm                   配置 pdm
  --poetry                配置 poetry（当前项目）
  --conda                 配置 conda
  --user                  用户级配置
  --global                系统级配置（需管理员权限）
  --venv                  当前虚拟环境配置
  -y, --yes               跳过交互
  -h, --help              显示此帮助信息"""


def _ensure_command():
    """argv 中没有识别到子命令时，默认插入 'set'。"""
    if len(sys.argv) < 2:
        sys.argv.insert(1, 'set')
        return
    first = sys.argv[1]
    if first in ('-h', '--help'):
        return
    if first not in _COMMANDS:
        sys.argv.insert(1, 'set')


def main():
    """主函数，解析命令行参数并执行相应操作"""
    _ensure_command()

    if '-h' in sys.argv[1:] or '--help' in sys.argv[1:]:
        print(_HELP_TEXT)
        sys.exit(0)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", choices=sorted(_COMMANDS))
    parser.add_argument("mirror", nargs="?")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--global", dest="global_", action="store_true")
    group.add_argument("--user", action="store_true")
    group.add_argument("--venv", "--site", dest="venv", action="store_true")
    group.add_argument("--uv", dest="uv", action="store_true")
    group.add_argument("--pdm", dest="pdm", action="store_true")
    group.add_argument("--poetry", dest="poetry", action="store_true")
    group.add_argument("--conda", dest="conda", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")

    args = parser.parse_args()

    if args.command == 'update':
        args.command = 'sync'

    if args.command == "list":
        results = list_mirrors()
        if not any(error is None for _name, _speed, _url, error in results):
            sys.exit(1)
        return
    elif args.command == "set":
        # 交互式：TTY 下未指定任何工具/作用域 flag 时，扫描环境让用户选择要配置的工具
        explicit_flags = (args.uv or args.pdm or args.poetry or args.conda
                          or args.global_ or args.user or args.venv)
        if (not explicit_flags and not args.yes
                and sys.stdin.isatty() and sys.stdout.isatty()):
            run_interactive_set(args)

        # conda 使用独立的镜像表（anaconda 镜像与 pypi 镜像是不同的服务）
        if args.conda:
            if args.mirror is None:
                print("未指定镜像源，即将对支持 conda 的镜像测速...")
                conda_mirror_name = choose_fastest_mirror(
                    CONDA_MIRRORS, probe_path=CONDA_MIRROR_PROBE_PATH)
                if conda_mirror_name is None:
                    print("错误: 无法连接到任何 conda 镜像源")
                    sys.exit(1)
                print(f"自动选择最快的镜像源: {conda_mirror_name}")
            elif args.mirror not in CONDA_MIRRORS:
                print(f"错误: 镜像源 '{args.mirror}' 不提供 conda 镜像")
                print(f"支持 conda 的镜像源: {', '.join(CONDA_MIRRORS)}")
                sys.exit(1)
            else:
                conda_mirror_name = args.mirror
            success, msg = set_conda_mirror(CONDA_MIRRORS[conda_mirror_name])
            print(msg)
            sys.exit(0 if success else 1)

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
        elif args.pdm:
            success, msg = set_pdm_mirror(mirror_url)
            print(msg)
            sys.exit(0 if success else 1)
        elif args.poetry:
            success, msg = set_poetry_mirror(mirror_url)
            print(msg)
            sys.exit(0 if success else 1)
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
                success = update_pip_config(mirror_url, scope_args)
                if not success:
                    sys.exit(1)
                return
    elif args.command == "unset":
        if args.uv:
            success, msg = unset_uv_config()
            print(msg)
            sys.exit(0 if success else 1)
        elif args.pdm:
            success, msg = unset_pdm_mirror()
            print(msg)
            sys.exit(0 if success else 1)
        elif args.poetry:
            success, msg = unset_poetry_mirror()
            print(msg)
            sys.exit(0 if success else 1)
        elif args.conda:
            success, msg = unset_conda_mirror()
            print(msg)
            sys.exit(0 if success else 1)
        else:
            scope_args = get_scope_args(args)
            success = unset_pip_mirror(scope_args)
            sys.exit(0 if success else 1)
    elif args.command == "info":
        show_info()
    elif args.command == "sync":
        print("正在从远程获取最新的镜像源列表...")
        success, msg = update_mirrors_from_remote()
        print(msg)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
