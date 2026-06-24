# utils/paths.py —— 资源路径工具
# 处理开发环境与打包环境的路径差异

import sys
import os
from pathlib import Path


def get_app_dir() -> Path:
    """获取应用程序根目录"""
    if getattr(sys, 'frozen', False):
        # 打包后，PyInstaller onefile/onedir模式
        if hasattr(sys, '_MEIPASS'):
            # onefile模式，资源在临时解压目录
            return Path(sys._MEIPASS)
        else:
            # onedir模式
            return Path(sys.executable).parent / "_internal"
    else:
        # 开发环境
        return Path(__file__).parent.parent


def get_resource_path(relative_path: str) -> Path:
    """获取资源文件的完整路径

    Args:
        relative_path: 相对于项目根目录的相对路径，如 "theme/theme.qss

    Returns:
        资源文件的绝对路径
    """
    return get_app_dir() / relative_path


def get_data_dir() -> Path:
    """获取 data 目录路径"""
    return get_resource_path("data")


def get_theme_dir() -> Path:
    """获取 theme 目录路径"""
    return get_resource_path("theme")
