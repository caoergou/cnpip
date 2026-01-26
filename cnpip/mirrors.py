import json
import os
import urllib.request
import urllib.error
import socket
from pathlib import Path

# Hardcoded fallback
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
    """Returns the path to the packaged mirrors.json"""
    return os.path.join(os.path.dirname(__file__), 'mirrors.json')

def load_mirrors():
    """
    Load mirrors in order of priority:
    1. User custom mirrors (~/.cnpip/mirrors.json)
    2. Package mirrors (cnpip/mirrors.json)
    3. Hardcoded fallback
    """
    # 1. User config
    if USER_MIRRORS_FILE.exists():
        try:
            with open(USER_MIRRORS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass # Fallback

    # 2. Package config
    pkg_file = get_local_mirrors_file()
    if os.path.exists(pkg_file):
        try:
            with open(pkg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    # 3. Hardcoded
    return DEFAULT_MIRRORS.copy()

def update_mirrors_from_remote():
    """
    Fetches mirrors from remote URL and saves to user config file.
    Returns (success, message/error).
    """
    try:
        # 5 second timeout
        with urllib.request.urlopen(REMOTE_MIRRORS_URL, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))

                # Validation: simple check if it looks like a dict
                if not isinstance(data, dict):
                    return False, "Invalid JSON format from remote"

                # Ensure directory exists
                USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

                with open(USER_MIRRORS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                return True, f"Successfully updated mirrors from {REMOTE_MIRRORS_URL}"
            else:
                return False, f"Failed to fetch: HTTP {response.status}"
    except urllib.error.URLError as e:
        return False, f"Network error: {e.reason}"
    except socket.timeout:
        return False, "Request timed out"
    except Exception as e:
        return False, f"Error: {e}"

# Initialize MIRRORS for backward compatibility (if needed)
# But ideally, consumers should call load_mirrors()
MIRRORS = load_mirrors()
