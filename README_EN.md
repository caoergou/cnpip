# cnpip

[中文](./README.md)

![PyPI](https://img.shields.io/pypi/v/cnpip)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cnpip)
![License](https://img.shields.io/github/license/caoergou/cnpip)
![Tests](https://github.com/caoergou/cnpip/actions/workflows/test.yml/badge.svg)

`cnpip` is a command-line tool for users in **mainland China** to quickly switch `pip` mirrors and improve Python package download speeds. It benchmarks all mirrors concurrently, automatically selects the fastest one, and natively supports modern tools like `uv`, `pdm`, `poetry`, and `conda`.

## Quick Start

```bash
pip install cnpip
cnpip
```

No arguments needed — just run `cnpip` and it benchmarks all mirrors then applies the fastest one.

Or run via `uvx` without installing (automatically configures uv mirrors):

```bash
uvx cnpip
```

You can also specify a mirror directly:

```bash
cnpip tuna          # equivalent to cnpip set tuna
```

## Features

- **One command, fastest mirror**: Concurrent latency tests across all mirrors — automatically picks and applies the winner
- **Real package-index probes**: Repeated GET requests to the PEP 503 `pip` project page, using median response latency instead of a single root-path HEAD request
- **Interactive multi-tool setup**: `cnpip set` scans installed package managers and configures the ones you pick in one go (`-y` to skip)
- **Native uv support**: Auto-writes `uv.toml` in uvx environments; use `--uv` for explicit control at any time
- **Covers the whole packaging ecosystem**: Configure pdm, poetry, and conda mirrors with `--pdm`, `--poetry`, `--conda`
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
镜像名称      响应延迟/状态        地址
-----------------------------------------------------------------------------------
ustc         135.71 ms           https://pypi.mirrors.ustc.edu.cn/simple
aliyun       300.77 ms           https://mirrors.aliyun.com/pypi/simple
tuna         499.51 ms           https://pypi.tuna.tsinghua.edu.cn/simple
default      1252.75 ms          https://pypi.org/simple
huawei       Timeout             https://repo.huaweicloud.com/repository/pypi/simple
```

### 2. Switch mirror

```bash
cnpip               # Auto-select the fastest mirror (same as cnpip set)
cnpip tuna          # Manually specify a mirror (same as cnpip set tuna)
cnpip set -y        # Skip the prompt and use the default behavior
```

When run in a terminal, `cnpip set` first scans installed package managers and lets you pick which ones to configure:

```
检测到以下包管理工具:

  1. pip      当前源: 默认
  2. uv       当前源: 默认
  3. conda    用户级 (~/.condarc)

请选择要配置的工具（编号，空格分隔多个；a=全部；回车=1 即 pip）:
```

Non-TTY environments (scripts/CI), explicit tool flags like `--uv`, and `-y` skip the prompt; if a tool fails during interactive batch setup, cnpip rolls back the tools already configured in that batch.

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

### 3. Restore cnpip configuration

```bash
cnpip unset         # Restore the pip config from before cnpip changed it
cnpip unset --uv    # Restore the uv config from before cnpip changed it
```

Scope flags work the same as `set`:

```bash
cnpip unset --user    # Restore the user-level config
cnpip unset --global  # Restore the system-level config
```

### 4. Diagnostics

```bash
cnpip info
```

Example output:

```
cnpip 版本: v1.6.0
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

### 5. Configure pdm / poetry / conda mirrors

```bash
cnpip set --pdm            # Benchmark and configure pdm (user-level pdm config)
cnpip set tuna --poetry    # Point the current poetry project at TUNA (writes pyproject.toml)
cnpip set --conda          # Benchmark and configure conda (writes ~/.condarc)

cnpip unset --pdm          # Restore the config from before cnpip changed it
cnpip unset --poetry
cnpip unset --conda
```

Notes:

- **pdm**: Writes user-level config (`pdm config pypi.url`), applies to all projects
- **poetry**: Poetry has no global mirror setting; the source is written to the current project's `pyproject.toml` (source name: `cnpip`) — run from the project root
- **conda**: Anaconda mirrors are a separate service from PyPI mirrors; currently `tuna`, `ustc`, `nju`, and `sustech` are supported, configuring `default_channels` plus the conda-forge / pytorch community channels

### 6. Sync mirror list

Fetch the latest mirror list (tries jsDelivr CDN first, then GitHub — no proxy needed in mainland China). Remote entries may add mirrors, but must use valid names, HTTPS, no credentials/ports/query parameters, and a PEP 503 path:

```bash
cnpip sync
```

## Configuration

`cnpip` automatically selects the right config file based on your environment. Run `cnpip info` to see the actual paths in use.

- **pip config**: Only modifies `global.index-url`; `global.trusted-host` is written only for http mirrors (trusted-host disables TLS verification, so https mirrors must not set it)
- **uv config**: Writes a named `[[index]]` block (`name = "cnpip"`) to `uv.toml`; leaves other indexes untouched
- **pdm config**: Written via `pdm config` to the user-level `config.toml`
- **poetry config**: Written via `poetry source add` to the current project's `pyproject.toml`
- **conda config**: Written via `conda config --prepend/--set` to `~/.condarc`, preserving existing default channels

## Safety and recovery

- Before changing a target, cnpip records the complete original file and stores the post-change fingerprint in `~/.cnpip/state.json`. On Linux/macOS the state directory and file use mode 700/600; on Windows privacy is provided by the default ACL of the user's profile directory.
- `unset` only restores configuration managed by the corresponding cnpip operation. If another program changed the file or value afterwards, cnpip refuses to overwrite it and exits nonzero.
- File writes use a same-directory temporary file and atomic replacement. Interactive multi-tool setup rolls back tools that succeeded when a later tool fails.
- `cnpip sync` validates the remote manifest before saving it. PyPI probes issue three GET requests to `simple/pip/`; conda probes use `pkgs/main/noarch/repodata.json`. Both use the median and require at least two successful responses.

## FAQ

### 1. How do I restore the config from before cnpip?

```bash
cnpip unset        # Restore the pip config from before cnpip
cnpip unset --uv   # Restore the uv config from before cnpip
```

If the config changed after cnpip applied it, cnpip reports drift and refuses to overwrite the file. Review the difference manually first.

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

### 5. Why does `--conda` support fewer mirrors than pip?

Anaconda mirrors are an independent service from PyPI mirrors, and not every PyPI mirror site also hosts an anaconda mirror (Aliyun, for example, has discontinued theirs). cnpip only lists conda mirrors verified to be working.

### 6. Why does `cnpip set --poetry` require a pyproject.toml?

Poetry has no global mirror setting — sources can only be written into a specific project's `pyproject.toml`. `cd` into your poetry project root first.

## License

This project is licensed under the [MIT License](LICENSE).
