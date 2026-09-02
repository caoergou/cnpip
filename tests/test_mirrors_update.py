"""测试 cnpip update 的多远程地址 fallback 逻辑。"""
import json

import pytest

import cnpip.mirrors as mirrors_module
from cnpip.mirrors import update_mirrors_from_remote, REMOTE_MIRRORS_URLS

FAKE_MIRRORS = {"tuna": "https://pypi.tuna.tsinghua.edu.cn/simple"}


@pytest.fixture
def fake_user_config(tmp_path, monkeypatch):
    """将用户配置目录重定向到 tmp_path。"""
    config_dir = tmp_path / '.cnpip'
    monkeypatch.setattr(mirrors_module, 'USER_CONFIG_DIR', config_dir)
    monkeypatch.setattr(mirrors_module, 'USER_MIRRORS_FILE', config_dir / 'mirrors.json')
    return config_dir / 'mirrors.json'


def test_url_list_prefers_china_accessible_cdn():
    # jsDelivr 必须排在 raw.githubusercontent.com 之前（后者在中国大陆不可达）
    raw_index = next(i for i, u in enumerate(REMOTE_MIRRORS_URLS) if 'raw.githubusercontent.com' in u)
    jsdelivr_index = next(i for i, u in enumerate(REMOTE_MIRRORS_URLS) if 'jsdelivr.net' in u)
    assert jsdelivr_index < raw_index


def test_first_url_success(fake_user_config, monkeypatch):
    monkeypatch.setattr(mirrors_module, '_fetch_mirrors_json', lambda url, timeout=5: FAKE_MIRRORS)
    success, msg = update_mirrors_from_remote()
    assert success
    assert REMOTE_MIRRORS_URLS[0] in msg
    assert json.loads(fake_user_config.read_text(encoding='utf-8')) == FAKE_MIRRORS


def test_fallback_to_second_url(fake_user_config, monkeypatch):
    def _fetch(url, timeout=5):
        if url == REMOTE_MIRRORS_URLS[0]:
            raise ValueError("connection failed")
        return FAKE_MIRRORS

    monkeypatch.setattr(mirrors_module, '_fetch_mirrors_json', _fetch)
    success, msg = update_mirrors_from_remote()
    assert success
    assert REMOTE_MIRRORS_URLS[1] in msg
    assert json.loads(fake_user_config.read_text(encoding='utf-8')) == FAKE_MIRRORS


def test_all_urls_fail(fake_user_config, monkeypatch):
    def _fetch(url, timeout=5):
        raise ValueError("unreachable")

    monkeypatch.setattr(mirrors_module, '_fetch_mirrors_json', _fetch)
    success, msg = update_mirrors_from_remote()
    assert not success
    # 错误信息应列出每个尝试过的地址
    for url in REMOTE_MIRRORS_URLS:
        assert url in msg
    assert not fake_user_config.exists()


def test_invalid_json_falls_through(fake_user_config, monkeypatch):
    """非 dict 的 JSON 应视为该地址失败，继续尝试下一个。"""
    calls = []

    def _fake_urlopen(url, timeout=5):
        calls.append(url)

        class FakeResponse:
            status = 200

            def read(self):
                # 第一个地址返回非法内容（list），之后返回合法 dict
                if len(calls) == 1:
                    return json.dumps([1, 2, 3]).encode('utf-8')
                return json.dumps(FAKE_MIRRORS).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return FakeResponse()

    monkeypatch.setattr(mirrors_module.urllib.request, 'urlopen', _fake_urlopen)
    success, msg = update_mirrors_from_remote()
    assert success
    assert len(calls) == 2
