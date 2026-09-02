import json
import os
import urllib.request
import urllib.error
import socket
from pathlib import Path
from urllib.parse import urlparse

from .state import atomic_write_text

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

_MIRROR_NAME_RE = r'^[a-z0-9][a-z0-9_-]{0,31}$'
# 按顺序尝试：jsDelivr CDN 在中国大陆可达，raw.githubusercontent.com 作为最终兜底
REMOTE_MIRRORS_URLS = [
    "https://cdn.jsdelivr.net/gh/caoergou/cnpip@main/cnpip/mirrors.json",
    "https://fastly.jsdelivr.net/gh/caoergou/cnpip@main/cnpip/mirrors.json",
    "https://raw.githubusercontent.com/caoergou/cnpip/main/cnpip/mirrors.json",
]
USER_CONFIG_DIR = Path.home() / ".cnpip"
USER_MIRRORS_FILE = USER_CONFIG_DIR / "mirrors.json"


def _validate_mirrors(data, strict_remote=False):
    """校验镜像清单；远程清单只强化传输协议与地址结构约束。"""
    import re

    if not isinstance(data, dict) or not data:
        raise ValueError("镜像清单必须是非空对象")
    if len(data) > 128:
        raise ValueError("镜像清单条目过多")

    for name, url in data.items():
        if not isinstance(name, str) or not re.fullmatch(_MIRROR_NAME_RE, name):
            raise ValueError(f"镜像名称无效: {name!r}")
        if not isinstance(url, str) or len(url) > 512:
            raise ValueError(f"镜像地址无效: {name}")
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"镜像地址无效: {name}: {exc}")
        if ((parsed.scheme != 'https') if strict_remote
                else parsed.scheme not in ('http', 'https')):
            raise ValueError(f"镜像必须使用 HTTPS: {name}")
        if any(char.isspace() or ord(char) < 32 for char in url):
            raise ValueError(f"镜像地址包含非法空白字符: {name}")
        if not hostname or parsed.username or parsed.password or port is not None:
            raise ValueError(f"镜像地址不得包含凭据或端口: {name}")
        if (parsed.params or parsed.query or parsed.fragment
                or not parsed.path.rstrip('/').endswith('/simple')):
            raise ValueError(f"镜像地址必须是 PEP 503 simple 路径: {name}")
    return {name: url.rstrip('/') for name, url in data.items()}

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
                return _validate_mirrors(json.load(f))
        except Exception:
            pass # 失败则后备

    # 2. 包内配置
    pkg_file = get_local_mirrors_file()
    if os.path.exists(pkg_file):
        try:
            with open(pkg_file, 'r', encoding='utf-8') as f:
                return _validate_mirrors(json.load(f))
        except Exception:
            pass

    # 3. 硬编码
    return _validate_mirrors(DEFAULT_MIRRORS.copy())

def _fetch_mirrors_json(url, timeout=5):
    """从单个 URL 获取并解析 mirrors.json，失败抛出异常。"""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise urllib.error.URLError(f"HTTP {response.status}")
        raw = response.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise ValueError("远程镜像清单过大")
        data = json.loads(raw.decode('utf-8'))
        return _validate_mirrors(data, strict_remote=True)


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

        try:
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            payload = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
            atomic_write_text(USER_MIRRORS_FILE, payload, mode=0o600)
        except OSError as exc:
            return False, f"保存镜像源列表失败: {exc}"
        return True, f"成功从 {url} 更新镜像源"

    detail = "\n".join(f"  - {e}" for e in errors)
    return False, f"所有远程地址均获取失败:\n{detail}"

# 初始化 MIRRORS 以兼容旧代码
# 但建议调用者直接使用 load_mirrors()
MIRRORS = load_mirrors()
