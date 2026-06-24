# server_provider.py —— 服务端核心下载模块
# 职责：
#   1. 根据加载器类型和版本构造官方下载 URL + 备用镜像 URL
#   2. 多源故障转移下载（按用户设置的优先级顺序）
#   3. 支持离线模式（指定本地核心文件，跳过下载）
#   4. 对于原版服务端，自动从 Mojang API 获取正确的文件哈希
#   5. 返回核心文件路径供 generator 使用

import json
import os
from pathlib import Path
from typing import Optional, Callable, List, Tuple, Dict

from utils.constants import (
    DOWNLOAD_SOURCES,
    VANILLA_MANIFEST_URL,
)
from utils.downloader import Downloader, DownloadError, DownloadCancelled


def download_server_core(
    loader_type: str,
    mc_version: str,
    loader_version: str,
    dest_dir: Path,
    offline_core_path: Optional[str] = None,
    custom_sources: Optional[List[dict]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, str]:
    """
    下载（或定位）服务端核心文件。

    参数：
        loader_type: "forge" / "fabric" / "neoforge" / "vanilla"
        mc_version: MC 版本号，如 "1.20.1"
        loader_version: 加载器版本，如 "47.2.0"
        dest_dir: 目标目录（核心文件将放置于此）
        offline_core_path: 离线模式指定的本地核心文件路径
        custom_sources: 用户自定义下载源列表
        progress_callback: 下载进度回调 (0.0 ~ 1.0)
        status_callback: 状态回调
        cancel_check: 取消检查回调

    返回：
        {
            "core_path": str,         # 核心文件完整路径
            "core_filename": str,     # 核心文件名
            "source_used": str,       # 使用的下载源名称（或 "离线模式"）
        }
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # --- 离线模式：直接使用用户指定的核心文件 ---
    if offline_core_path:
        offline_path = Path(offline_core_path)
        if not offline_path.exists():
            raise FileNotFoundError(f"指定的离线核心文件不存在: {offline_core_path}")
        if status_callback:
            status_callback(f"离线模式：使用 {offline_path.name}")
        return {
            "core_path": str(offline_path),
            "core_filename": offline_path.name,
            "source_used": "离线模式",
        }

    # --- 构建 URL 列表 ---
    url_list = _build_url_list(loader_type, mc_version, loader_version, custom_sources)

    if not url_list:
        raise DownloadError(
            f"无法为 {loader_type}/{mc_version} 构造下载地址。\n"
            f"请检查版本号是否正确，或使用离线模式手动提供核心文件。"
        )

    # --- 确定核心文件名 ---
    core_filename = _get_core_filename(loader_type, mc_version, loader_version)
    dest_path = dest_dir / core_filename

    # --- 下载 ---
    if status_callback:
        status_callback(f"准备下载 {core_filename}...")

    downloader = Downloader(
        progress_callback=progress_callback,
        status_callback=status_callback,
        cancel_check=cancel_check,
    )

    try:
        downloader.download(url_list, dest_path)
    except DownloadCancelled:
        raise
    except DownloadError:
        # 重新抛出，由主窗口显示手动下载提示
        raise

    return {
        "core_path": str(dest_path),
        "core_filename": core_filename,
        "source_used": "下载完成",
    }


def _build_url_list(
    loader_type: str,
    mc_version: str,
    loader_version: str,
    custom_sources: Optional[List[dict]] = None,
) -> List[Tuple[str, str]]:
    """
    根据加载器类型和版本构造下载 URL 列表。

    优先级：内置源（按 DOWNLOAD_SOURCES 定义顺序）→ 自定义源

    参数：
        loader_type: 加载器类型
        mc_version: MC 版本
        loader_version: 加载器版本
        custom_sources: 自定义下载源列表

    返回：
        [(源名称, 完整URL), ...]
    """
    url_list = []

    # 原版服务端需要先获取文件哈希
    vanilla_hash = ""
    if loader_type == "vanilla":
        vanilla_hash = _fetch_vanilla_server_hash(mc_version)

    # 收集内置源 URL 模板
    sources = DOWNLOAD_SOURCES.get(loader_type, [])

    for src in sources:
        raw_url = src["url"]
        url = _fill_url_template(
            raw_url, mc_version, loader_type, loader_version, vanilla_hash
        )
        if url:
            url_list.append((src["name"], url))

    # 追加自定义源
    if custom_sources:
        for cs in custom_sources:
            cs_loader = cs.get("loader", "全部")
            if cs_loader == "全部" or cs_loader == loader_type:
                url = _fill_url_template(
                    cs["url"], mc_version, loader_type, loader_version, vanilla_hash
                )
                if url:
                    url_list.append((cs["name"], url))

    return url_list


def _fill_url_template(
    url_template: str,
    mc_version: str,
    loader_type: str,
    loader_version: str,
    vanilla_hash: str = "",
) -> str:
    """
    将 URL 模板中的占位符替换为实际值。

    支持的占位符：
        {mc_version}   — MC 版本
        {loader}       — 加载器类型
        {loader_ver}   — 加载器版本
        {vanilla_hash} — 原版服务端 jar 哈希值
    """
    url = url_template.replace("{mc_version}", mc_version)
    url = url.replace("{loader}", loader_type)
    url = url.replace("{loader_ver}", loader_version)
    url = url.replace("{vanilla_hash}", vanilla_hash)
    return url


def _get_core_filename(
    loader_type: str,
    mc_version: str,
    loader_version: str,
) -> str:
    """
    根据加载器类型确定服务端核心文件的推荐名称。
    """
    if loader_type == "forge":
        return f"forge-{mc_version}-{loader_version}-installer.jar"
    elif loader_type == "neoforge":
        return f"neoforge-{loader_version}-installer.jar"
    elif loader_type == "fabric":
        return f"fabric-server-{mc_version}-{loader_version}.jar"
    else:  # vanilla
        return f"server-{mc_version}.jar"


def _fetch_vanilla_server_hash(mc_version: str) -> str:
    """
    从 Mojang 官方 version_manifest.json 获取指定 MC 版本的 server.jar 哈希值。

    返回：
        SHA1 哈希字符串，失败时返回空字符串
    """
    from utils.downloader import Downloader

    try:
        Downloader.get_json(VANILLA_MANIFEST_URL, timeout=15)
    except Exception:
        return ""

    try:
        data = Downloader.get_json(VANILLA_MANIFEST_URL, timeout=15)
        for version_entry in data.get("versions", []):
            if version_entry.get("id") == mc_version:
                version_url = version_entry.get("url", "")
                if version_url:
                    version_data = Downloader.get_json(version_url, timeout=15)
                    downloads = version_data.get("downloads", {})
                    server_info = downloads.get("server", {})
                    return server_info.get("sha1", "")
        return ""
    except Exception:
        return ""


def get_missing_core_info(
    loader_type: str,
    mc_version: str,
    loader_version: str,
    dest_dir: Path,
) -> Dict[str, str]:
    """
    当所有下载源均失败后，返回需要手动下载的核心文件信息，
    供 UI 提示用户手动下载。

    返回：
        {
            "filename": str,       # 需要下载的文件名
            "placement_dir": str,  # 文件应放置的目录
            "suggested_urls": [str, ...]  # 建议的下载地址
        }
    """
    core_filename = _get_core_filename(loader_type, mc_version, loader_version)

    # 收集所有可能的原始 URL（不含占位符替换的）
    raw_urls = []
    sources = DOWNLOAD_SOURCES.get(loader_type, [])
    vanilla_hash = ""
    if loader_type == "vanilla":
        vanilla_hash = _fetch_vanilla_server_hash(mc_version)

    for src in sources:
        url = _fill_url_template(src["url"], mc_version, loader_type, loader_version, vanilla_hash)
        if url:
            raw_urls.append(url)

    return {
        "filename": core_filename,
        "placement_dir": str(dest_dir),
        "suggested_urls": raw_urls,
    }