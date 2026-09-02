import json
import os
import urllib.request
import urllib.error
import socket
from pathlib import Path

# 硬编码作为后备
DEFAULT_MIRRORS = {
    "tuna": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc": "https://pypi.mirrors.ustc.edu.cn/simple",
    "tencent": "https://mirrors.cloud.tencent.com/pypi/simple",
    "huawei": "https://repo.huaweicloud.com/repository/pypi/simple",
    "westlake": "https://mirrors.westlake.edu.cn/pypi/simple",
    "sustech": "https://mirrors.sustech.edu.cn/pypi/web/simple",
    "default": "https://pypi.org/simple"
}

# 按顺序尝试：jsDelivr CDN 在中国大陆可达，raw.githubusercontent.com 作为最终兜底
REMOTE_MIRRORS_URLS = [
    "https://cdn.jsdelivr.net/gh/caoergou/cnpip@main/cnpip/mirrors.json",
    "https://fastly.jsdelivr.net/gh/caoergou/cnpip@main/cnpip/mirrors.json",
    "https://raw.githubusercontent.com/caoergou/cnpip/main/cnpip/mirrors.json",
]
USER_CONFIG_DIR = Path.home() / ".cnpip"
USER_MIRRORS_FILE = USER_CONFIG_DIR / "mirrors.json"

def get_local_mirrors_file():
    """返回打包的 mirrors.json 路径"""
    return os.path.join(os.path.dirname(__file__), 'mirrors.json')

def load_mirrors():
    """
    按优先级加载镜像源：
    1. 用户自定义配置 (~/.cnpip/mirrors.json)
    2. 包内自带配置 (cnpip/mirrors.json)
    3. 硬编码后备
    """
    # 1. 用户配置
    if USER_MIRRORS_FILE.exists():
        try:
            with open(USER_MIRRORS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass # 失败则后备

    # 2. 包内配置
    pkg_file = get_local_mirrors_file()
    if os.path.exists(pkg_file):
        try:
            with open(pkg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    # 3. 硬编码
    return DEFAULT_MIRRORS.copy()

def _fetch_mirrors_json(url, timeout=5):
    """从单个 URL 获取并解析 mirrors.json，失败抛出异常。"""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise urllib.error.URLError(f"HTTP {response.status}")
        data = json.loads(response.read().decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError("远程 JSON 格式无效")
        return data


def update_mirrors_from_remote():
    """
    依次尝试多个远程地址获取镜像源列表，成功后保存到用户配置文件。
    返回 (success, message/error)。
    """
    errors = []
    for url in REMOTE_MIRRORS_URLS:
        try:
            data = _fetch_mirrors_json(url)
        except urllib.error.URLError as e:
            errors.append(f"{url}: 网络错误 ({getattr(e, 'reason', e)})")
            continue
        except socket.timeout:
            errors.append(f"{url}: 请求超时")
            continue
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue

        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(USER_MIRRORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True, f"成功从 {url} 更新镜像源"

    detail = "\n".join(f"  - {e}" for e in errors)
    return False, f"所有远程地址均获取失败:\n{detail}"

# 初始化 MIRRORS 以兼容旧代码
# 但建议调用者直接使用 load_mirrors()
MIRRORS = load_mirrors()
