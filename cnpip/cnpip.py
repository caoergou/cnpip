import os
import sys
import argparse
import requests
import time
import configparser

MIRRORS = {
    "tuna": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc": "https://pypi.mirrors.ustc.edu.cn/simple",
    "douban": "https://pypi.douban.com/simple",
    "default": "https://pypi.org/simple"
}

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

# 列出所有可用的镜像源，并测试连接速度，按速度排序
def list_mirrors():
    results = []
    for name, url in MIRRORS.items():
        speed = test_mirror_speed(url)
        results.append((name, speed, url))

    # 按速度从小到大排序，无法连接的镜像放在最后
    results.sort(key=lambda x: (x[1] is None, x[1]))

    # 动态计算列宽
    name_width = max(len(name) for name in MIRRORS.keys()) + 2
    time_width = 10  # 固定宽度，确保耗时列对齐
    url_width = max(len(url) for url in MIRRORS.values()) + 2

    # 打印表头
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

    # 确保目录存在，如果不存在则创建
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    config = configparser.ConfigParser()

    # 如果配置文件存在，读取它
    if os.path.exists(config_path):
        config.read(config_path)

    # 确保有 [global] 部分
    if 'global' not in config:
        config['global'] = {}

    config['global']['index-url'] = mirror_url

    with open(config_path, 'w') as configfile:
        config.write(configfile)

    print(f"成功设置 pip 镜像源为 '{mirror_url}'")

# 设置指定的镜像源
def set_mirror(mirror_name=None):
    if mirror_name is None:
        # 如果没有提供镜像名称，选择速度最快的镜像
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

    # 获取镜像 URL
    mirror_url = MIRRORS[mirror_name]

    # 更新 pip 配置文件
    update_pip_config(mirror_url)

# 取消设置镜像源，恢复默认
def unset_mirror():
    config_path = get_pip_config_path()

    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)

        # 删除 index-url 配置
        if 'global' in config and 'index-url' in config['global']:
            del config['global']['index-url']

            # 如果 global 部分为空，删除它
            if not config['global']:
                del config['global']

            # 写回配置文件
            with open(config_path, 'w') as configfile:
                config.write(configfile)

            print("成功取消 pip 镜像源设置，已恢复为默认源。")
        else:
            print("未设置自定义 pip 镜像源。")
    else:
        print("未设置自定义 pip 镜像源。")

# 主函数，解析命令行参数
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
