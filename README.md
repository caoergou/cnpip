# cnpip

![PyPI](https://img.shields.io/pypi/v/cnpip)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cnpip)
![License](https://img.shields.io/github/license/caoergou/cnpip)

`cnpip` 是一个帮助你快速切换 `pip` 镜像源，提升 Python 包的下载速度的命令行工具。  
它可以测试各镜像源的连接速度，并**自动选择最快的镜像源**。

## 快速使用

运行以下命令，快速切换为最快的镜像源：

```bash
pip install cnpip
cnpip set
```

## 功能

- **列出并测试镜像源速度**，按连接速度排序，并显示具体错误信息（如超时、状态码）
- **快速切换 pip 镜像源**，支持*手动选择*或*自动选择*最快镜像
- **灵活的配置作用域**，支持设置全局、当前用户或当前虚拟环境的配置
- **诊断功能**，查看当前 Python/Pip 环境及配置信息
- **远程更新**，从 GitHub 获取最新的镜像源列表

## 支持的镜像源

- [清华大学 TUNA](https://pypi.tuna.tsinghua.edu.cn/simple)
- [中国科学技术大学 USTC](https://pypi.mirrors.ustc.edu.cn/simple)
- [阿里云 Aliyun](https://mirrors.aliyun.com/pypi/simple)
- [腾讯 Tencent](https://mirrors.cloud.tencent.com/pypi/simple)
- [华为 Huawei](https://repo.huaweicloud.com/repository/pypi/simple)
- [西湖大学 Westlake University](https://mirrors.westlake.edu.cn)
- [南方科技大学 SUSTech](https://mirrors.sustech.edu.cn/pypi/web/simple)
- [默认源 PyPi](https://pypi.org/simple)

## 使用方法

### 1. 列出所有可用的镜像源

```bash
cnpip list
```

示例输出：

```
镜像名称       耗时/状态            地址
-----------------------------------------------------------------------------------
ustc         135.71 ms           https://pypi.mirrors.ustc.edu.cn/simple
aliyun       300.77 ms           https://mirrors.aliyun.com/pypi/simple
tuna         499.51 ms           https://pypi.tuna.tsinghua.edu.cn/simple
default      1252.75 ms          https://pypi.org/simple
huawei       Timeout             https://repo.huaweicloud.com/repository/pypi/simple
```

### 2. 自动选择最快的镜像源

```bash
cnpip set
```

默认行为：
*   **在虚拟环境中**：默认设置到当前环境 (`--site`)。
*   **在系统环境中**：默认设置到当前用户 (`--user`)。

你也可以显式指定作用域：

```bash
cnpip set --user    # 强制设置用户级配置
cnpip set --global  # 强制设置系统全局配置 (需要管理员权限)
cnpip set --venv    # 强制设置当前虚拟环境配置
```

### 3. 选择指定的镜像源

```bash
cnpip set <镜像名称>
```

示例：

```bash
cnpip set tuna
```

### 4. 诊断与信息

查看当前 Python 路径、Pip 版本以及生效的配置文件位置：

```bash
cnpip info
```

### 5. 更新镜像源列表

从 GitHub 获取最新的镜像源列表：

```bash
cnpip update
```

### 6. 取消自定义镜像源设置

```bash
cnpip unset
```

同样支持指定作用域：
```bash
cnpip unset --user
```

## 配置文件

`cnpip` 默认根据你的环境智能选择修改哪个配置文件。你可以通过 `cnpip info` 查看当前生效的配置。

在设置镜像源时，`cnpip` 只会修改或添加 `global.index-url` 和 `global.trusted-host` 配置，不会覆盖其他配置项。

## 常见问题

### 1. 为什么我无法连接到某些镜像源？

网络问题可能导致连接失败。`cnpip list` 现在会显示具体的错误信息（如 `Timeout` 或 `Status 404`），帮助你排查问题。

### 2. 如何恢复为默认的 `pip` 镜像源？

使用 `unset` 命令恢复为默认的 `pip` 镜像源：

```bash
cnpip unset
```

### 3. 在 uvx 或 pipx 临时环境中使用？

在这些临时环境中，`cnpip` 会检测并建议你使用 `--user` 选项，或者直接输出配置命令供你复制执行，以确保配置能持久化到你的用户配置中，而不是随着临时环境消失。

## 许可证

本项目使用 [MIT 许可证](LICENSE)。

---

# cnpip (English)

`cnpip` is a command-line tool designed specifically for users in **mainland China** to help quickly switch `pip`
mirrors and improve Python package download speeds.       
It tests the connection speed of various mirrors and **automatically selects the fastest one**.

> **Attention: This Python package is only available in Chinese mainland.**

## Quick Start

Run the following commands to quickly switch to the fastest mirror:

```bash
pip install cnpip
cnpip set
```

## Features

- **List and test mirror speeds**, with detailed error reporting.
- **Quickly switch pip mirrors**, supporting *manual selection* or *automatic selection*.
- **Flexible Scopes**: Support `--user`, `--global`, and `--venv` (site) configuration.
- **Diagnostics**: `cnpip info` to view environment and config details.
- **Remote Update**: `cnpip update` to fetch the latest mirror list from GitHub.

## Usage

### Switch Mirror

```bash
cnpip set              # Auto-detect fastest and set (smart scope)
cnpip set tuna         # Set specifically to TUNA mirror
cnpip set --user       # Force user-level config
cnpip set --venv       # Force virtualenv config
```

### Other Commands

```bash
cnpip list     # List mirrors and speeds
cnpip info     # Show environment info
cnpip update   # Update mirror list from remote
cnpip unset    # Restore default pip source
```
