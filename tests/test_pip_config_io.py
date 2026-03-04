"""测试直接读写 pip 配置文件（不依赖 pip 命令）。"""
import configparser
import pytest

from cnpip.cnpip import write_pip_config_directly, unset_pip_config_directly

MIRROR_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'
ALT_URL = 'https://mirrors.aliyun.com/pypi/simple'
MIRROR_HOST = 'pypi.tuna.tsinghua.edu.cn'
ALT_HOST = 'mirrors.aliyun.com'


def read_config(path):
    cfg = configparser.ConfigParser()
    cfg.read(str(path), encoding='utf-8')
    return cfg


class TestWritePipConfigDirectly:
    def test_creates_config_file(self, fake_pip_config_path):
        success, msg = write_pip_config_directly(MIRROR_URL, 'user')
        assert success, msg
        config_file = fake_pip_config_path / 'pip.conf'
        assert config_file.exists()

    def test_writes_index_url(self, fake_pip_config_path):
        write_pip_config_directly(MIRROR_URL, 'user')
        cfg = read_config(fake_pip_config_path / 'pip.conf')
        assert cfg.get('global', 'index-url') == MIRROR_URL

    def test_writes_trusted_host(self, fake_pip_config_path):
        write_pip_config_directly(MIRROR_URL, 'user')
        cfg = read_config(fake_pip_config_path / 'pip.conf')
        assert cfg.get('global', 'trusted-host') == MIRROR_HOST

    def test_creates_parent_directories(self, fake_pip_config_path):
        # fake_pip_config_path 目录此时还不存在
        assert not fake_pip_config_path.exists()
        success, msg = write_pip_config_directly(MIRROR_URL, 'user')
        assert success, msg
        assert fake_pip_config_path.exists()

    def test_updates_existing_config(self, fake_pip_config_path):
        write_pip_config_directly(MIRROR_URL, 'user')
        success, msg = write_pip_config_directly(ALT_URL, 'user')
        assert success, msg
        cfg = read_config(fake_pip_config_path / 'pip.conf')
        assert cfg.get('global', 'index-url') == ALT_URL
        assert cfg.get('global', 'trusted-host') == ALT_HOST

    def test_preserves_other_config_sections(self, fake_pip_config_path):
        # 预先写入其他配置
        config_file = fake_pip_config_path / 'pip.conf'
        fake_pip_config_path.mkdir(parents=True, exist_ok=True)
        existing_cfg = configparser.ConfigParser()
        existing_cfg['install'] = {'timeout': '60'}
        with open(config_file, 'w', encoding='utf-8') as f:
            existing_cfg.write(f)

        write_pip_config_directly(MIRROR_URL, 'user')
        cfg = read_config(config_file)
        assert cfg.get('global', 'index-url') == MIRROR_URL
        # 已有的 [install] 节应被保留
        assert cfg.has_section('install')
        assert cfg.get('install', 'timeout') == '60'

    def test_message_contains_mirror_url(self, fake_pip_config_path):
        success, msg = write_pip_config_directly(MIRROR_URL, 'user')
        assert success
        assert MIRROR_URL in msg

    def test_message_contains_config_path(self, fake_pip_config_path):
        success, msg = write_pip_config_directly(MIRROR_URL, 'user')
        assert success
        assert 'pip.conf' in msg

    def test_invalid_scope_returns_failure(self):
        # 不使用 fake_pip_config_path，让真实函数返回 None（无效 scope）
        success, msg = write_pip_config_directly(MIRROR_URL, 'invalid_scope')
        assert not success


class TestUnsetPipConfigDirectly:
    def test_removes_index_url(self, fake_pip_config_path):
        write_pip_config_directly(MIRROR_URL, 'user')
        success, msg = unset_pip_config_directly('user')
        assert success, msg
        cfg = read_config(fake_pip_config_path / 'pip.conf')
        assert not cfg.has_option('global', 'index-url')

    def test_removes_trusted_host(self, fake_pip_config_path):
        write_pip_config_directly(MIRROR_URL, 'user')
        unset_pip_config_directly('user')
        cfg = read_config(fake_pip_config_path / 'pip.conf')
        assert not cfg.has_option('global', 'trusted-host')

    def test_graceful_when_file_not_exists(self, fake_pip_config_path):
        # 文件不存在时应该成功（什么也不用做）
        success, msg = unset_pip_config_directly('user')
        assert success

    def test_graceful_when_no_mirror_set(self, fake_pip_config_path):
        # 文件存在但没有设置镜像源
        config_file = fake_pip_config_path / 'pip.conf'
        fake_pip_config_path.mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        cfg['global'] = {'timeout': '30'}
        with open(config_file, 'w', encoding='utf-8') as f:
            cfg.write(f)
        success, msg = unset_pip_config_directly('user')
        assert success

    def test_preserves_other_options_after_unset(self, fake_pip_config_path):
        # 写入带镜像源的配置
        config_file = fake_pip_config_path / 'pip.conf'
        fake_pip_config_path.mkdir(parents=True, exist_ok=True)
        existing_cfg = configparser.ConfigParser()
        existing_cfg['global'] = {
            'index-url': MIRROR_URL,
            'trusted-host': MIRROR_HOST,
            'timeout': '60',
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            existing_cfg.write(f)

        unset_pip_config_directly('user')
        cfg = read_config(config_file)
        assert not cfg.has_option('global', 'index-url')
        assert cfg.has_option('global', 'timeout')
        assert cfg.get('global', 'timeout') == '60'
