from setuptools import setup, find_packages

setup(
    name="cnpip",
    version="1.0.0",
    description="帮助中国用户快速切换 pip 镜像源，提升下载速度的命令行工具/A tool that helps Chinese users quickly switch pip mirrors to improve download speeds.",
    author="caoergou",
    author_email="itsericsmail@gmail.com",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'cnpip=cnpip.cnpip:main',  # 指定命令行工具的入口
        ],
    },
    install_requires=[
        'requests'
    ],
)
