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
from . import __version__

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
    检测当前 Python 环境类型。
    返回: 'venv' 或 'system'
    """
    # 检查是否为虚拟环境 (标准 venv 或 conda)
    if sys.prefix != sys.base_prefix or os.environ.get('CONDA_PREFIX'):
        return 'venv'
    return 'system'


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
            check=False
        )
        if result.returncode != 0:
            return None, None

        output = result.stdout
        index_url = None
        trusted_host = None

        for line in output.splitlines():
            # 格式通常是 global.index-url='...'
            if 'global.index-url' in line:
                # 提取单引号或双引号中的内容，或者直接提取值
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    # 去除可能的引号
                    index_url = val.strip("'\"")
            elif 'global.trusted-host' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    trusted_host = val.strip("'\"")

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
    if env == 'venv':
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


def update_pip_config(mirror_url, scope_args):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    scope_str = " ".join(scope_args) if scope_args else "auto"
    scope_desc = get_scope_description(scope_args)

    if not is_pip_installed():
        print(f"\n检测到当前环境未安装 pip (可能是 uvx 环境)。")
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
    """显示诊断信息"""
    print(f"cnpip 版本: v{__version__}")
    print(f"Python 路径: {sys.executable}")

    try:
        pip_ver = subprocess.check_output([sys.executable, '-m', 'pip', '--version']).decode().strip()
        print(f"Pip 版本: {pip_ver}")
    except Exception as e:
        print(f"Pip 版本: 错误 ({e})")

    env_type = detect_environment()
    env_desc = "虚拟环境" if env_type == 'venv' else "系统环境"
    print(f"环境类型: {env_desc}")

    print("\n--- 当前 Pip 配置 ---")
    index_url, trusted_host = get_pip_config()

    if index_url:
        print(f"当前镜像源: {index_url}")
    else:
        print(f"当前镜像源: 默认 (https://pypi.org/simple)")

    if trusted_host:
        print(f"信任主机: {trusted_host}")
    else:
        print(f"信任主机: 未设置")


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
