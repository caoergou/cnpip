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

REMOTE_MIRRORS_URL = "https://raw.githubusercontent.com/caoergou/cnpip/main/cnpip/mirrors.json"
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

def update_mirrors_from_remote():
    """
    从远程 URL 获取镜像源并保存到用户配置文件。
    返回 (success, message/error)。
    """
    try:
        # 5秒超时
        with urllib.request.urlopen(REMOTE_MIRRORS_URL, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))

                # 验证：简单检查是否为字典
                if not isinstance(data, dict):
                    return False, "远程 JSON 格式无效"

                # 确保目录存在
                USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

                with open(USER_MIRRORS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                return True, f"成功从 {REMOTE_MIRRORS_URL} 更新镜像源"
            else:
                return False, f"获取失败: HTTP {response.status}"
    except urllib.error.URLError as e:
        return False, f"网络错误: {e.reason}"
    except socket.timeout:
        return False, "请求超时"
    except Exception as e:
        return False, f"错误: {e}"

# 初始化 MIRRORS 以兼容旧代码
# 但建议调用者直接使用 load_mirrors()
MIRRORS = load_mirrors()
