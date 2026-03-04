# cnpip

![PyPI](https://img.shields.io/pypi/v/cnpip)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cnpip)
![License](https://img.shields.io/github/license/caoergou/cnpip)

`cnpip` 是一个帮助你快速切换 `pip` 镜像源，提升 Python 包下载速度的命令行工具。
它可以测试各镜像源的连接速度，**自动选择最快的镜像源**，并原生支持 `uv` 等现代包管理工具。

## 快速使用

```bash
pip install cnpip
cnpip set
```

或通过 `uvx` 临时运行（自动配置 uv 镜像源，无需安装）：

```bash
uvx cnpip set
```

## 功能

- **测速并切换镜像源**：并发测试所有镜像源延迟，按速度排序，自动选择最快镜像
- **原生支持 uv**：检测到 uvx 环境时自动配置 `uv.toml`，也可通过 `--uv` 显式配置
- **智能环境检测**：自动识别 uvx、uv 虚拟环境、conda、pipx、venv 等环境并选择合适的配置作用域
- **灵活的配置作用域**：支持 `--user`、`--global`、`--venv`、`--uv` 四种作用域
- **跨平台支持**：兼容 Linux、macOS 和 Windows（含商店版、pyenv-win、Scoop 等多种安装方式）
- **诊断功能**：显示当前环境类型、pip 配置文件实际路径、uv 安装状态与配置

## 支持的镜像源

| 名称 | 简写 | 地址 |
|------|------|------|
| 清华大学 TUNA | `tuna` | https://pypi.tuna.tsinghua.edu.cn/simple |
| 中国科学技术大学 USTC | `ustc` | https://pypi.mirrors.ustc.edu.cn/simple |
| 阿里云 Aliyun | `aliyun` | https://mirrors.aliyun.com/pypi/simple |
| 腾讯 Tencent | `tencent` | https://mirrors.cloud.tencent.com/pypi/simple |
| 华为 Huawei | `huawei` | https://repo.huaweicloud.com/repository/pypi/simple |
| 西湖大学 Westlake | `westlake` | https://mirrors.westlake.edu.cn/pypi/simple |
| 南方科技大学 SUSTech | `sustech` | https://mirrors.sustech.edu.cn/pypi/web/simple |
| 默认源 PyPI | `default` | https://pypi.org/simple |

## 使用方法

### 1. 列出所有可用的镜像源并测速

```bash
cnpip list
```

示例输出：

```
镜像名称      耗时/状态            地址
-----------------------------------------------------------------------------------
ustc         135.71 ms           https://pypi.mirrors.ustc.edu.cn/simple
aliyun       300.77 ms           https://mirrors.aliyun.com/pypi/simple
tuna         499.51 ms           https://pypi.tuna.tsinghua.edu.cn/simple
default      1252.75 ms          https://pypi.org/simple
huawei       Timeout             https://repo.huaweicloud.com/repository/pypi/simple
```

### 2. 切换 pip 镜像源

```bash
cnpip set           # 测速并自动选择最快镜像源
cnpip set tuna      # 手动指定镜像源
```

**默认配置作用域（自动检测）：**

| 当前环境 | 自动选择的作用域 |
|----------|-----------------|
| uvx 临时工具环境 | 写入 `~/.config/uv/uv.toml` |
| uv 虚拟环境 / conda / venv | `--site`（虚拟环境级） |
| 系统环境 / pipx | `--user`（用户级） |

**显式指定作用域：**

```bash
cnpip set --user    # 用户级配置（~/.config/pip/pip.conf）
cnpip set --global  # 系统全局配置（需要管理员权限）
cnpip set --venv    # 当前虚拟环境配置
cnpip set --uv      # 写入 uv 配置（~/.config/uv/uv.toml）
```

### 3. 取消自定义镜像源

```bash
cnpip unset         # 取消 pip 镜像源设置
cnpip unset --uv    # 移除 uv 镜像源配置
```

同样支持指定 pip 作用域：

```bash
cnpip unset --user
cnpip unset --global
```

### 4. 诊断与信息

```bash
cnpip info
```

示例输出：

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

### 5. 更新镜像源列表

从 GitHub 获取最新的镜像源列表：

```bash
cnpip update
```

## 配置文件

`cnpip` 会根据当前环境自动选择修改哪个配置文件。你可以通过 `cnpip info` 查看实际生效的配置文件路径。

- **pip 配置**：只修改 `global.index-url` 和 `global.trusted-host`，不影响其他配置项
- **uv 配置**：写入 `[[index]]` 块到 `uv.toml`，不影响其他 uv 配置

## 常见问题

### 1. 如何恢复为默认镜像源？

```bash
cnpip unset        # 恢复 pip 默认源
cnpip unset --uv   # 恢复 uv 默认源
```

### 2. 在 uvx 环境中使用时配置会持久化吗？

会。通过 `uvx cnpip set` 运行时，cnpip 检测到 uvx 环境后会自动配置写入 `~/.config/uv/uv.toml`（Windows 为 `%APPDATA%\uv\uv.toml`），对所有 uv 操作永久生效，不会随临时环境消失。

### 3. 为什么 `--global` 设置失败？

- **Linux / macOS**：需要 sudo 权限，请运行 `sudo cnpip set --global`
- **Windows 商店版 Python**：受沙盒限制，建议改用 `cnpip set --user`
- **其他 Windows**：请以管理员身份运行 PowerShell 后重试

### 4. 如何单独配置 uv 的镜像源？

```bash
cnpip set --uv tuna    # 配置 uv 使用清华镜像
cnpip set --uv         # 测速并自动选择最快镜像写入 uv
```

## 许可证

本项目使用 [MIT 许可证](LICENSE)。

---

# cnpip (English)

`cnpip` is a command-line tool for users in **mainland China** to quickly switch `pip` mirrors and improve Python package download speeds. It tests mirror latency concurrently, automatically selects the fastest one, and natively supports modern tools like `uv`.

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

- **Benchmark & switch mirrors**: Concurrent latency tests, sorted results, auto-select fastest
- **Native uv support**: Auto-configures `uv.toml` in uvx environments; explicit `--uv` flag available
- **Smart environment detection**: Identifies uvx, uv venv, conda, pipx, venv and selects the right config scope
- **Flexible scopes**: `--user`, `--global`, `--venv`, `--uv`
- **Cross-platform**: Linux, macOS, and Windows (Store, pyenv-win, Scoop, official installer, etc.)
- **Diagnostics**: Shows environment type, pip config file paths, uv status

## Usage

### Switch Mirror

```bash
cnpip set              # Auto-select fastest mirror (smart scope detection)
cnpip set tuna         # Set to TUNA mirror
cnpip set --user       # Force user-level pip config
cnpip set --venv       # Force virtualenv pip config
cnpip set --uv         # Write to uv.toml instead of pip config
cnpip set --uv tuna    # Write specific mirror to uv.toml
```

### Other Commands

```bash
cnpip list             # List all mirrors with latency
cnpip info             # Show environment, pip config paths, and uv status
cnpip update           # Fetch latest mirror list from GitHub
cnpip unset            # Restore default pip source
cnpip unset --uv       # Remove uv mirror configuration
```
