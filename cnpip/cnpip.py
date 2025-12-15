import subprocess
import sys
import argparse
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from .mirrors import MIRRORS

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
                return name, round((end_time - start_time) * 1000, 2), url
            else:
                return name, None, url
    except Exception:
        # Catching all exceptions including timeout and connection errors
        return name, None, url


def list_mirrors():
    """展示镜像源列表并测速"""
    start_time = time.monotonic()
    print("正在测速，请稍候...")

    with ThreadPoolExecutor(max_workers=len(MIRRORS)) as executor:
        futures = [executor.submit(measure_mirror_speed, name, url) for name, url in MIRRORS.items()]
        results = [f.result() for f in futures]

    total_time = round((time.monotonic() - start_time) * 1000, 2)
    # sort by speed (None last)
    results.sort(key=lambda x: (x[1] is None, x[1]))
    print_mirror_results(results)
    print(f"\n测速总耗时: {total_time} ms")
    return results


def print_mirror_results(results):
    name_width = max(len(name) for name in MIRRORS.keys()) + 2
    time_width = 10
    url_width = max(len(url) for url in MIRRORS.values()) + 2

    header = f"{'镜像名称':<{name_width}}\t{'耗时(ms)':<{time_width}}\t{'地址':<{url_width}}"
    print(header)
    print("-" * (name_width + time_width + url_width))

    for name, speed, url in results:
        if speed is not None:
            print(f"{name:<{name_width}}\t{speed:<{time_width}.2f}\t{url:<{url_width}}")
        else:
            print(f"{name:<{name_width}}\t{'error':<{time_width}}\t{url:<{url_width}}")


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


def update_pip_config(mirror_url):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    try:
        # 尝试设置用户级别的配置 (Adding --user)
        # Note: If running inside a venv, pip config set usually defaults to user unless environment var is set
        # However, to be persistent across uvx sessions, we should prefer User configuration.
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set', '--user', 'global.index-url', mirror_url], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set', '--user', 'global.trusted-host', host], check=True)
        print(f"成功设置 pip 镜像源为 '{mirror_url}'，并添加 trusted-host '{host}'")
    except subprocess.CalledProcessError:
        print(f"\n警告: 无法自动修改 pip 配置文件 (可能是权限问题)。")
        print(f"请手动运行以下命令设置镜像源:")
        print(f"pip config set global.index-url {mirror_url}")
        print(f"pip config set global.trusted-host {host}")


def unset_pip_mirror() -> None:
    """取消pip镜像源设置"""
    try:
        # Also using --user here
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset', '--user', 'global.index-url'], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset', '--user', 'global.trusted-host'], check=True)
        print("成功取消 pip 镜像源设置，已恢复为默认源")
    except subprocess.CalledProcessError as e:
         print(f"取消 pip 镜像源设置时出错: {e}")


def main():
    """主函数，解析命令行参数并执行相应操作"""
    if not is_pip_installed():
        print("错误: 未找到 pip，无法设置镜像源")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="轻松管理 pip 镜像源。")
    parser.add_argument("command", choices=["list", "set", "unset"], help="要执行的命令")
    parser.add_argument("mirror", nargs="?", help="要设置的镜像源名称 (仅用于 'set' 命令)")

    args = parser.parse_args()

    if args.command == "list":
        list_mirrors()
    elif args.command == "set":
        if args.mirror is None:
            print("未指定镜像源，即将测速并选择最快的镜像源...")
            results = list_mirrors()

            fastest_mirror = next((name for name, speed, url in results if speed is not None), None)

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
        update_pip_config(mirror_url)
    elif args.command == "unset":
        unset_pip_mirror()
        sys.exit(0)


if __name__ == "__main__":
    main()
