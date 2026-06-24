# worker.py —— 后台工作线程模块
# 所有耗时操作（下载、解压、文件遍历、子进程、数据库刷新）均在此运行
# Worker 继承 QThread，通过自定义 Signal 与主线程通信，保证 UI 不卡顿
# 支持安全中断：通过 _cancelled 标志位 + cancel_check 回调在各阶段检查

from PySide6.QtCore import QThread, Signal, QObject
from pathlib import Path
from typing import Optional, Callable


class WorkerSignals(QObject):
    """
    集中管理所有 Worker 可能发出的信号。

    信号说明：
        progress(int, str):   进度值(0-100) + 当前步骤描述
        status(str):          状态栏文字更新
        log(str):             日志行（含时间戳的完整信息）
        finished(dict):       任务完成，携带结果数据
        error(str):           任务出错，携带错误消息
        mod_progress(str):    模组分析进度（当前模组文件名）
        core_download_progress(int):  核心下载进度(0-100)

    注意：Signal 必须是 QObject 子类的类属性（class attribute），
    不能写在 __init__ 中，否则 PySide6 会报 AttributeError: connect。
    """

    progress = Signal(int, str)
    status = Signal(str)
    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)
    mod_progress = Signal(str)
    core_download_progress = Signal(int)
    manual_download_needed = Signal(object)  # 携带 ManualDownloadNeeded.info


class BaseWorker(QThread):
    """
    Worker 基类，封装取消逻辑和信号发射便捷方法。

    子类必须实现 run() 方法。
    在 run() 中应定期调用 self._check_cancelled() 检查是否需要中断。

    用法：
        worker = SomeWorker(...)
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        worker.start()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self):
        """请求取消当前任务（线程安全）"""
        self._cancelled = True

    def _check_cancelled(self):
        """如果取消标志被设置，抛出 InterruptedError"""
        if self._cancelled:
            raise InterruptedError("任务已被用户取消")

    def _emit_progress(self, value: int, desc: str = ""):
        """便捷方法：发射进度信号"""
        self.signals.progress.emit(value, desc)

    def _emit_status(self, message: str):
        """便捷方法：发射状态信号"""
        self.signals.status.emit(message)

    def _emit_log(self, message: str):
        """便捷方法：发射日志信号"""
        self.signals.log.emit(message)

    def _emit_error(self, message: str):
        """便捷方法：发射错误信号"""
        self.signals.error.emit(message)


class ScanWorker(BaseWorker):
    """
    扫描游戏目录的 Worker。

    输入：
        game_dir: str — 游戏版本目录路径（如 .minecraft/versions/1.20.1-forge-47.2.0）

    输出 (finished signal 携带 dict)：
        {
            "mc_version": str,
            "loader_type": "forge" | "fabric" | "neoforge" | "vanilla",
            "loader_version": str,
            "mod_count": int,
            "mod_files": [Path, ...],
            "config_folders": [str, ...],
            "all_folders": [str, ...],
        }
    """

    def __init__(self, game_dir: str, parent=None):
        super().__init__(parent)
        self._game_dir = Path(game_dir)

    def run(self):
        """在后台线程中执行扫描任务"""
        from core.scanner import scan_game_directory

        try:
            self._emit_status("正在扫描游戏目录...")
            self._emit_log(f"[扫描] 开始扫描: {self._game_dir}")
            self._emit_progress(10, "正在识别版本与加载器...")

            self._check_cancelled()

            result = scan_game_directory(self._game_dir)

            self._check_cancelled()

            self._emit_progress(100, "扫描完成")
            self._emit_status(
                f"扫描完成: MC {result['mc_version']}, "
                f"{result['loader_type']} {result['loader_version']}, "
                f"{result['mod_count']} 个模组"
            )
            self._emit_log(
                f"[扫描] 完成: 版本={result['mc_version']}, "
                f"加载器={result['loader_type']}/{result['loader_version']}, "
                f"模组={result['mod_count']}"
            )
            self.signals.finished.emit(result)

        except InterruptedError:
            self._emit_log("[扫描] 已被用户取消")
            self._emit_error("扫描已被取消")
        except Exception as e:
            self._emit_log(f"[扫描] 错误: {e}")
            self._emit_error(f"扫描失败: {e}")


class CoreDownloadWorker(BaseWorker):
    """
    下载服务端核心的 Worker。

    输入：
        loader_type: str — forge / fabric / neoforge / vanilla
        mc_version: str — 如 1.20.1
        loader_version: str — 如 47.2.0
        dest_dir: str — 目标目录
        offline_core_path: Optional[str] — 离线模式指定的核心文件路径
        custom_sources: Optional[list] — 自定义下载源（覆盖默认）

    输出 (finished signal 携带 dict)：
        {
            "core_path": str,        # 最终核心 jar 文件路径
            "core_filename": str,    # 核心文件名
            "source_used": str,      # 实际使用的下载源名称
        }
    """

    def __init__(
        self,
        loader_type: str,
        mc_version: str,
        loader_version: str,
        dest_dir: str,
        offline_core_path: Optional[str] = None,
        custom_sources: Optional[list] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._loader_type = loader_type
        self._mc_version = mc_version
        self._loader_version = loader_version
        self._dest_dir = Path(dest_dir)
        self._offline_core_path = offline_core_path
        self._custom_sources = custom_sources

    def run(self):
        """在后台线程中执行下载任务"""
        from core.server_provider import download_server_core

        try:
            self._emit_status("正在准备下载服务端核心...")
            self._emit_log(
                f"[核心下载] 加载器={self._loader_type}, "
                f"MC={self._mc_version}, 加载器版本={self._loader_version}"
            )

            # 进度回调
            def on_progress(percent: float):
                self.signals.core_download_progress.emit(int(percent * 100))
                self._emit_progress(int(percent * 100), "正在下载服务端核心...")

            # 状态回调
            def on_status(msg: str):
                self._emit_status(msg)
                self._emit_log(f"[核心下载] {msg}")

            # 取消检查回调
            def cancel_check() -> bool:
                return self._cancelled

            self._check_cancelled()

            result = download_server_core(
                loader_type=self._loader_type,
                mc_version=self._mc_version,
                loader_version=self._loader_version,
                dest_dir=self._dest_dir,
                offline_core_path=self._offline_core_path,
                custom_sources=self._custom_sources,
                progress_callback=on_progress,
                status_callback=on_status,
                cancel_check=cancel_check,
            )

            self._emit_progress(100, "核心下载完成")
            self._emit_status(f"核心就绪: {result['core_filename']}")
            self._emit_log(f"[核心下载] 完成: 文件={result['core_filename']}, 源={result['source_used']}")
            self.signals.finished.emit(result)

        except InterruptedError:
            self._emit_log("[核心下载] 已被用户取消")
            self._emit_error("下载已被取消")
        except Exception as e:
            self._emit_log(f"[核心下载] 错误: {e}")
            self._emit_error(f"下载服务端核心失败: {e}")


class ModFilterWorker(BaseWorker):
    """
    智能模组分离 Worker。

    输入：
        mod_files: [Path, ...] — 所有模组 jar 文件路径列表
        mod_db: ModDatabase — 已初始化的数据库实例

    输出 (finished signal 携带 dict)：
        {
            "server_mods": [Path, ...],   # 待复制到服务端的模组
            "client_mods": [Path, ...],   # 纯客户端模组（不复制）
            "unknown_mods": [Path, ...],  # 无法确定环境的模组
        }
    """

    def __init__(
        self,
        mod_files: list,
        mod_db,
        parent=None,
    ):
        super().__init__(parent)
        self._mod_files = mod_files
        self._mod_db = mod_db

    def run(self):
        """在后台线程中执行模组过滤任务"""
        from core.mod_filter import filter_mods

        try:
            self._emit_status("正在分析模组环境...")
            self._emit_log(f"[模组过滤] 开始分析 {len(self._mod_files)} 个模组")

            def on_mod_progress(mod_name: str):
                """每个模组分析完成时的回调"""
                self.signals.mod_progress.emit(mod_name)

            def cancel_check() -> bool:
                return self._cancelled

            self._check_cancelled()

            result = filter_mods(
                mod_files=self._mod_files,
                mod_db=self._mod_db,
                progress_callback=on_mod_progress,
                cancel_check=cancel_check,
            )

            self._emit_progress(100, "模组分析完成")
            self._emit_status(
                f"模组分析完成: {len(result['server_mods'])} 服务端 / "
                f"{len(result['client_mods'])} 客户端"
            )
            self._emit_log(
                f"[模组过滤] 完成: 服务端={len(result['server_mods'])}, "
                f"客户端={len(result['client_mods'])}, "
                f"未知={len(result['unknown_mods'])}"
            )
            self.signals.finished.emit(result)

        except InterruptedError:
            self._emit_log("[模组过滤] 已被用户取消")
            self._emit_error("模组分析已被取消")
        except Exception as e:
            self._emit_log(f"[模组过滤] 错误: {e}")
            self._emit_error(f"模组分析失败: {e}")


class GenerateWorker(BaseWorker):
    """
    生成服务端目录、配置文件、启动脚本的 Worker。

    输入：
        config: dict — 完整的生成配置字典（来自主窗口收集的所有设置）

    输出 (finished signal 携带 dict)：
        {
            "output_dir": str,    # 输出目录路径
            "core_jar": str,      # 核心 jar 文件名
        }
    """

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config

    def run(self):
        """在后台线程中生成服务端"""
        from core.generator import generate_server, ManualDownloadNeeded

        try:
            self._emit_status("正在生成服务端...")
            self._emit_log("[生成] 开始生成服务端文件...")

            def on_status(msg: str):
                self._emit_status(msg)
                self._emit_log(f"[生成] {msg}")

            def on_progress(value: int):
                self._emit_progress(value)

            def cancel_check() -> bool:
                return self._cancelled

            self._check_cancelled()

            result = generate_server(
                config=self._config,
                status_callback=on_status,
                progress_callback=on_progress,
                cancel_check=cancel_check,
            )

            self._emit_progress(100, "服务端生成完毕！")
            self._emit_status(f"✅ 服务端已生成: {result['output_dir']}")
            self._emit_log(f"[生成] 完成: 输出目录={result['output_dir']}")
            self.signals.finished.emit(result)

        except ManualDownloadNeeded as e:
            self._emit_log(f"[生成] 自动下载失败: {e}")
            self.signals.manual_download_needed.emit(e.info)
        except InterruptedError:
            self._emit_log("[生成] 已被用户取消")
            self._emit_error("生成已被取消")
        except Exception as e:
            self._emit_log(f"[生成] 错误: {e}")
            self._emit_error(f"生成服务端失败: {e}")


class DBRefreshWorker(BaseWorker):
    """
    在线数据库刷新 Worker。

    输入：
        mod_db: ModDatabase — 数据库实例
        url: str — 数据库 URL

    输出 (finished signal 携带 dict)：
        {
            "success": bool,
            "message": str,
        }
    """

    def __init__(self, mod_db, url: str, parent=None):
        super().__init__(parent)
        self._mod_db = mod_db
        self._url = url

    def run(self):
        """在后台线程中刷新数据库"""
        try:
            self._emit_status("正在刷新在线数据库...")
            self._emit_log(f"[数据库] 从 URL 刷新: {self._url}")

            def on_progress(val: float):
                self._emit_progress(int(val * 100), "正在下载数据库...")

            def on_status(msg: str):
                self._emit_log(f"[数据库] {msg}")

            self._check_cancelled()

            success, message = self._mod_db.refresh_from_url(
                url=self._url,
                progress_callback=on_progress,
                status_callback=on_status,
            )

            if success:
                self._emit_status(f"数据库刷新成功 ({self._mod_db.online_count} 条)")
            else:
                self._emit_status("数据库刷新失败")

            self._emit_log(f"[数据库] 结果: {message}")
            self.signals.finished.emit({
                "success": success,
                "message": message,
            })

        except InterruptedError:
            self._emit_log("[数据库] 已被用户取消")
            self._emit_error("刷新已被取消")
        except Exception as e:
            self._emit_log(f"[数据库] 错误: {e}")
            self._emit_error(f"数据库刷新出错: {e}")


class TestSourceWorker(BaseWorker):
    """
    下载源连接测试 Worker。

    输入：
        source_name: str — 源名称
        test_url: str — 测试连接用的小文件 URL

    输出 (finished signal 携带 dict)：
        {
            "success": bool,
            "source_name": str,
            "latency_ms": float,   # 延迟（毫秒）
            "status_code": int,    # HTTP 状态码
            "message": str,
        }
    """

    def __init__(self, source_name: str, test_url: str, parent=None):
        super().__init__(parent)
        self._source_name = source_name
        self._test_url = test_url

    def run(self):
        """在后台线程中测试连接"""
        from utils.downloader import Downloader

        try:
            self._emit_status(f"正在测试连接: {self._source_name}...")
            self._emit_log(f"[连接测试] 测试 {self._source_name}: {self._test_url}")

            status_code, latency_ms = Downloader.head_request(
                self._test_url, timeout=10
            )

            self._emit_log(
                f"[连接测试] {self._source_name}: "
                f"状态码={status_code}, 延迟={latency_ms:.0f}ms"
            )
            self._emit_status(
                f"✅ {self._source_name}: {latency_ms:.0f}ms"
            )
            self.signals.finished.emit({
                "success": True,
                "source_name": self._source_name,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "message": f"连接正常，延迟 {latency_ms:.0f}ms",
            })

        except InterruptedError:
            self._emit_error("测试已被取消")
        except Exception as e:
            self._emit_log(f"[连接测试] {self._source_name}: 失败 - {e}")
            self._emit_status(f"❌ {self._source_name}: 连接失败")
            self.signals.finished.emit({
                "success": False,
                "source_name": self._source_name,
                "latency_ms": 0,
                "status_code": 0,
                "message": f"连接失败: {e}",
            })


class InstallerWorker(BaseWorker):
    """
    运行 Forge/NeoForge 安装器的 Worker。

    输入：
        output_dir: str — 服务端输出目录（installer.jar 所在位置）
        loader_type: str — "forge" 或 "neoforge"
        mc_version: str — MC 版本号
        loader_version: str — 加载器版本号

    输出（finished signal 携带 dict）：
        {
            "success": bool,
            "message": str,
            "run_script": str | None,
            "libraries_dir": str | None,
        }
    """

    def __init__(
        self,
        output_dir: str,
        loader_type: str,
        mc_version: str,
        loader_version: str,
        java_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._output_dir = Path(output_dir)
        self._loader_type = loader_type
        self._mc_version = mc_version
        self._loader_version = loader_version
        self._java_path = java_path

    def run(self):
        from core.server_runner import run_installer

        try:
            self._emit_status("正在运行安装器...")
            self._emit_log(f"[安装器] 开始运行 {self._loader_type} installer")
            self._emit_progress(5, "启动中...")

            def on_log(msg: str):
                self._emit_log(msg)

            def cancel_check() -> bool:
                return self._cancelled

            result = run_installer(
                output_dir=self._output_dir,
                loader_type=self._loader_type,
                mc_version=self._mc_version,
                loader_version=self._loader_version,
                log_callback=on_log,
                cancel_check=cancel_check,
                java_path=self._java_path,
            )

            self._emit_progress(100, "安装器运行完成")
            if result.get("success"):
                self._emit_status("✅ 安装器运行成功")
            else:
                self._emit_status("❌ 安装器运行失败")

            self.signals.finished.emit(result)

        except InterruptedError:
            self._emit_log("[安装器] 已被用户取消")
            self.signals.error.emit("已取消")
        except Exception as e:
            self._emit_log(f"[安装器] 错误: {e}")
            self.signals.error.emit(f"运行安装器失败: {e}")


class ServerRunWorker(BaseWorker):
    """
    启动并运行 Minecraft 服务端的 Worker。

    输入：
        output_dir: str — 服务端输出目录
        loader_type: str — forge / neoforge / fabric / vanilla
        mc_version: str — MC 版本
        loader_version: str — 加载器版本

    输出（finished signal 携带 dict）：
        {
            "success": bool,
            "message": str,
            "output_count": int,
            "server_started": bool,
            "eula_prompted": bool,
            "properties_generated": bool,
        }
    """

    def __init__(
        self,
        output_dir: str,
        loader_type: str,
        mc_version: str,
        loader_version: str,
        java_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._output_dir = Path(output_dir)
        self._loader_type = loader_type
        self._mc_version = mc_version
        self._loader_version = loader_version
        self._java_path = java_path
        self._server_proc = None

    def run(self):
        from core.server_runner import ServerProcess

        try:
            self._emit_status("正在启动服务端...")
            self._emit_log(f"[启动] 启动 {self._loader_type} 服务端")
            self._emit_progress(10, "启动中...")

            server = ServerProcess(
                self._output_dir,
                self._loader_type,
                self._mc_version,
                self._loader_version,
                java_path=self._java_path,
            )
            self._server_proc = server

            def on_log(msg: str):
                self._emit_log(msg)

            def cancel_check() -> bool:
                return self._cancelled

            result = server.start(
                log_callback=on_log,
                cancel_check=cancel_check,
            )

            self._emit_progress(100, "服务端已停止")
            if result.get("success"):
                self._emit_status("✅ 服务端运行结束")
            else:
                self._emit_status("❌ 服务端运行异常")

            self.signals.finished.emit(result)

        except InterruptedError:
            self._emit_log("[启动] 已被用户取消")
            self.signals.error.emit("已取消")
        except Exception as e:
            self._emit_log(f"[启动] 错误: {e}")
            self.signals.error.emit(f"启动服务端失败: {e}")

    def stop_server(self):
        """外部调用：安全停止服务端"""
        if self._server_proc:
            self._emit_log("[停止] 请求停止服务端...")
            self._server_proc.stop(log_callback=lambda m: self._emit_log(m))


class InterruptedError(Exception):
    """任务被用户主动取消的内部异常"""
    pass