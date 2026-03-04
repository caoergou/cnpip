"""测试 uv 配置文件的读写操作（不依赖 uv 命令）。"""
import pytest

from cnpip.cnpip import update_uv_config, unset_uv_config, get_uv_index_url

MIRROR_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'
ALT_URL = 'https://mirrors.aliyun.com/pypi/simple'


class TestUpdateUvConfig:
    def test_creates_uv_toml(self, fake_uv_config_path):
        success, msg = update_uv_config(MIRROR_URL)
        assert success, msg
        assert fake_uv_config_path.exists()

    def test_creates_parent_directories(self, fake_uv_config_path):
        assert not fake_uv_config_path.parent.exists()
        update_uv_config(MIRROR_URL)
        assert fake_uv_config_path.parent.exists()

    def test_writes_index_block(self, fake_uv_config_path):
        update_uv_config(MIRROR_URL)
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert '[[index]]' in content

    def test_writes_url(self, fake_uv_config_path):
        update_uv_config(MIRROR_URL)
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert MIRROR_URL in content

    def test_writes_default_true(self, fake_uv_config_path):
        update_uv_config(MIRROR_URL)
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert 'default = true' in content

    def test_replaces_existing_index_block(self, fake_uv_config_path):
        update_uv_config(ALT_URL)
        success, msg = update_uv_config(MIRROR_URL)
        assert success, msg
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert MIRROR_URL in content
        assert ALT_URL not in content

    def test_only_one_index_block_after_replace(self, fake_uv_config_path):
        update_uv_config(ALT_URL)
        update_uv_config(MIRROR_URL)
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert content.count('[[index]]') == 1

    def test_appends_to_existing_file(self, fake_uv_config_path):
        # 文件已有其他内容
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text('[global]\nsome-key = "value"\n', encoding='utf-8')
        success, msg = update_uv_config(MIRROR_URL)
        assert success, msg
        content = fake_uv_config_path.read_text(encoding='utf-8')
        # 原有内容保留
        assert 'some-key' in content
        # 新内容追加
        assert '[[index]]' in content

    def test_message_contains_mirror_url(self, fake_uv_config_path):
        success, msg = update_uv_config(MIRROR_URL)
        assert success
        assert MIRROR_URL in msg


class TestGetUvIndexUrl:
    def test_returns_configured_url(self, fake_uv_config_path):
        update_uv_config(MIRROR_URL)
        result = get_uv_index_url()
        assert result == MIRROR_URL

    def test_returns_none_when_file_missing(self, fake_uv_config_path):
        # 文件不存在
        assert not fake_uv_config_path.exists()
        result = get_uv_index_url()
        assert result is None

    def test_returns_none_when_no_index_block(self, fake_uv_config_path):
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text('[global]\nsome-key = "value"\n', encoding='utf-8')
        result = get_uv_index_url()
        assert result is None

    def test_returns_url_after_replace(self, fake_uv_config_path):
        update_uv_config(ALT_URL)
        update_uv_config(MIRROR_URL)
        result = get_uv_index_url()
        assert result == MIRROR_URL


class TestUnsetUvConfig:
    def test_removes_index_block(self, fake_uv_config_path):
        update_uv_config(MIRROR_URL)
        success, msg = unset_uv_config()
        assert success, msg
        result = get_uv_index_url()
        assert result is None

    def test_graceful_when_file_missing(self, fake_uv_config_path):
        assert not fake_uv_config_path.exists()
        success, msg = unset_uv_config()
        assert success

    def test_graceful_when_no_index_block(self, fake_uv_config_path):
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text('[global]\nkey = "val"\n', encoding='utf-8')
        success, msg = unset_uv_config()
        assert success

    def test_preserves_other_content(self, fake_uv_config_path):
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text(
            '[global]\nkey = "val"\n\n[[index]]\nurl = "https://example.com"\ndefault = true\n',
            encoding='utf-8'
        )
        unset_uv_config()
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert '[[index]]' not in content
        assert 'key = "val"' in content

    def test_removes_multiple_index_blocks(self, fake_uv_config_path):
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text(
            '[[index]]\nurl = "https://a.com"\ndefault = true\n\n'
            '[[index]]\nurl = "https://b.com"\n',
            encoding='utf-8'
        )
        success, msg = unset_uv_config()
        assert success
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert '[[index]]' not in content
