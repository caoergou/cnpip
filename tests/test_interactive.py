"""测试交互式 cnpip set（工具扫描、选择解析、批量应用）。"""
import sys

import pytest

import cnpip.cnpip as module
from cnpip.cnpip import (
    apply_mirror_to_tool,
    default_tool_selection,
    main,
    parse_tool_selection,
    run_interactive_set,
)

TOOL_NAMES = ['pip', 'uv', 'pdm', 'conda']


class TestParseToolSelection:
    def test_empty_returns_default(self):
        assert parse_tool_selection('', TOOL_NAMES, ['pip']) == ['pip']
        assert parse_tool_selection('  ', TOOL_NAMES, ['uv']) == ['uv']

    def test_all_keyword(self):
        for raw in ('a', 'all', 'A', '全部'):
            assert parse_tool_selection(raw, TOOL_NAMES, ['pip']) == TOOL_NAMES

    def test_single_number(self):
        assert parse_tool_selection('2', TOOL_NAMES, ['pip']) == ['uv']

    def test_multiple_numbers_space_and_comma(self):
        assert parse_tool_selection('1 3', TOOL_NAMES, ['pip']) == ['pip', 'pdm']
        assert parse_tool_selection('1,3', TOOL_NAMES, ['pip']) == ['pip', 'pdm']
        assert parse_tool_selection('1，4', TOOL_NAMES, ['pip']) == ['pip', 'conda']

    def test_duplicates_removed(self):
        assert parse_tool_selection('2 2 2', TOOL_NAMES, ['pip']) == ['uv']

    def test_out_of_range_is_invalid(self):
        assert parse_tool_selection('5', TOOL_NAMES, ['pip']) is None
        assert parse_tool_selection('0', TOOL_NAMES, ['pip']) is None

    def test_non_numeric_is_invalid(self):
        assert parse_tool_selection('pip', TOOL_NAMES, ['pip']) is None
        assert parse_tool_selection('1 x', TOOL_NAMES, ['pip']) is None


class TestDefaultToolSelection:
    def test_prefers_pip(self, monkeypatch):
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        assert default_tool_selection(['pip', 'uv', 'conda']) == ['pip']

    def test_uvx_env_prefers_uv(self, monkeypatch):
        monkeypatch.setattr(module, 'detect_environment', lambda: 'uvx')
        assert default_tool_selection(['pip', 'uv']) == ['uv']

    def test_falls_back_to_first_tool(self, monkeypatch):
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        assert default_tool_selection(['pdm', 'conda']) == ['pdm']


class TestApplyMirrorToTool:
    def test_conda_uses_own_mirror_table(self, monkeypatch):
        received = {}
        monkeypatch.setattr(module, 'set_conda_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        ok = apply_mirror_to_tool('conda', 'tuna', module.MIRRORS['tuna'], None)
        assert ok
        assert received['url'] == module.CONDA_MIRRORS['tuna']

    def test_conda_rebenchmarks_when_mirror_has_no_conda(self, monkeypatch):
        # aliyun 无 conda 镜像：应单独测速并回落到可用的 conda 镜像
        received = {}
        monkeypatch.setattr(module, 'choose_fastest_mirror', lambda mirrors: 'ustc')
        monkeypatch.setattr(module, 'set_conda_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        ok = apply_mirror_to_tool('conda', 'aliyun', module.MIRRORS['aliyun'], None)
        assert ok
        assert received['url'] == module.CONDA_MIRRORS['ustc']

    def test_pdm_routes_to_pdm(self, monkeypatch):
        received = {}
        monkeypatch.setattr(module, 'set_pdm_mirror',
                            lambda url: received.update(url=url) or (True, 'ok'))
        assert apply_mirror_to_tool('pdm', 'tuna', module.MIRRORS['tuna'], None)
        assert received['url'] == module.MIRRORS['tuna']

    def test_failure_propagates(self, monkeypatch):
        monkeypatch.setattr(module, 'set_pdm_mirror', lambda url: (False, 'boom'))
        assert not apply_mirror_to_tool('pdm', 'tuna', module.MIRRORS['tuna'], None)


class TestRunInteractiveSet:
    def _make_args(self, mirror=None):
        from types import SimpleNamespace
        return SimpleNamespace(mirror=mirror, global_=False, user=False, venv=False)

    def test_applies_to_selected_tools(self, monkeypatch, capsys):
        monkeypatch.setattr(module, 'scan_available_tools',
                            lambda: [('pip', ''), ('uv', ''), ('pdm', '')])
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        monkeypatch.setattr('builtins.input', lambda prompt: '2 3')

        applied = []
        monkeypatch.setattr(module, 'apply_mirror_to_tool',
                            lambda tool, name, url, args: applied.append(tool) or True)

        with pytest.raises(SystemExit) as exc_info:
            run_interactive_set(self._make_args(mirror='tuna'))
        assert exc_info.value.code == 0
        assert applied == ['uv', 'pdm']

    def test_enter_uses_default(self, monkeypatch, capsys):
        monkeypatch.setattr(module, 'scan_available_tools',
                            lambda: [('pip', ''), ('uv', '')])
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        monkeypatch.setattr('builtins.input', lambda prompt: '')

        applied = []
        monkeypatch.setattr(module, 'apply_mirror_to_tool',
                            lambda tool, name, url, args: applied.append(tool) or True)

        with pytest.raises(SystemExit):
            run_interactive_set(self._make_args(mirror='tuna'))
        assert applied == ['pip']

    def test_no_tools_exits_with_error(self, monkeypatch, capsys):
        monkeypatch.setattr(module, 'scan_available_tools', lambda: [])
        with pytest.raises(SystemExit) as exc_info:
            run_interactive_set(self._make_args(mirror='tuna'))
        assert exc_info.value.code != 0

    def test_failed_tool_gives_nonzero_exit(self, monkeypatch, capsys):
        monkeypatch.setattr(module, 'scan_available_tools', lambda: [('pip', '')])
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        monkeypatch.setattr('builtins.input', lambda prompt: '1')
        monkeypatch.setattr(module, 'apply_mirror_to_tool',
                            lambda tool, name, url, args: False)

        with pytest.raises(SystemExit) as exc_info:
            run_interactive_set(self._make_args(mirror='tuna'))
        assert exc_info.value.code != 0

    def test_failed_batch_rolls_back_completed_tools(self, monkeypatch, capsys):
        monkeypatch.setattr(module, 'scan_available_tools',
                            lambda: [('uv', ''), ('pdm', '')])
        monkeypatch.setattr(module, 'detect_environment', lambda: 'system')
        monkeypatch.setattr('builtins.input', lambda prompt: '1 2')

        applied = []
        monkeypatch.setattr(
            module,
            'apply_mirror_to_tool',
            lambda tool, name, url, args: applied.append(tool) or tool == 'uv',
        )
        rolled_back = []
        monkeypatch.setattr(
            module,
            'rollback_mirror_from_tool',
            lambda tool, args: rolled_back.append(tool) or (True, 'ok'),
        )

        with pytest.raises(SystemExit) as exc_info:
            run_interactive_set(self._make_args(mirror='tuna'))

        assert exc_info.value.code != 0
        assert applied == ['uv', 'pdm']
        assert rolled_back == ['uv']


class TestCliTrigger:
    def test_tty_without_flags_enters_interactive(self, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna'])
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)

        called = []

        def _fake_interactive(args):
            called.append(True)
            sys.exit(0)

        monkeypatch.setattr(module, 'run_interactive_set', _fake_interactive)
        with pytest.raises(SystemExit):
            main()
        assert called

    def test_yes_flag_skips_interactive(self, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--yes'])
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setattr(module, 'run_interactive_set',
                            lambda args: pytest.fail('should not enter interactive mode'))
        # 屏蔽真实 pip 配置写入
        monkeypatch.setattr(module, 'update_pip_config', lambda url, scope: True)

        main()

    def test_explicit_tool_flag_skips_interactive(self, monkeypatch, fake_uv_config_path):
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna', '--uv'])
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setattr(module, 'detect_uv_binary', lambda: '/usr/bin/uv')
        monkeypatch.setattr(module, 'run_interactive_set',
                            lambda args: pytest.fail('should not enter interactive mode'))

        main()
        assert fake_uv_config_path.exists()

    def test_non_tty_keeps_old_behavior(self, monkeypatch):
        # pytest 环境下 stdin 非 TTY：不应进入交互模式
        monkeypatch.setattr(sys, 'argv', ['cnpip', 'set', 'tuna'])
        monkeypatch.setattr(module, 'run_interactive_set',
                            lambda args: pytest.fail('should not enter interactive mode'))
        monkeypatch.setattr(module, 'update_pip_config', lambda url, scope: True)

        main()
