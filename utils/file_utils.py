# file_utils.py —— 文件操作工具模块
# 提供：递归复制、目录创建、ZIP/JAR 解压、原子写入等通用文件操作
# 所有操作都接受可选的 cancel_check 回调以支持中断

import shutil
import zipfile
import os
from pathlib import Path
from typing import Optional, Callable, List


def ensure_dir(path: Path):
    """确保目录存在，不存在则递归创建"""
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path, cancel_check: Optional[Callable[[], bool]] = None):
    """
    复制单个文件到目标路径。

    参数：
        src: 源文件路径
        dst: 目标文件路径
        cancel_check: 取消检查回调
    """
    if cancel_check and cancel_check():
        raise InterruptedError("复制操作已被取消")

    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def copy_directory(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
):
    """
    递归复制整个目录。

    使用 shutil.copytree，复制前先删除已存在的目标目录（若存在）。

    参数：
        src: 源目录路径
        dst: 目标目录路径
        progress_callback: 进度回调 (已复制文件数, 当前文件名)
        cancel_check: 取消检查回调
    """
    if cancel_check and cancel_check():
        raise InterruptedError("复制操作已被取消")

    # 如果目标已存在，先删除
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)

    # 确保目标父目录存在
    ensure_dir(dst.parent)

    # 先统计总文件数以提供准确进度
    total_files = sum(1 for _ in src.rglob("*") if _.is_file())
    copied_count = 0

    # 创建目标目录
    ensure_dir(dst)

    for item in src.iterdir():
        if cancel_check and cancel_check():
            raise InterruptedError("复制操作已被取消")

        dest_item = dst / item.name

        if item.is_dir():
            copy_directory(item, dest_item, progress_callback, cancel_check)
        else:
            copy_file(item, dest_item, cancel_check)
            copied_count += 1
            if progress_callback and total_files > 0:
                progress_callback(copied_count, item.name)


def copy_selected_folders(
    src_dir: Path,
    dst_dir: Path,
    folder_names: List[str],
    progress_callback: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
):
    """
    将源目录中指定的子文件夹复制到目标目录。

    参数：
        src_dir: 源根目录
        dst_dir: 目标根目录
        folder_names: 要复制的文件夹名称列表
        progress_callback: 进度回调
        cancel_check: 取消检查回调

    返回：
        成功复制的文件夹数量
    """
    if cancel_check and cancel_check():
        raise InterruptedError("复制操作已被取消")

    ensure_dir(dst_dir)
    copied = 0

    for name in folder_names:
        src_path = src_dir / name
        if src_path.exists() and src_path.is_dir():
            if cancel_check and cancel_check():
                raise InterruptedError("复制操作已被取消")
            dst_path = dst_dir / name
            copy_directory(src_path, dst_path, progress_callback, cancel_check)
            copied += 1

    return copied


def extract_zip(
    zip_path: Path,
    extract_to: Path,
    cancel_check: Optional[Callable[[], bool]] = None,
):
    """
    解压 ZIP/JAR 文件到指定目录。

    参数：
        zip_path: ZIP 文件路径
        extract_to: 解压目标目录
        cancel_check: 取消检查回调
    """
    if cancel_check and cancel_check():
        raise InterruptedError("解压操作已被取消")

    ensure_dir(extract_to)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # 安全检查：防止 ZIP 炸弹（路径穿越攻击）
        for member in zf.namelist():
            member_path = extract_to / member
            # 确保解压路径在目标目录内
            abs_target = os.path.realpath(extract_to)
            abs_member = os.path.realpath(member_path)
            if not abs_member.startswith(abs_target + os.sep) and abs_member != abs_target:
                raise ValueError(f"ZIP 路径不安全: {member}")

        zf.extractall(extract_to)


def read_zip_entry(zip_path: Path, entry_name: str) -> Optional[str]:
    """
    读取 ZIP/JAR 文件中某个条目的文本内容。

    参数：
        zip_path: ZIP 文件路径
        entry_name: 内部条目路径（如 'META-INF/mods.toml'）

    返回：
        条目文本内容，找不到时返回 None
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if entry_name in zf.namelist():
                return zf.read(entry_name).decode("utf-8", errors="replace")
            # Forge 新版可能使用小写或大小写混合
            for name in zf.namelist():
                if name.lower() == entry_name.lower():
                    return zf.read(name).decode("utf-8", errors="replace")
            return None
    except (zipfile.BadZipFile, IOError):
        return None


def list_zip_entries(zip_path: Path) -> List[str]:
    """
    列出 ZIP/JAR 文件中的所有条目名称。

    参数：
        zip_path: ZIP 文件路径

    返回：
        条目名列表，损坏的 ZIP 返回空列表
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return zf.namelist()
    except (zipfile.BadZipFile, IOError):
        return []


def atomic_write(path: Path, content: str, encoding: str = "utf-8"):
    """
    原子写入文件（先写临时文件，再重命名）。

    参数：
        path: 目标文件路径
        content: 要写入的文本内容
    """
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding=encoding) as f:
        f.write(content)
    if path.exists():
        path.unlink()
    tmp_path.rename(path)


def get_size_mb(path: Path) -> float:
    """
    获取文件或目录的大小（MB）。

    参数：
        path: 文件或目录路径

    返回：
        大小（兆字节，保留两位小数）
    """
    if path.is_file():
        return round(path.stat().st_size / (1024 * 1024), 2)
    elif path.is_dir():
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
    return 0.0


class InterruptedError(Exception):
    """操作被用户主动取消的内部异常"""
    pass