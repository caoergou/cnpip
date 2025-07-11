# cnpip

![PyPI](https://img.shields.io/pypi/v/cnpip)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cnpip)
![License](https://img.shields.io/github/license/caoergou/cnpip)

`cnpip` 是一个帮助你快速切换 Python 包管理器镜像源的命令行工具，支持 **uv** 和 **pip**，提升 Python 包的下载速度。  
它可以测试各镜像源的连接速度，并**自动选择最快的镜像源**。支持现代化的 **uv** 包管理器，享受更快的构建体验。

## ✨ 特性

- 🚀 **支持 uv 和 pip** - 自动检测并配置现代化的 uv 包管理器和传统的 pip
- ⚡ **更快的包管理** - 推荐使用 uv 获得显著更快的包安装和依赖解析速度
- 🎯 **智能镜像选择** - 自动测试并选择最快的镜像源
- 🔧 **向后兼容** - 在没有 uv 的环境中自动回退到 pip

## 快速使用

### 使用 uv（推荐）

```bash
# 安装 uv（如果尚未安装）
pip install uv

# 安装 cnpip  
uv pip install cnpip

# 快速切换为最快的镜像源
cnpip set
```

### 使用传统 pip

```bash
pip install cnpip
cnpip set
```

## 功能

- **列出并测试镜像源速度**，按连接速度排序
- **快速切换包管理器镜像源**，支持*手动选择*或*自动选择*最快镜像
- **现代化 uv 支持**，享受更快的包安装和依赖解析速度
- **向后兼容**，在没有 uv 的环境中自动使用 pip

## 为什么选择 uv？

[uv](https://github.com/astral-sh/uv) 是一个用 Rust 编写的现代化 Python 包管理器，相比传统的 pip 有以下优势：

- ⚡ **速度更快** - 包安装速度比 pip 快 10-100 倍
- 🔒 **更好的依赖解析** - 更智能的依赖冲突解决
- 📦 **现代化设计** - 支持现代 Python 包管理最佳实践
- 🛠️ **易于使用** - 兼容 pip 的命令行界面

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
镜像名称       耗时(ms)     地址
--------------------------------------------------
ustc         135.71       https://pypi.mirrors.ustc.edu.cn/simple
aliyun       300.77       https://mirrors.aliyun.com/pypi/simple
tuna         499.51       https://pypi.tuna.tsinghua.edu.cn/simple
default      1252.75      https://pypi.org/simple
tencent      1253.07      https://mirrors.cloud.tencent.com/pypi/simple
```

### 2. 自动选择最快的镜像源

```bash
cnpip set
```

示例输出：

```
未指定镜像源，自动选择最快的镜像源: ustc
成功设置 pip 镜像源为 'https://pypi.mirrors.ustc.edu.cn/simple'
```

### 3. 选择指定的镜像源

```bash
cnpip set <镜像名称>
```

示例：

```bash
cnpip set tuna
```

输出：

```
成功设置 pip 镜像源为 'https://pypi.tuna.tsinghua.edu.cn/simple'
```

### 4. 取消自定义镜像源设置

```bash
cnpip unset
```

输出：

```
成功取消 pip 镜像源设置，已恢复为默认源。
```

## 配置文件

`cnpip` 会修改或创建包管理器的配置文件来设置镜像源：

### uv 配置文件
- **Linux/macOS**: `~/.config/uv/uv.toml`
- **Windows**: `%APPDATA%\uv\uv.toml`

### pip 配置文件
- **Linux/macOS**: `~/.pip/pip.conf`
- **Windows**: `%APPDATA%\pip\pip.ini`

在设置镜像源时，`cnpip` 只会修改或添加 `index-url` 配置，不会覆盖其他配置项。

## 常见问题

### 1. 如何安装和使用 uv？

```bash
# 安装 uv
pip install uv

# 验证安装
uv --version

# 使用 uv 安装包（比 pip 更快）
uv pip install package_name
```

### 2. 为什么我无法连接到某些镜像源？

某些镜像源（如豆瓣）可能由于网络问题或镜像源本身的原因无法连接。在这种情况下，`cnpip` 会显示“无法连接”，并将其排在速度测试结果的最后。

### 3. 如何恢复为默认的镜像源？

使用 `unset` 命令恢复为默认的镜像源：

```bash
cnpip unset
```

### 4. `cnpip` 会覆盖我的配置文件吗？

不会。`cnpip` 只会修改或添加 `index-url` 配置项，其他配置项会被保留。

### 5. 我可以同时使用 uv 和 pip 吗？

可以。`cnpip` 会自动检测系统中安装的包管理器，并同时为 uv 和 pip 配置镜像源。这样无论使用哪个工具都能享受到更快的下载速度。

## 许可证

本项目使用 [MIT 许可证](LICENSE)。

---

# cnpip (English)

`cnpip` is a command-line tool designed specifically for users in **mainland China** to help quickly switch Python package manager mirrors and improve Python package download speeds.       
It tests the connection speed of various mirrors and **automatically selects the fastest one**. Supports modern **uv** package manager for faster build experience.

## ✨ Features

- 🚀 **Supports uv and pip** - Automatically detects and configures modern uv package manager and traditional pip
- ⚡ **Faster package management** - Recommends using uv for significantly faster package installation and dependency resolution
- 🎯 **Smart mirror selection** - Automatically tests and selects the fastest mirror
- 🔧 **Backward compatible** - Automatically falls back to pip in environments without uv

> **Attention: This Python package is only available in Chinese mainland.**

## Quick Start

### Using uv (Recommended)

```bash
# Install uv (if not already installed)
pip install uv

# Install cnpip
uv pip install cnpip

# Quickly switch to the fastest mirror
cnpip set
```

### Using traditional pip

```bash
pip install cnpip
cnpip set
```

## Features

- **List and test mirror speeds**, sorted by connection time
- **Quickly switch package manager mirrors**, supporting *manual selection* or *automatic selection* of the fastest mirror
- **Modern uv support**, enjoy faster package installation and dependency resolution
- **Backward compatible**, automatically uses pip in environments without uv
