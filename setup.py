from setuptools import setup, find_packages

DEV_REQUIREMENTS = ["pytest>=7.0"]

QUALITY_REQUIREMENTS = [
    "ruff==0.11.13",
    "pyright==1.1.405",
]

setup(
    name="cnpip",
    version="1.6.0",
    description="面向中国网络环境的 Python 包管理镜像配置命令行工具，支持 pip、uv、PDM、Poetry 和 Conda。",
    author="caoergou",
    author_email="itsericsmail@gmail.com",
    url="https://github.com/caoergou/cnpip",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "cnpip=cnpip.cnpip:main",
        ],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Installation/Setup",
        "Topic :: Utilities",
    ],
    install_requires=[],
    extras_require={
        "dev": DEV_REQUIREMENTS,
        "quality": QUALITY_REQUIREMENTS,
    },
)
