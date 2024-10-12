from setuptools import setup, find_packages

setup(
    name="cnpip",
    version="1.1.0",
    description="""帮助中国用户快速切换 pip 镜像源，提升下载速度的命令行工具
A tool helps Chinese users quickly switch pip mirrors to improve download speeds.""",
    author="caoergou",
    author_email="itsericsmail@gmail.com",
    url="https://github.com/caoergou/cnpip",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'cnpip=cnpip.cnpip:main',
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
    install_requires=[
        "requests"
    ],
    extras_require={
        "async": ["aiohttp"]
    }
)
