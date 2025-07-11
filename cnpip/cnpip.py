import subprocess
import sys
import argparse
import time
import asyncio
import os
import platform
from urllib.parse import urlparse
from pathlib import Path

MIN_PYTHON_VERSION = (3, 6)
if sys.version_info < MIN_PYTHON_VERSION:
    sys.stderr.write(f"错误: cnpip需要 Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} 或更高版本。\n")
    sys.stderr.write("您也可直接使用以下命令快速安装包:\n")
    sys.stderr.write(">\tpip install [package_name] -i https://pypi.tuna.tsinghua.edu.cn/simple \n")
    sys.exit(1)

try:
    import aiohttp  # noqa

    ASYNC_SUPPORTED = True
except ImportError:
    import requests

    ASYNC_SUPPORTED = False

from .mirrors import MIRRORS

# 异步测速函数
if ASYNC_SUPPORTED:
    async def measure_mirror_speed_async(session, name, url):
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
        """改进的异步测速主函数"""
        start_time = time.monotonic()
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=5)  # 限制并发连接数

        async with aiohttp.ClientSession(timeout=timeout,
                                         connector=connector) as session:
            tasks = [measure_mirror_speed_async(session, name, url)
                     for name, url in MIRRORS.items()]
            print("正在异步测速，请稍候...")
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉异常结果
        valid_results = [r for r in results if isinstance(r, tuple)]
        valid_results.sort(key=lambda x: (x[1] is None, x[1]))
        print_mirror_results(valid_results)
        print(f"异步测速总耗时: {round((time.monotonic() - start_time) * 1000, 2)} ms")
        return valid_results


def measure_mirror_speed_sync(name, url):
    """同步测速函数"""
    try:
        start_time = time.monotonic()
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        return name, round((time.monotonic() - start_time) * 1000, 2), url
    except requests.RequestException as e:
        print(f"同步测速失败: {name} ({url}) - {e}")
        return name, None, url


def list_mirrors_sync():
    """展示镜像源列表并同步测速"""
    start_time = time.monotonic()
    print("正在同步测速，请稍候...")
    results = [measure_mirror_speed_sync(name, url) for name, url in MIRRORS.items()]
    total_time = round((time.monotonic() - start_time) * 1000, 2)
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


def is_uv_available():
    """检查 uv 是否安装"""
    try:
        subprocess.run(['uv', '--version'], 
                       check=True, 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


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


def get_uv_config_path():
    """获取 uv 配置文件路径"""
    if platform.system() == "Windows":
        config_dir = Path.home() / "AppData" / "Roaming" / "uv"
    else:
        config_dir = Path.home() / ".config" / "uv"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "uv.toml"


def update_uv_config(mirror_url):
    """更新 uv 配置"""
    config_path = get_uv_config_path()
    
    # 读取现有配置
    config_content = ""
    if config_path.exists():
        config_content = config_path.read_text(encoding='utf-8')
    
    # 检查是否已有 [pip] 段
    if '[pip]' in config_content:
        # 替换现有的 index-url
        lines = config_content.split('\n')
        new_lines = []
        in_pip_section = False
        index_url_updated = False
        
        for line in lines:
            if line.strip() == '[pip]':
                in_pip_section = True
                new_lines.append(line)
            elif line.strip().startswith('[') and line.strip() != '[pip]':
                in_pip_section = False
                new_lines.append(line)
            elif in_pip_section and line.strip().startswith('index-url'):
                new_lines.append(f'index-url = "{mirror_url}"')
                index_url_updated = True
            else:
                new_lines.append(line)
        
        if in_pip_section and not index_url_updated:
            new_lines.append(f'index-url = "{mirror_url}"')
        
        config_content = '\n'.join(new_lines)
    else:
        # 添加新的 [pip] 段
        if config_content and not config_content.endswith('\n'):
            config_content += '\n'
        config_content += f'[pip]\nindex-url = "{mirror_url}"\n'
    
    # 写入配置文件
    config_path.write_text(config_content, encoding='utf-8')


def unset_uv_config():
    """取消 uv 镜像源设置"""
    config_path = get_uv_config_path()
    
    if not config_path.exists():
        print("uv 配置文件不存在，无需取消设置")
        return
    
    config_content = config_path.read_text(encoding='utf-8')
    
    # 移除 [pip] 段中的 index-url
    lines = config_content.split('\n')
    new_lines = []
    in_pip_section = False
    
    for line in lines:
        if line.strip() == '[pip]':
            in_pip_section = True
            # 检查下一行是否只有 index-url，如果是则跳过整个 [pip] 段
            continue
        elif line.strip().startswith('[') and line.strip() != '[pip]':
            in_pip_section = False
            new_lines.append(line)
        elif in_pip_section and line.strip().startswith('index-url'):
            # 跳过 index-url 行
            continue
        else:
            if not in_pip_section:
                new_lines.append(line)
    
    # 移除空行
    while new_lines and new_lines[-1].strip() == '':
        new_lines.pop()
    
    if new_lines:
        config_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    else:
        config_path.unlink()  # 删除空的配置文件


def update_pip_config(mirror_url):
    # 提取主机名
    host = urlparse(mirror_url).netloc
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set', 'global.index-url', mirror_url], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'set', 'global.trusted-host', host], check=True)
        print(f"成功设置 pip 镜像源为 '{mirror_url}'，并添加 trusted-host '{host}'")
    except subprocess.CalledProcessError as e:
        print(f"更新 pip 配置时出错: {e}, 详细报错如下：")
        raise e


def unset_pip_mirror() -> None:
    """取消pip镜像源设置"""
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset', 'global.index-url'], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'config', 'unset', 'global.trusted-host'], check=True)
        print("成功取消 pip 镜像源设置，已恢复为默认源")
    except subprocess.CalledProcessError as e:
        print(f"取消 pip 镜像源设置时出错: {e}, 详细报错如下：")
        raise e


def update_mirror_config(mirror_url):
    """更新包管理器镜像源配置（支持 uv 和 pip）"""
    uv_available = is_uv_available()
    pip_available = is_pip_installed()
    
    success_count = 0
    
    if uv_available:
        try:
            update_uv_config(mirror_url)
            success_count += 1
        except Exception as e:
            print(f"更新 uv 配置时出错: {e}")
    
    if pip_available:
        try:
            update_pip_config(mirror_url)
            success_count += 1
        except Exception as e:
            print(f"更新 pip 配置时出错: {e}")
    
    if success_count == 0:
        print("错误: 无法更新任何包管理器的配置")
        sys.exit(1)
    
    # 只向用户显示 pip 相关信息
    print("成功设置 pip 镜像源")


def unset_mirror_config():
    """取消包管理器镜像源设置（支持 uv 和 pip）"""
    uv_available = is_uv_available()
    pip_available = is_pip_installed()
    
    success_count = 0
    
    if uv_available:
        try:
            unset_uv_config()
            success_count += 1
        except Exception as e:
            print(f"取消 uv 配置时出错: {e}")
    
    if pip_available:
        try:
            unset_pip_mirror()
            success_count += 1
        except Exception as e:
            print(f"取消 pip 配置时出错: {e}")
    
    if success_count == 0:
        print("错误: 无法取消任何包管理器的配置")
        sys.exit(1)
    
    # 只向用户显示 pip 相关信息
    print("成功取消 pip 镜像源设置，已恢复为默认源")


def main():
    """主函数，解析命令行参数并执行相应操作"""
    uv_available = is_uv_available()
    pip_available = is_pip_installed()
    
    if not uv_available and not pip_available:
        print("错误: 未找到 pip，无法设置镜像源")
        sys.exit(1)

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
            print("未指定镜像源，即将测速并选择最快的镜像源...")
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
        update_mirror_config(mirror_url)
    elif args.command == "unset":
        unset_mirror_config()
        sys.exit(0)


if __name__ == "__main__":
    main()
