"""cnpip 对持久化配置的所有权与恢复状态。"""

import base64
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path


STATE_FILE = Path.home() / ".cnpip" / "state.json"
STATE_VERSION = 1


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _fingerprint(data):
    """返回能区分不存在文件与零字节文件的指纹。"""
    return "missing" if data is None else f"sha256:{_digest(data)}"


def _read_bytes(path):
    path = Path(path)
    return path.read_bytes() if path.exists() else None


def atomic_write_bytes(path, data, mode=None):
    """在目标目录内写临时文件并原子替换，避免留下截断文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode & 0o777 if path.exists() else None
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, mode if mode is not None else (existing_mode or 0o600))
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_text(path, content, mode=None):
    atomic_write_bytes(path, content.encode("utf-8"), mode=mode)


def _empty_state():
    return {"version": STATE_VERSION, "files": {}, "values": {}}


def _load_state():
    if not STATE_FILE.exists():
        return _empty_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(f"cnpip 状态文件损坏: {STATE_FILE}")
    if not isinstance(data, dict):
        raise ValueError(f"cnpip 状态文件格式无效: {STATE_FILE}")
    if data.get("version") != STATE_VERSION:
        raise ValueError(f"不支持的 cnpip 状态版本: {data.get('version')}")
    if not isinstance(data.get("files"), dict) or not isinstance(data.get("values"), dict):
        raise ValueError(f"cnpip 状态文件格式无效: {STATE_FILE}")
    return data


def _save_state(state):
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_text(STATE_FILE, payload + "\n", mode=0o600)


def _encoded(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def _decoded(data):
    return None if data is None else base64.b64decode(data.encode("ascii"))


class ManagedFileChange:
    """一次受 cnpip 管理的文件修改。"""

    def __init__(self, key, path, state, original_entry, immediate_before):
        self.key = key
        self.path = Path(path)
        self.state = state
        self.original_entry = original_entry
        self.immediate_before = immediate_before

    @classmethod
    def begin(cls, key, path):
        path = Path(path).expanduser().resolve()
        try:
            state = _load_state()
            immediate = _read_bytes(path)
        except ValueError as exc:
            return None, str(exc)
        except OSError as exc:
            return None, f"读取配置失败: {path}: {exc}"
        existing = state["files"].get(key)
        if existing:
            if existing.get("path") != str(path):
                return None, f"cnpip 状态与配置路径不一致: {path}"
            if _fingerprint(immediate) != existing.get("after_fingerprint"):
                return None, f"检测到配置已在 cnpip 修改后发生变化，拒绝覆盖: {path}"
            original = existing
        else:
            original = {
                "path": str(path),
                "before": _encoded(immediate),
                "before_exists": immediate is not None,
            }
        return cls(key, path, state, original, immediate), None

    def abort(self):
        _restore_bytes(self.path, self.immediate_before)

    def commit(self):
        try:
            after = _read_bytes(self.path)
        except OSError as exc:
            self.abort()
            return False, f"读取配置写入结果失败: {self.path}: {exc}"
        if after is None:
            self.abort()
            return False, f"配置写入后不存在: {self.path}"
        entry = dict(self.original_entry)
        entry["after_fingerprint"] = _fingerprint(after)
        self.state["files"][self.key] = entry
        try:
            _save_state(self.state)
        except Exception as exc:
            self.abort()
            return False, f"保存 cnpip 配置所有权失败，已回滚: {exc}"
        return True, None


def _restore_bytes(path, data):
    path = Path(path)
    if data is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write_bytes(path, data)


def restore_managed_file(key, path):
    path = Path(path).expanduser().resolve()
    try:
        state = _load_state()
        current = _read_bytes(path)
    except ValueError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, f"读取配置失败: {path}: {exc}"
    entry = state["files"].get(key)
    if not entry:
        return True, f"cnpip 没有管理此配置，无需恢复: {path}"
    if entry.get("path") != str(path):
        return False, f"cnpip 状态与配置路径不一致: {path}"
    if _fingerprint(current) != entry.get("after_fingerprint"):
        return False, f"检测到配置已在 cnpip 修改后发生变化，拒绝覆盖: {path}"
    try:
        before = _decoded(entry.get("before")) if entry.get("before_exists") else None
    except Exception as exc:
        return False, f"cnpip 状态文件中的备份无效: {exc}"
    original_state = copy.deepcopy(state)
    try:
        _restore_bytes(path, before)
        del state["files"][key]
        _save_state(state)
    except Exception as exc:
        try:
            _restore_bytes(path, current)
        except Exception as rollback_exc:
            return False, f"恢复配置失败: {exc}；回滚失败: {rollback_exc}"
        # _save_state 使用原子替换；失败时旧状态通常仍然存在。
        # 保留这份副本供调用方诊断，也避免误报为恢复成功。
        state.clear()
        state.update(original_state)
        return False, f"恢复配置失败: {exc}"
    return True, f"已恢复 cnpip 修改前的配置: {path}"


def record_managed_value(key, before, after):
    try:
        state = _load_state()
    except ValueError as exc:
        return False, str(exc)
    existing = state["values"].get(key)
    if existing and existing.get("after") != before:
        return False, "检测到配置值已在 cnpip 修改后发生变化，拒绝覆盖"
    original = existing.get("before") if existing else before
    state["values"][key] = {"before": original, "after": after}
    try:
        _save_state(state)
    except Exception as exc:
        return False, f"保存 cnpip 配置所有权失败: {exc}"
    return True, None


def managed_value_to_restore(key, current):
    try:
        state = _load_state()
    except ValueError as exc:
        return False, None, str(exc)
    entry = state["values"].get(key)
    if not entry:
        return True, None, "cnpip 没有管理此配置，无需恢复"
    if entry.get("after") != current:
        return False, None, "检测到配置值已在 cnpip 修改后发生变化，拒绝覆盖"
    return True, entry.get("before"), None


def forget_managed_value(key):
    try:
        state = _load_state()
        state["values"].pop(key, None)
        _save_state(state)
    except Exception as exc:
        return False, f"清理 cnpip 配置所有权失败: {exc}"
    return True, None
