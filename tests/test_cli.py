"""CLI 命令的集成/冒烟测试。

原则：
- 不发起真实网络请求（mock measure_mirror_speed）
- 不修改真实配置文件（mock get_pip_config_path_for_scope 和 get_uv_config_path）
- 覆盖 info、set（指定镜像）、set --uv、unset --uv 命令
"""
import sys
import pytest

import cnpip.cnpip as module
from cnpip.cnpip import main
from cnpip.mirrors import MIRRORS

MIRROR_URL = MIRRORS['tuna']


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """所有 CLI 测试都屏蔽真实网络请求。"""
    def _fake_speed(name, url):
        return name, 100.0, url, None

    monkeypatch.setattr(module, 'measure_mirror_speed', _fake_speed)


class TestInfoCommand:
    def test_info_prints_version(self, capsys):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'info'])
        main()
        captured = capsys.readouterr()
        assert 'cnpip' in captured.out.lower()
        monkeypatch.undo()

    def test_info_prints_python_path(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'info'])
        main()
        captured = capsys.readouterr()
        assert 'Python' in captured.out

    def test_info_prints_env_type(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'info'])
        main()
        captured = capsys.readouterr()
        assert '环境类型' in captured.out

    def test_info_prints_pip_section(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'info'])
        main()
        captured = capsys.readouterr()
        assert 'Pip' in captured.out

    def test_info_prints_uv_section(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'info'])
        main()
        captured = capsys.readouterr()
        assert 'uv' in captured.out.lower()


class TestSetUvCommand:
    def test_set_uv_writes_config(self, monkeypatch, fake_uv_config_path, capsys):
        # mirror 位置参数必须在 --uv flag 前面（或后面均可，但前面更安全）
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--uv'])
        # 模拟 uv 已安装
        monkeypatch.setattr(module, 'detect_uv_binary', lambda: '/usr/bin/uv')

        # 成功时 main() 直接返回（不调用 sys.exit）
        main()

        assert fake_uv_config_path.exists()
        content = fake_uv_config_path.read_text(encoding='utf-8')
        assert MIRROR_URL in content

    def test_set_uv_fails_gracefully_when_no_uv(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--uv'])
        monkeypatch.setattr(module, 'detect_uv_binary', lambda: None)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        # 错误信息在 stdout 或 stderr 中
        combined = (captured.out + captured.err).lower()
        assert 'uv' in combined

    def test_set_uv_invalid_mirror(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'nonexistent_mirror', '--uv'])
        monkeypatch.setattr(module, 'detect_uv_binary', lambda: '/usr/bin/uv')

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


class TestUnsetUvCommand:
    def test_unset_uv_succeeds(self, monkeypatch, fake_uv_config_path, capsys):
        # 先写入配置
        fake_uv_config_path.parent.mkdir(parents=True, exist_ok=True)
        fake_uv_config_path.write_text(
            '[[index]]\nurl = "https://example.com"\ndefault = true\n',
            encoding='utf-8'
        )
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'unset', '--uv'])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_unset_uv_graceful_when_no_config(self, monkeypatch, fake_uv_config_path, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'unset', '--uv'])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


class TestListCommand:
    def test_list_prints_mirror_header(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'list'])
        main()
        captured = capsys.readouterr()
        assert '镜像名称' in captured.out

    def test_list_prints_mirror_names(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'list'])
        main()
        captured = capsys.readouterr()
        assert 'tuna' in captured.out
        assert 'ustc' in captured.out
