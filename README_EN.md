# cnpip

[中文](./README.md)

![PyPI](https://img.shields.io/pypi/v/cnpip)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cnpip)
![License](https://img.shields.io/github/license/caoergou/cnpip)
![Tests](https://github.com/caoergou/cnpip/actions/workflows/test.yml/badge.svg)

`cnpip` is a command-line tool for users in **mainland China** to quickly switch `pip` mirrors and improve Python package download speeds. It benchmarks all mirrors concurrently, automatically selects the fastest one, and natively supports modern tools like `uv`.

## Quick Start

```bash
pip install cnpip
cnpip set
```

Or run via `uvx` without installing (automatically configures uv mirrors):

```bash
uvx cnpip set
```

## Features

- **One command, fastest mirror**: Concurrent latency tests across all mirrors — automatically picks and applies the winner
- **Native uv support**: Auto-writes `uv.toml` in uvx environments; use `--uv` for explicit control at any time
- **Smart environment detection**: Distinguishes uvx, conda, pipx, venv and selects the right config scope automatically — no manual flags needed
- **Fine-grained scope control**: `--user`, `--global`, `--venv`, `--uv` — full control when you need it
- **Cross-platform**: Linux, macOS, Windows (official installer, Microsoft Store, pyenv-win, Scoop, etc.)
- **Built-in diagnostics**: `cnpip info` shows pip config file paths, uv status, and full environment details

## Supported Mirrors

| Name | Shorthand | URL |
|------|-----------|-----|
| Tsinghua TUNA | `tuna` | https://pypi.tuna.tsinghua.edu.cn/simple |
| USTC | `ustc` | https://pypi.mirrors.ustc.edu.cn/simple |
| Aliyun | `aliyun` | https://mirrors.aliyun.com/pypi/simple |
| Tencent | `tencent` | https://mirrors.cloud.tencent.com/pypi/simple |
| Huawei | `huawei` | https://repo.huaweicloud.com/repository/pypi/simple |
| Westlake University | `westlake` | https://mirrors.westlake.edu.cn/pypi/simple |
| SUSTech | `sustech` | https://mirrors.sustech.edu.cn/pypi/web/simple |
| PyPI (default) | `default` | https://pypi.org/simple |

## Usage

### 1. List and benchmark all mirrors

```bash
cnpip list
```

Example output:

```
镜像名称      耗时/状态            地址
-----------------------------------------------------------------------------------
ustc         135.71 ms           https://pypi.mirrors.ustc.edu.cn/simple
aliyun       300.77 ms           https://mirrors.aliyun.com/pypi/simple
tuna         499.51 ms           https://pypi.tuna.tsinghua.edu.cn/simple
default      1252.75 ms          https://pypi.org/simple
huawei       Timeout             https://repo.huaweicloud.com/repository/pypi/simple
```

### 2. Switch pip mirror

```bash
cnpip set           # Auto-select the fastest mirror
cnpip set tuna      # Manually specify a mirror
```

**Default scope (auto-detected):**

| Environment | Auto-selected scope |
|-------------|---------------------|
| uvx temporary tool environment | Writes to `~/.config/uv/uv.toml` |
| uv venv / conda / venv | `--site` (virtualenv-level) |
| System / pipx | `--user` (user-level) |

**Explicit scope:**

```bash
cnpip set --user    # User-level config (~/.config/pip/pip.conf)
cnpip set --global  # System-wide config (requires admin/sudo)
cnpip set --venv    # Current virtualenv config
cnpip set --uv      # Write to uv config (~/.config/uv/uv.toml)
```

### 3. Unset mirror

```bash
cnpip unset         # Remove pip mirror config
cnpip unset --uv    # Remove uv mirror config
```

Scope flags work the same as `set`:

```bash
cnpip unset --user
cnpip unset --global
```

### 4. Diagnostics

```bash
cnpip info
```

Example output:

```
cnpip 版本: v1.3.1
Python 路径: /usr/bin/python3
操作系统: Linux 5.15.0
Pip 版本: pip 24.0 from ...
环境类型: 系统环境

--- 当前 Pip 配置 ---
当前镜像源: https://pypi.tuna.tsinghua.edu.cn/simple
信任主机: pypi.tuna.tsinghua.edu.cn
配置文件路径:
  /home/user/.config/pip/pip.conf

--- uv 信息 ---
uv 版本: uv 0.5.0
uv 配置文件: /home/user/.config/uv/uv.toml
uv 镜像源: https://pypi.tuna.tsinghua.edu.cn/simple
```

### 5. Update mirror list

Fetch the latest mirror list from GitHub:

```bash
cnpip update
```

## Configuration

`cnpip` automatically selects the right config file based on your environment. Run `cnpip info` to see the actual paths in use.

- **pip config**: Only modifies `global.index-url` and `global.trusted-host`; leaves everything else untouched
- **uv config**: Writes an `[[index]]` block to `uv.toml`; leaves all other uv settings untouched

## FAQ

### 1. How do I restore the default mirror?

```bash
cnpip unset        # Restore pip default
cnpip unset --uv   # Restore uv default
```

### 2. Will the config persist when using uvx?

Yes. When you run `uvx cnpip set`, cnpip detects the uvx environment and writes the config to `~/.config/uv/uv.toml` (Windows: `%APPDATA%\uv\uv.toml`). This persists permanently for all uv operations and is not tied to the temporary uvx environment.

### 3. Why does `--global` fail?

- **Linux / macOS**: Requires sudo — run `sudo cnpip set --global`
- **Windows (Microsoft Store Python)**: Blocked by sandbox restrictions — use `cnpip set --user` instead
- **Windows (other installations)**: Run PowerShell or Command Prompt as Administrator

### 4. How do I configure uv's mirror separately?

```bash
cnpip set --uv tuna    # Set uv to use TUNA mirror
cnpip set --uv         # Auto-select fastest mirror and write to uv config
```

## License

This project is licensed under the [MIT License](LICENSE).
