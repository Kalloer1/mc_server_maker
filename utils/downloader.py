# downloader.py —— 通用下载器模块
# 支持：多 URL 故障转移、进度回调、超时重试、连接测试、可中断取消
# 所有下载操作在调用方线程中同步运行（由 Worker QThread 调用）

import requests
import time
import os
from pathlib import Path
from typing import Callable, Optional, List, Tuple
from utils.constants import (
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_RETRIES,
    DOWNLOAD_CHUNK_SIZE,
)


class DownloadError(Exception):
    """当所有下载源均失败时抛出的自定义异常"""

    def __init__(self, message: str, failed_urls: List[str] = None):
        super().__init__(message)
        self.failed_urls = failed_urls or []


class DownloadCancelled(Exception):
    """下载被用户或 Worker 主动取消"""

    pass


class Downloader:
    """
    通用下载器类。

    核心特性：
    - 支持多 URL 列表：按顺序尝试，一个失败后自动切换下一个
    - 每个源支持额外重试次数
    - 实时进度回调：进度百分比（0.0 ~ 1.0）
    - 状态回调：当前使用的源名称
    - 支持外部取消标志（通过 `cancelled` 属性或传入的回调）
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[float], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        """
        初始化下载器。

        参数：
            progress_callback: 进度回调，接收 float（0.0 ~ 1.0）
            status_callback: 状态回调，接收 str，如 "正在使用: BMCLAPI"
            cancel_check: 取消检查回调，返回 True 表示应中断下载
        """
        self._progress_cb = progress_callback
        self._status_cb = status_callback
        self._cancel_checker = cancel_check
        self._cancelled = False

    def cancel(self):
        """设置取消标志，使当前下载任务尽快停止"""
        self._cancelled = True

    def _check_cancelled(self):
        """检查是否应该取消，如果是则抛出 DownloadCancelled"""
        if self._cancelled:
            raise DownloadCancelled("下载已被用户取消")
        if self._cancel_checker and self._cancel_checker():
            raise DownloadCancelled("下载已被 Worker 中断")

    def _emit_progress(self, value: float):
        """安全地发送进度回调"""
        if self._progress_cb:
            self._progress_cb(value)

    def _emit_status(self, message: str):
        """安全地发送状态回调"""
        if self._status_cb:
            self._status_cb(message)

    def download(
        self,
        url_list: List[Tuple[str, str]],
        dest_path: Path,
        timeout: int = DOWNLOAD_TIMEOUT,
        retries: int = DOWNLOAD_RETRIES,
    ) -> Path:
        """
        从多个 URL 源中尝试下载文件，保存到 dest_path。

        参数：
            url_list: [(name, url), ...] 列表，name 为源名称，url 为下载地址
            dest_path: 目标文件路径（Path 对象）
            timeout: 单个请求超时时间（秒）
            retries: 每个源失败后额外重试次数

        返回：
            成功下载后的目标 Path

        抛出：
            DownloadCancelled: 用户或 Worker 取消
            DownloadError: 所有源均失败
        """
        # 确保目标目录存在
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        last_error = None
        failed_details = []  # 记录每个失败的源及原因

        for idx, (source_name, url) in enumerate(url_list):
            self._check_cancelled()

            # 对当前源进行多次尝试（包括首次 + retries 次重试）
            for attempt in range(1 + retries):
                self._check_cancelled()

                if attempt == 0:
                    self._emit_status(f"正在使用源: {source_name}")
                else:
                    self._emit_status(
                        f"源 {source_name} 第 {attempt}/{retries} 次重试..."
                    )

                try:
                    self._emit_progress(0.0)
                    self._download_single(url, dest_path, timeout)
                    # 下载成功
                    self._emit_progress(1.0)
                    self._emit_status(f"下载完成！源: {source_name}")
                    return dest_path
                except DownloadCancelled:
                    raise  # 直接向上抛出取消异常
                except Exception as e:
                    last_error = e
                    self._emit_status(
                        f"源 {source_name} 失败: {str(e)[:100]}"
                    )
                    # 非本次尝试的最后一次重试时，等待短暂时间再重试
                    if attempt < retries:
                        time.sleep(1)

            # 当前源所有尝试均失败，记录并继续下一个源
            failed_details.append(f"{source_name}: {str(last_error)[:100]}")

        # 所有源均失败
        error_msg = (
            f"所有下载源均失败（共 {len(url_list)} 个源）。\n"
            + "\n".join(f"  - {d}" for d in failed_details)
        )
        raise DownloadError(error_msg, failed_urls=[url for _, url in url_list])

    def _download_single(self, url: str, dest_path: Path, timeout: int):
        """
        从单个 URL 流式下载文件。

        参数：
            url: 下载 URL
            dest_path: 目标文件路径
            timeout: 超时时间（秒）
        """
        self._check_cancelled()

        with requests.get(
            url,
            stream=True,
            timeout=(timeout, timeout),
            allow_redirects=True,
            headers={
                "User-Agent": "MCServerMaker/2.0",
            },
        ) as response:
            response.raise_for_status()

            # 获取文件总大小（如果服务器提供 Content-Length）
            total_size = response.headers.get("content-length")
            if total_size is not None:
                total_size = int(total_size)
            else:
                total_size = 0

            downloaded = 0

            # 写入临时文件，完成后重命名（原子性操作）
            tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    self._check_cancelled()
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self._emit_progress(downloaded / total_size)
                        else:
                            # 无法获取总大小时，发送基于已下载的大致进度
                            self._emit_progress(min(downloaded / (10 * 1024 * 1024), 0.99))

            # 下载完成，原子性改名
            if tmp_path.exists():
                # Windows 下需要先删除已存在的目标文件
                if dest_path.exists():
                    dest_path.unlink()
                tmp_path.rename(dest_path)

    def download_small(
        self,
        url_list: List[Tuple[str, str]],
        timeout: int = 10,
    ) -> Tuple[str, bytes]:
        """
        从多个 URL 中尝试下载小文件（用于连接测试、JSON 数据库等）。
        返回完整的二进制内容，不写入磁盘。

        参数：
            url_list: [(name, url), ...]
            timeout: 请求超时时间（秒）

        返回：
            (source_name, content_bytes)

        抛出：
            DownloadError: 所有源均失败
        """
        last_error = None

        for source_name, url in url_list:
            self._check_cancelled()

            self._emit_status(f"正在尝试: {source_name}")
            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers={
                        "User-Agent": "MCServerMaker/2.0",
                    },
                )
                response.raise_for_status()
                self._emit_status(f"下载成功！源: {source_name}")
                return source_name, response.content
            except DownloadCancelled:
                raise
            except Exception as e:
                last_error = e
                self._emit_status(f"源 {source_name} 失败: {str(e)[:80]}")

        raise DownloadError(
            f"无法从任何源下载小文件。最后错误: {last_error}",
            failed_urls=[url for _, url in url_list],
        )

    @staticmethod
    def head_request(
        url: str,
        timeout: int = 10,
    ) -> Tuple[int, float]:
        """
        发送 HEAD 请求测试连接延迟和可用性。

        参数：
            url: 目标 URL
            timeout: 超时时间（秒）

        返回：
            (HTTP状态码, 响应延迟毫秒)

        抛出：
            requests.RequestException: 连接失败
        """
        start = time.perf_counter()
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "MCServerMaker/2.0",
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        return response.status_code, elapsed_ms

    @staticmethod
    def get_json(
        url: str,
        timeout: int = 15,
    ) -> dict:
        """
        同步获取并解析 JSON。

        参数：
            url: 目标 URL
            timeout: 超时时间（秒）

        返回：
            JSON 反序列化后的 dict

        抛出：
            requests.RequestException: 网络错误
            ValueError: JSON 解析错误
        """
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "MCServerMaker/2.0",
            },
        )
        response.raise_for_status()
        return response.json()