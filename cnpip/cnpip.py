import json
import os
import sys
import argparse
import requests
import time
import configparser

with open(os.path.join(os.path.dirname(__file__), 'mirrors.txt')) as f:
    MIRRORS = json.load(f)


def get_pip_config_path():
    if os.name == 'nt':  # Windows
        return os.path.join(os.getenv('APPDATA'), 'pip', 'pip.ini')
    else:  # Linux and macOS
        return os.path.expanduser('~/.pip/pip.conf')


def test_mirror_speed(url):
    try:
        start_time = time.time()
        response = requests.head(url, timeout=5)  # 发送 HEAD 请求
        response.raise_for_status()  # 检查请求是否成功
        end_time = time.time()
        return round((end_time - start_time) * 1000, 2)  # 返回毫秒级的响应时间
    except requests.RequestException:
        return None  # 如果请求失败，返回 None


def list_mirrors():
    results = []
    for name, url in MIRRORS.items():
        speed = test_mirror_speed(url)
        results.append((name, speed, url))

    results.sort(key=lambda x: (x[1] is None, x[1]))

    name_width = max(len(name) for name in MIRRORS.keys()) + 2
    time_width = 10  # 固定宽度，确保耗时列对齐
    url_width = max(len(url) for url in MIRRORS.values()) + 2

    header = f"{'镜像名称':<{name_width}} {'耗时(ms)':<{time_width}} {'地址':<{url_width}}"
    print(header)
    print("-" * (name_width + time_width + url_width))

    # 打印排序后的结果
    for name, speed, url in results:
        if speed is not None:
            print(f"{name:<{name_width}} {speed:<{time_width}.2f} {url:<{url_width}}")
        else:
            print(f"{name:<{name_width}} {'error':<{time_width}} {url:<{url_width}}")


def update_pip_config(mirror_url):
    config_path = get_pip_config_path()
    config_dir = os.path.dirname(config_path)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)

    # 确保有 [global] 部分
    if 'global' not in config:
        config['global'] = {}

    config['global']['index-url'] = mirror_url

    with open(config_path, 'w') as configfile:
        config.write(configfile)

    print(f"成功设置 pip 镜像源为 '{mirror_url}'")


def set_mirror(mirror_name=None):
    if mirror_name is None:
        results = []
        for name, url in MIRRORS.items():
            speed = test_mirror_speed(url)
            results.append((name, speed, url))

        # 按速度从小到大排序，选择第一个可用的镜像
        results.sort(key=lambda x: (x[1] is None, x[1]))
        fastest_mirror = next((name for name, speed, url in results if speed is not None), None)

        if fastest_mirror is None:
            print("错误: 无法连接到任何镜像源。")
            sys.exit(1)

        mirror_name = fastest_mirror
        print(f"未指定镜像源，自动选择最快的镜像源: {mirror_name}")

    elif mirror_name not in MIRRORS:
        print(f"错误: 未找到镜像源 '{mirror_name}'。")
        sys.exit(1)

    mirror_url = MIRRORS[mirror_name]

    update_pip_config(mirror_url)


def unset_mirror():
    config_path = get_pip_config_path()

    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)

        if 'global' in config and 'index-url' in config['global']:
            del config['global']['index-url']

            if not config['global']:
                del config['global']

            with open(config_path, 'w') as configfile:
                config.write(configfile)

            print("成功取消 pip 镜像源设置，已恢复为默认源。")
        else:
            print("未设置自定义 pip 镜像源。")
    else:
        print("未设置自定义 pip 镜像源。")


def main():
    parser = argparse.ArgumentParser(description="轻松管理 pip 镜像源。")
    parser.add_argument("command", choices=["list", "set", "unset"], help="要执行的命令")
    parser.add_argument("mirror", nargs="?", help="要设置的镜像源名称 (仅用于 'set' 命令)")

    args = parser.parse_args()

    if args.command == "list":
        list_mirrors()
    elif args.command == "set":
        set_mirror(args.mirror)
    elif args.command == "unset":
        unset_mirror()


if __name__ == "__main__":
    main()
