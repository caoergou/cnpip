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

- **列出并测试镜像源速度**，按连接速度排序
- **快速切换 pip 镜像源**，支持*手动选择*或*自动选择*最快镜像

## 支持的镜像源

- [清华大学 TUNA](https://pypi.tuna.tsinghua.edu.cn/simple)
- [阿里云](https://mirrors.aliyun.com/pypi/simple)
- [中国科学技术大学](https://pypi.mirrors.ustc.edu.cn/simple)
- [豆瓣](https://pypi.douban.com/simple)（目前可能无法连接）
- [默认源](https://pypi.org/simple)

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
douban       error        https://pypi.douban.com/simple
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

`cnpip` 会修改或创建 `pip` 的配置文件来设置镜像源：

- **Linux/macOS**: `~/.pip/pip.conf`
- **Windows**: `%APPDATA%\pip\pip.ini`

在设置镜像源时，`cnpip` 只会修改或添加 `index-url` 配置，不会覆盖其他配置项。

## 常见问题

### 1. 为什么我无法连接到某些镜像源？

某些镜像源（如豆瓣）可能由于网络问题或镜像源本身的原因无法连接。在这种情况下，`cnpip` 会显示“无法连接”，并将其排在速度测试结果的最后。

### 2. 如何恢复为默认的 `pip` 镜像源？

使用 `unset` 命令恢复为默认的 `pip` 镜像源：

```bash
cnpip unset
```

### 3. `cnpip` 会覆盖我的 `pip.conf` 文件吗？

不会。`cnpip` 只会修改或添加 `index-url` 配置项，其他配置项会被保留。

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

- **List and test mirror speeds**, sorted by connection time
- **Quickly switch pip mirrors**, supporting *manual selection* or *automatic selection* of the fastest mirror
- Designed specifically for users in mainland China
