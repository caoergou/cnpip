# cnpip

[English](./README_EN.md)

![PyPI](https://img.shields.io/pypi/v/cnpip)
![Python](https://img.shields.io/pypi/pyversions/cnpip)
![Tests](https://github.com/caoergou/cnpip/actions/workflows/test.yml/badge.svg)
![Quality](https://github.com/caoergou/cnpip/actions/workflows/quality.yml/badge.svg)
![License](https://img.shields.io/github/license/caoergou/cnpip)

`cnpip` 是为中国网络环境准备的 Python 包管理镜像配置工具。它会测试可用镜像，并把选中的镜像写入你已经在使用的 `pip`、`uv`、`PDM`、`Poetry` 或 `Conda` 配置。

它不提供代理、缓存或私有包仓库，也不会改变包管理器本身的解析规则。镜像是否更快取决于你所在的网络、镜像站状态和包的实际内容；`cnpip` 做的是把配置过程变得可观察、可恢复。

## 30 秒开始

```bash
pip install cnpip
cnpip
```

在交互终端中，`cnpip` 会列出已检测到的包管理工具，默认选择 `pip`，测速后应用最快的可用 PyPI 镜像。

已有明确选择时，可以直接指定镜像：

```bash
cnpip tuna                 # 等同于 cnpip set tuna
cnpip set --uv             # 测速后只配置 uv
cnpip set tuna --pdm       # 只为 PDM 配置清华镜像
cnpip set --conda          # 对 Conda 专用镜像测速后配置 Conda
```

也可以不安装而临时运行：

```bash
uvx cnpip
```

在 `uvx` 环境中，默认目标是用户级 uv 配置，而不是短生命周期的临时环境。

## 支持什么

| 工具 | cnpip 的操作范围 | 配置位置 |
| --- | --- | --- |
| `pip` | 配置 PyPI `index-url`；可选用户、系统或虚拟环境作用域 | 由 `pip config` 和当前环境决定 |
| `uv` | 添加或恢复名为 `cnpip` 的索引 | 用户级 `uv.toml` |
| `PDM` | 设置或恢复 `pypi.url` | PDM 用户级配置 |
| `Poetry` | 添加或移除名为 `cnpip` 的源 | 当前项目的 `pyproject.toml` |
| `Conda` | 配置或恢复 `default_channels`、conda-forge 与 pytorch 社区源 | 用户级 `~/.condarc` |

`Conda` 镜像和 PyPI 镜像是两套服务，因此它使用独立的镜像表；不是每个 PyPI 镜像都能用于 Conda。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 查看所有 PyPI 镜像的测速结果 | `cnpip list` |
| 测速并自动设置 | `cnpip` 或 `cnpip set` |
| 设置指定的 PyPI 镜像 | `cnpip tuna` 或 `cnpip set tuna` |
| 只配置一个工具 | `cnpip set --uv`、`cnpip set --pdm`、`cnpip set --poetry`、`cnpip set --conda` |
| 查看环境和实际配置文件 | `cnpip info` |
| 恢复 cnpip 管理的配置 | `cnpip unset`，或追加 `--uv`、`--pdm`、`--poetry`、`--conda` |
| 更新镜像清单 | `cnpip sync` |

脚本、CI 等非交互环境会跳过工具选择；`-y`／`--yes` 也会跳过交互。显式指定 `--uv`、`--pdm`、`--poetry` 或 `--conda` 时，只会操作对应工具。

## pip 的配置作用域

未显式指定作用域时，`cnpip` 会根据环境选择。可用 `cnpip info` 查看最终使用的配置文件。

| 当前环境 | 默认作用域 |
| --- | --- |
| `uvx` 临时工具环境 | 写入用户级 `uv.toml` |
| uv 虚拟环境、Conda 环境或普通 venv | 当前环境的 `--site` 配置 |
| 系统 Python 或 pipx | 用户级 `--user` 配置 |

需要固定作用域时：

```bash
cnpip set --user       # 用户级 pip 配置
cnpip set --venv       # 当前虚拟环境的 pip 配置
cnpip set --global     # 系统级 pip 配置，通常需要管理员权限

cnpip unset --user     # 按记录恢复用户级 pip 配置
cnpip unset --global   # 按记录恢复系统级 pip 配置
```

Windows 商店版 Python 不能可靠地写系统级配置，建议使用 `--user`。其他 Windows 安装方式需要以管理员身份运行终端后，才能使用 `--global`。

## 各工具的明确配置方式

```bash
# pip 和 uv
cnpip set tuna
cnpip set tuna --uv

# PDM：写入用户级 `pdm config pypi.url`
cnpip set tuna --pdm

# Poetry：在项目根目录运行，写入当前项目的 pyproject.toml
cnpip set tuna --poetry

# Conda：仅从 Conda 支持的镜像中选择
cnpip set --conda
```

`Poetry` 没有全局镜像源配置。如果 `cnpip set --poetry` 提示缺少 `pyproject.toml`，请先进入 Poetry 项目根目录。

## 如何测速与恢复

- PyPI 测速请求真实的 PEP 503 `simple/pip/` 页面；Conda 测速请求 `pkgs/main/noarch/repodata.json`。
- 每个候选源连续请求三次，取中位响应时间；至少两次成功才会被视为可用。
- 设置前会保存原始状态，并记录 cnpip 写入后的指纹。`unset` 只恢复由对应 cnpip 操作管理的配置。
- 如果配置在设置后被其他程序或人工改动，`unset` 会拒绝覆盖，避免误删后续修改。
- 配置文件采用同目录临时文件加原子替换。交互式批量设置中，后一个工具失败时会反向恢复此前成功的工具。
- HTTPS 镜像不会写入 `trusted-host`；这个 pip 选项会跳过 TLS 校验，只有 HTTP 镜像才可能需要它。

## 镜像清单

| 名称 | 简写 | PyPI 地址 |
| --- | --- | --- |
| 清华大学 TUNA | `tuna` | https://pypi.tuna.tsinghua.edu.cn/simple |
| 中国科学技术大学 USTC | `ustc` | https://pypi.mirrors.ustc.edu.cn/simple |
| 阿里云 Aliyun | `aliyun` | https://mirrors.aliyun.com/pypi/simple |
| 腾讯 Tencent | `tencent` | https://mirrors.cloud.tencent.com/pypi/simple |
| 华为 Huawei | `huawei` | https://repo.huaweicloud.com/repository/pypi/simple |
| 西湖大学 Westlake | `westlake` | https://mirrors.westlake.edu.cn/pypi/simple |
| 南方科技大学 SUSTech | `sustech` | https://mirrors.sustech.edu.cn/pypi/web/simple |
| 官方 PyPI | `default` | https://pypi.org/simple |

使用 `cnpip sync` 可以获取更新后的镜像清单。远程条目可以新增镜像，但必须是合法名称、HTTPS、无凭据／端口／查询参数的 PEP 503 地址；不合规条目不会写入本地配置。

## 排错

### `cnpip unset` 拒绝恢复

这表示 cnpip 检测到配置在它设置后发生了变化。先人工确认当前配置和需要保留的改动，再决定是否手动恢复；不要强制覆盖未知修改。

### `--global` 失败

- Linux／macOS：使用 `sudo cnpip set --global`。
- Windows：以管理员身份运行 PowerShell 或命令提示符；商店版 Python 请改用 `--user`。

### `uvx cnpip` 的设置会不会消失

不会。cnpip 会写入用户级 uv 配置：Linux／macOS 通常是 `~/.config/uv/uv.toml`，Windows 通常是 `%APPDATA%\\uv\\uv.toml`。

## 许可证

本项目使用 [MIT 许可证](LICENSE)。
