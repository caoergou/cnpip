import os
import sys
import argparse
import time
import configparser
import asyncio
from urllib.parse import urlparse

MIN_PYTHON_VERSION = (3, 6)
if sys.version_info < MIN_PYTHON_VERSION:
    sys.stderr.write(f"错误: cnpip需要 Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 或更高版本。\n")
    sys.stderr.write("您也可直接使用以下命令快速安装包:\n")
    sys.stderr.write(">\tpip install [package_name] -i https://pypi.tuna.tsinghua.edu.cn/simple \n")
    sys.exit(1)

try:
    import aiohttp

    ASYNC_SUPPORTED = True
except ImportError:
    import requests

    ASYNC_SUPPORTED = False

from .mirrors import MIRRORS


def get_pip_config_path():
    if os.name == 'nt':  # Windows
        appdata = os.getenv('APPDATA')
        if appdata and os.path.exists(appdata):
            return os.path.join(appdata, 'pip', 'pip.ini')
        else:
            return os.path.expanduser('~\\pip\\pip.ini')
    else:  # Linux and macOS
        return os.path.expanduser('~/.pip/pip.conf')


# 异步测速函数
if ASYNC_SUPPORTED:
    async def test_mirror_speed_async(session, name, url):
        try:
            start_time = time.time()
            async with session.head(url, timeout=10) as response:
                if 200 <= response.status < 400:
                    end_time = time.time()
                    return name, round((end_time - start_time) * 1000, 2), url
                else:
                    print(f"异步测速失败: {name} ({url}) - HTTP {response.status}")
                    return name, None, url
        except Exception as e:
            print(f"异步测速失败: {name} ({url}) - {e}")
            return name, None, url


    async def list_mirrors_async():
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            tasks = [test_mirror_speed_async(session, name, url) for name, url in MIRRORS.items()]
            print("正在异步测速，请稍候...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        total_time = round((end_time - start_time) * 1000, 2)
        results.sort(key=lambda x: (x[1] is None, x[1]))
        print_mirror_results(results)
        print(f"异步测速总耗时: {total_time} ms")
        return results


# 同步测速函数
def test_mirror_speed_sync(name, url):
    try:
        start_time = time.time()
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        end_time = time.time()
        return name, round((end_time - start_time) * 1000, 2), url
    except requests.RequestException as e:
        print(f"同步测速失败: {name} ({url}) - {e}")
        return name, None, url


def list_mirrors_sync():
    start_time = time.time()
    print("正在同步测速，请稍候...")
    results = [test_mirror_speed_sync(name, url) for name, url in MIRRORS.items()]
    end_time = time.time()
    total_time = round((end_time - start_time) * 1000, 2)
    results.sort(key=lambda x: (x[1] is None, x[1]))
    print_mirror_results(results)
    print(f"\n同步测速总耗时: {total_time} ms")
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


def extract_host_from_url(url):
    return urlparse(url).hostname


def update_pip_config(mirror_url):
    config_path = get_pip_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)

    if 'global' not in config:
        config['global'] = {}

    config['global']['index-url'] = mirror_url

    host = extract_host_from_url(mirror_url)
    if 'trusted-host' in config['global']:
        existing_hosts = config['global']['trusted-host'].split()
        if host not in existing_hosts:
            existing_hosts.append(host)
            config['global']['trusted-host'] = ' '.join(existing_hosts)
    else:
        config['global']['trusted-host'] = host

    with open(config_path, 'w') as configfile:
        config.write(configfile)

    print(f"成功设置 pip 镜像源为 '{mirror_url}'，并添加 trusted-host '{host}'")


def unset_mirror():
    """取消 pip 镜像源设置"""
    config_path = get_pip_config_path()
    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        if 'global' in config:
            config['global'].pop('index-url', None)
            config['global'].pop('trusted-host', None)
            if not config['global']:
                config.remove_section('global')
            with open(config_path, 'w') as configfile:
                config.write(configfile)
            print("成功取消 pip 镜像源设置，已恢复为默认源")
        else:
            print("未设置自定义 pip 镜像源")
    else:
        print("未设置自定义 pip 镜像源")


def main():
    """主函数，解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(description="轻松管理 pip 镜像源。")
    parser.add_argument("command", choices=["list", "set", "unset"], help="要执行的命令")
    parser.add_argument("mirror", nargs="?", help="要设置的镜像源名称 (仅用于 'set' 命令)")

    args = parser.parse_args()

    if args.command == "list":
        if ASYNC_SUPPORTED:
            asyncio.run(list_mirrors_async())
        else:
            list_mirrors_sync()
    elif args.command == "set":
        if args.mirror is None:
            print("未指定镜像源，正在测速并选择最快的镜像源...")
            if ASYNC_SUPPORTED:
                results = asyncio.run(list_mirrors_async())
            else:
                results = list_mirrors_sync()

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
        unset_mirror()
        sys.exit(0)


if __name__ == "__main__":
    main()
