# cnpip

[中文](./README.md)

![PyPI](https://img.shields.io/pypi/v/cnpip)
![Python](https://img.shields.io/pypi/pyversions/cnpip)
![Tests](https://github.com/caoergou/cnpip/actions/workflows/test.yml/badge.svg)
![Quality](https://github.com/caoergou/cnpip/actions/workflows/quality.yml/badge.svg)
![License](https://img.shields.io/github/license/caoergou/cnpip)

`cnpip` configures Python package-manager mirrors for networks in China. It benchmarks available mirrors, then writes the selected one into the configuration you already use for `pip`, `uv`, `PDM`, `Poetry`, or `conda`.

It is not a proxy, cache, private package index, or replacement for a package manager. A mirror's real speed depends on your network, the mirror's health, and the package being fetched. cnpip makes choosing and reverting the configuration explicit.

## Start in 30 seconds

```bash
pip install cnpip
cnpip
```

In an interactive terminal, `cnpip` lists the package managers it detects, selects `pip` by default, benchmarks the PyPI mirrors, and applies the fastest available one.

When you already know what you want, choose it directly:

```bash
cnpip tuna                 # Same as: cnpip set tuna
cnpip set --uv             # Benchmark, then configure only uv
cnpip set tuna --pdm       # Configure TUNA only for PDM
cnpip set --conda          # Benchmark conda-specific mirrors, then configure conda
```

You can also run it temporarily without installing it:

```bash
uvx cnpip
```

In a `uvx` environment, the default target is the user-level uv configuration, not the short-lived tool environment.

## What it supports

| Tool | What cnpip manages | Where it is written |
| --- | --- | --- |
| `pip` | PyPI `index-url`; user, system, or virtual-environment scopes | Determined by `pip config` and the active environment |
| `uv` | A named `cnpip` index | User-level `uv.toml` |
| `PDM` | `pypi.url` | PDM user configuration |
| `Poetry` | A named `cnpip` source | The current project's `pyproject.toml` |
| `conda` | `default_channels` plus conda-forge and pytorch community channels | The file set by `CONDARC`, or `~/.condarc` by default |

Conda and PyPI mirrors are separate services, so cnpip keeps a separate conda mirror table. A PyPI mirror is not necessarily usable for conda.

## Common commands

| Goal | Command |
| --- | --- |
| List and benchmark all PyPI mirrors | `cnpip list` |
| Benchmark and set the fastest mirror | `cnpip` or `cnpip set` |
| Set a chosen PyPI mirror | `cnpip tuna` or `cnpip set tuna` |
| Configure exactly one tool | `cnpip set --uv`, `cnpip set --pdm`, `cnpip set --poetry`, or `cnpip set --conda` |
| Inspect the environment and active config paths | `cnpip info` |
| Restore configuration managed by cnpip | `cnpip unset`, optionally with `--uv`, `--pdm`, `--poetry`, or `--conda` |
| Refresh the mirror manifest | `cnpip sync` |

Scripts and CI skip the interactive tool picker. `-y` / `--yes` also skips it. An explicit `--uv`, `--pdm`, `--poetry`, or `--conda` flag limits the operation to that tool.

## Default targets

Without an explicit tool or pip scope, cnpip chooses a default target from the environment. Run `cnpip info` to see the file that is actually in use.

| Environment | Default target |
| --- | --- |
| `uvx` temporary tool environment | User-level `uv.toml` (uv) |
| uv virtual environment, conda environment, or regular venv | Environment-level pip `--site` config |
| System Python or pipx | User-level pip `--user` config |

Choose a fixed pip scope when needed:

```bash
cnpip set --user       # User-level pip config
cnpip set --venv       # pip config for the active virtual environment
cnpip set --global     # System-wide pip config; usually requires elevation

cnpip unset --user     # Restore the recorded user-level pip config
cnpip unset --global   # Restore the recorded system-wide pip config
```

Microsoft Store Python cannot reliably write system-wide configuration; use `--user`. For other Windows installations, open the terminal as Administrator before using `--global`.

## Explicit configuration by tool

```bash
# pip and uv
cnpip set tuna
cnpip set tuna --uv

# PDM: writes user-level `pdm config pypi.url`
cnpip set tuna --pdm

# Poetry: run in a project root; writes that project's pyproject.toml
cnpip set tuna --poetry

# conda: chooses only from conda-supported mirrors
cnpip set --conda
```

Poetry has no global mirror-source configuration. If `cnpip set --poetry` reports that `pyproject.toml` is missing, change to the Poetry project root first.

## Benchmarking and recovery

- PyPI probes use the real PEP 503 `simple/pip/` page; conda probes use `pkgs/main/noarch/repodata.json`.
- Each candidate is requested three times. cnpip uses the median response time and requires at least two successes.
- For pip, uv, Poetry, and conda, cnpip records the target file's original state and its post-change fingerprint. For PDM, it records the before and after values of `pypi.url`. `unset` restores only configuration managed by that cnpip operation.
- If another program or a manual edit changed the target afterwards, `unset` refuses to overwrite it.
- When cnpip writes pip or uv configuration directly, it uses a same-directory temporary file followed by an atomic replacement. PDM, Poetry, and conda configuration is delegated to their own CLIs. In an interactive batch, a later failure attempts to roll back tools already configured and reports any tool it could not restore.
- HTTPS mirrors do not get `trusted-host`; that pip setting bypasses TLS verification and is only relevant to HTTP mirrors.

## Mirror catalog

| Name | Shorthand | PyPI URL |
| --- | --- | --- |
| Tsinghua University TUNA | `tuna` | https://pypi.tuna.tsinghua.edu.cn/simple |
| University of Science and Technology of China | `ustc` | https://pypi.mirrors.ustc.edu.cn/simple |
| Aliyun | `aliyun` | https://mirrors.aliyun.com/pypi/simple |
| Tencent | `tencent` | https://mirrors.cloud.tencent.com/pypi/simple |
| Huawei | `huawei` | https://repo.huaweicloud.com/repository/pypi/simple |
| Westlake University | `westlake` | https://mirrors.westlake.edu.cn/pypi/simple |
| Southern University of Science and Technology | `sustech` | https://mirrors.sustech.edu.cn/pypi/web/simple |
| Official PyPI | `default` | https://pypi.org/simple |

Run `cnpip sync` to fetch an updated mirror manifest. Remote entries can add mirrors, but only valid PEP 503 URLs with HTTPS and no credentials, port, or query parameters are accepted. Invalid entries are not saved locally.

## Troubleshooting

### `cnpip unset` refuses to restore a configuration

The target changed after cnpip set it. Review the current configuration and any changes that must be retained, then restore it manually if appropriate. Do not overwrite an unknown change blindly.

### `--global` fails

- Linux/macOS: run `sudo cnpip set --global`.
- Windows: run PowerShell or Command Prompt as Administrator; with Microsoft Store Python, use `--user` instead.

### Does a `uvx cnpip` configuration disappear?

No. cnpip writes the user-level uv configuration: usually `~/.config/uv/uv.toml` on Linux/macOS and `%APPDATA%\\uv\\uv.toml` on Windows.

## License

This project is licensed under the [MIT License](LICENSE).
