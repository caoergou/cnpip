import subprocess
import sys
import os
import argparse
import time
import socket
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from .mirrors import MIRRORS, update_mirrors_from_remote

MIN_PYTHON_VERSION = (3, 6)
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


def detect_environment():
    """
    Detects the current Python environment type.
    Returns: 'venv' or 'system'
    """
    # Check for venv (standard or conda)
    if sys.prefix != sys.base_prefix or os.environ.get('CONDA_PREFIX'):
        return 'venv'
    return 'system'


def get_scope_args(args):
    """
    Determines the pip config arguments based on user flag and environment.
    """
    if args.global_:
        return ['--global']
    elif args.user:
        return ['--user']
    elif args.venv:
        return ['--site']

    # Auto-detection
    env = detect_environment()
    if env == 'venv':
        return ['--site']
    else:
        return ['--user']


def update_pip_config(mirror_url, scope_args):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    scope_str = " ".join(scope_args) if scope_args else "auto"

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip (可能是 uvx 环境)。")
        print(f"请复制以下命令在终端运行以生效配置:")
        print(f"pip config set {scope_str} global.index-url {mirror_url}")
        print(f"pip config set {scope_str} global.trusted-host {host}")
        return

    try:
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set'] + scope_args + ['global.index-url', mirror_url], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set'] + scope_args + ['global.trusted-host', host], check=True)
        print(f"成功设置 pip 镜像源为 '{mirror_url}'，并添加 trusted-host '{host}'")
    except subprocess.CalledProcessError:
        print(f"\n警告: 无法自动修改 pip 配置文件 (可能是权限问题)。")
        if '--global' in scope_args:
             print("尝试使用 --global 但失败，请确保以管理员身份运行。")
        print(f"请尝试手动运行以下命令:")
        print(f"pip config set {scope_str} global.index-url {mirror_url}")
        print(f"pip config set {scope_str} global.trusted-host {host}")


def unset_pip_mirror(scope_args) -> None:
    """取消pip镜像源设置"""
    scope_str = " ".join(scope_args) if scope_args else "auto"

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip (可能是 uvx 环境)。")
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


def show_info():
    """Shows diagnostic information"""
    print(f"Python Executable: {sys.executable}")

    try:
        pip_ver = subprocess.check_output([sys.executable, '-m', 'pip', '--version']).decode().strip()
        print(f"Pip Version: {pip_ver}")
    except Exception as e:
        print(f"Pip Version: Error ({e})")

    env_type = detect_environment()
    print(f"Environment Type: {env_type}")

    print("\n--- Pip Configuration (pip config list -v) ---")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'list', '-v'], check=False)
    except Exception as e:
        print(f"Error listing config: {e}")


def main():
    """主函数，解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(description="轻松管理 pip 镜像源。")
    parser.add_argument("command", choices=["list", "set", "unset", "info", "update"], help="要执行的命令")
    parser.add_argument("mirror", nargs="?", help="要设置的镜像源名称 (仅用于 'set' 命令)")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--global", dest="global_", action="store_true", help="设置全局系统配置")
    group.add_argument("--user", action="store_true", help="设置当前用户配置")
    group.add_argument("--venv", "--site", dest="venv", action="store_true", help="设置当前虚拟环境配置")

    args = parser.parse_args()

    if args.command == "list":
        list_mirrors()
    elif args.command == "set":
        scope_args = get_scope_args(args)
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
        update_pip_config(mirror_url, scope_args)
    elif args.command == "unset":
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
