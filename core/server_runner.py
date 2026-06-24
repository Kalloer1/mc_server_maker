# server_runner.py —— 服务端运行模块
# 职责：
#   1. 运行 Forge / NeoForge 安装器（java -jar installer.jar --installServer）
#   2. 运行服务端启动脚本（start.bat / run.bat / fabric server jar）
#   3. 实时捕获子进程 stdout/stderr 输出
#   4. 安全停止服务端（发送 stop 命令或终止进程）
#   5. 验证安装器产物（libraries/ 目录、run.bat 等）
#
# 设计要点：
#   - 所有子进程操作都在独立线程中运行（调用方应为 QThread 子类）
#   - 通过 yield / generator 方式逐行回传日志，便于 UI 显示
#   - cancel_flag 通过回调函数传入，定期检查是否需要中断
#   - Forge/NeoForge 安装器需要 java 在 PATH 中

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple


# ------------------------------------------------------------------
# 辅助：检查 Java 是否可用
# ------------------------------------------------------------------

def check_java_available() -> Tuple[bool, str]:
    """
    检查系统中是否有可用的 Java 运行环境。

    返回：
        (是否可用, 版本信息或错误信息)
    """
    java_path = shutil.which("java")
    if not java_path:
        return False, "未找到 Java，请先安装 JDK/JRE 并配置环境变量 PATH。"

    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True, timeout=10
        )
        version_info = result.stderr.strip() or result.stdout.strip() or "(未知版本)"
        return True, version_info
    except Exception as e:
        return False, f"Java 检测失败: {e}"


# ------------------------------------------------------------------
# 安装器运行（仅 Forge / NeoForge）
# ------------------------------------------------------------------

def run_installer(
    output_dir: Path,
    loader_type: str,
    mc_version: str,
    loader_version: str,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    java_path: Optional[str] = None,
) -> Dict[str, object]:
    """
    运行 Forge / NeoForge 安装器，解压出 libraries/ 和 run.bat。

    参数：
        output_dir: 服务端输出目录（installer.jar 所在目录）
        loader_type: "forge" 或 "neoforge"
        mc_version: MC 版本号（如 "1.20.1"）
        loader_version: 加载器版本号（如 "47.2.0"）
        log_callback: 每行日志回调，参数为日志字符串
        cancel_check: 取消检查回调，返回 True 表示应中断
        java_path: 自定义 java 可执行文件路径，None 则使用 PATH 中的 java

    返回：
        {
            "success": bool,
            "message": str,
            "run_script": str | None,      # 生成的启动脚本路径
            "libraries_dir": str | None,   # libraries/ 目录路径
        }
    """
    output_dir = Path(output_dir)

    if loader_type not in ("forge", "neoforge"):
        msg = f"{loader_type} 无需安装器，可直接启动服务端。"
        if log_callback:
            log_callback(msg)
        return {
            "success": True,
            "message": msg,
            "run_script": None,
            "libraries_dir": None,
        }

    # 查找 installer.jar
    installer_jar = _find_installer_jar(output_dir, loader_type, mc_version, loader_version)
    if not installer_jar:
        msg = (f"未在 {output_dir} 中找到 {loader_type} 安装器 jar 文件。\n"
               f"请先完成「分离服务器基础文件」步骤下载安装器。")
        if log_callback:
            log_callback(msg)
        return {"success": False, "message": msg, "run_script": None, "libraries_dir": None}

    # 检查 Java
    java_exe = java_path if java_path else "java"
    java_ok, java_msg = check_java_available()
    if not java_ok:
        if log_callback:
            log_callback(f"[Java] {java_msg}")
        return {"success": False, "message": java_msg, "run_script": None, "libraries_dir": None}

    if log_callback:
        log_callback(f"[Java] 使用 Java: {java_exe}")
        log_callback(f"[Java] 检测到 Java: {java_msg}")
        log_callback(f"[安装器] 开始运行: {installer_jar.name}")
        log_callback(f"[安装器] 工作目录: {output_dir}")
        log_callback(f"[安装器] 执行: {java_exe} -jar {installer_jar.name} --installServer")
        log_callback("-" * 60)

    # 运行安装器
    cmd = [java_exe, "-jar", str(installer_jar), "--installServer"]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(output_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        msg = f"启动安装器失败: {e}"
        if log_callback:
            log_callback(f"[错误] {msg}")
        return {"success": False, "message": msg, "run_script": None, "libraries_dir": None}

    # 实时读取输出
    output_lines: List[str] = []
    try:
        for line in process.stdout:
            if cancel_check and cancel_check():
                process.terminate()
                if log_callback:
                    log_callback("[操作] 安装器已被用户取消")
                return {"success": False, "message": "已取消", "run_script": None, "libraries_dir": None}

            line = line.strip()
            if line:
                output_lines.append(line)
                if log_callback:
                    log_callback(line)

        return_code = process.wait(timeout=10)
    except Exception as e:
        process.kill()
        msg = f"运行安装器时出错: {e}"
        if log_callback:
            log_callback(f"[错误] {msg}")
        return {"success": False, "message": msg, "run_script": None, "libraries_dir": None}

    if log_callback:
        log_callback("-" * 60)
        log_callback(f"[安装器] 进程退出码: {return_code}")

    # 验证产物
    libraries_dir = output_dir / "libraries"
    has_libraries = libraries_dir.exists() and libraries_dir.is_dir()

    run_script = _find_run_script(output_dir, loader_type)

    if return_code != 0:
        msg = f"安装器运行失败（退出码 {return_code}），请检查上面的日志。"
        if log_callback:
            log_callback(f"[失败] {msg}")
        return {"success": False, "message": msg, "run_script": str(run_script) if run_script else None,
                "libraries_dir": str(libraries_dir) if has_libraries else None}

    if not has_libraries:
        msg = "安装器未生成 libraries/ 目录，可能安装不完整。"
        if log_callback:
            log_callback(f"[警告] {msg}")
        return {"success": False, "message": msg, "run_script": str(run_script) if run_script else None,
                "libraries_dir": None}

    if not run_script:
        msg = "未找到启动脚本（run.bat/start.bat），请手动检查目录内容。"
        if log_callback:
            log_callback(f"[警告] {msg}")
        return {"success": False, "message": msg, "run_script": None,
                "libraries_dir": str(libraries_dir)}

    if log_callback:
        log_callback(f"[成功] libraries/ 目录: {libraries_dir}")
        log_callback(f"[成功] 启动脚本: {run_script}")
        log_callback("[成功] ✅ 安装器运行完成！")

    return {
        "success": True,
        "message": "安装器运行成功",
        "run_script": str(run_script),
        "libraries_dir": str(libraries_dir),
    }


def _find_installer_jar(output_dir: Path, loader_type: str, mc_version: str, loader_version: str) -> Optional[Path]:
    """
    在输出目录中查找安装器 jar 文件。
    优先匹配精确文件名，找不到时尝试模糊匹配。
    """
    # 精确匹配
    expected_name = f"{loader_type}-{mc_version}-{loader_version}-installer.jar"
    exact_path = output_dir / expected_name
    if exact_path.exists():
        return exact_path

    # 模糊匹配：*installer*.jar
    for jar_file in output_dir.glob("*.jar"):
        name = jar_file.name.lower()
        if "installer" in name and loader_type in name:
            return jar_file

    return None


def _find_run_script(output_dir: Path, loader_type: str) -> Optional[Path]:
    """
    查找启动脚本（run.bat 或 start.bat）。
    优先顺序：run.bat（官方）> start.bat（我们生成的）> run.sh
    """
    candidates = ["run.bat", "start.bat", "run.sh"]
    for name in candidates:
        path = output_dir / name
        if path.exists():
            return path
    return None


# ------------------------------------------------------------------
# 服务端启动/停止
# ------------------------------------------------------------------

class ServerProcess:
    """
    服务端进程管理器。
    负责启动、输出监听、安全停止服务端。

    用法：
        server = ServerProcess(output_dir, loader_type, mc_version, loader_version)
        server.start(log_callback=lambda line: print(line))
        ...
        server.stop()
    """

    def __init__(
        self,
        output_dir: Path,
        loader_type: str,
        mc_version: str,
        loader_version: str,
        java_path: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.loader_type = loader_type
        self.mc_version = mc_version
        self.loader_version = loader_version
        self._java_path = java_path
        self._process: Optional[subprocess.Popen] = None
        self._running = False

    def is_running(self) -> bool:
        return self._running and self._process and self._process.poll() is None

    def start(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, object]:
        """
        启动服务端，实时回传日志。阻塞直到服务端停止。

        启动策略：
          - forge/neoforge: 优先运行 run.bat（官方），找不到则用 start.bat
          - fabric: 运行 start.bat（java -jar fabric-server-*.jar nogui）
          - vanilla: 运行 start.bat（java -jar server-*.jar nogui）
        """
        if self.is_running():
            return {"success": False, "message": "服务端已在运行"}

        # 检查 Java
        java_exe = self._java_path if self._java_path else "java"
        java_ok, java_msg = check_java_available()
        if not java_ok:
            if log_callback:
                log_callback(f"[Java] {java_msg}")
            return {"success": False, "message": java_msg}

        # 构建启动命令
        cmd, work_dir = self._build_start_command(java_exe)
        if not cmd:
            msg = f"未找到启动脚本或核心 jar 文件。请先完成「分离服务器基础文件」和「运行安装器」。"
            if log_callback:
                log_callback(f"[错误] {msg}")
            return {"success": False, "message": msg}

        if log_callback:
            log_callback(f"[启动] 工作目录: {work_dir}")
            log_callback(f"[启动] 命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
            log_callback("-" * 60)

        # 启动进程
        try:
            if isinstance(cmd, list):
                # java -jar ... nogui
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                # .bat / .sh 脚本
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=isinstance(cmd, str) and cmd.endswith(".sh"),
                )
        except Exception as e:
            msg = f"启动服务端失败: {e}"
            if log_callback:
                log_callback(f"[错误] {msg}")
            return {"success": False, "message": msg}

        self._running = True

        # 读取输出
        all_output: List[str] = []
        seen_eula_prompt = False
        server_started = False

        try:
            for line in self._process.stdout:
                if cancel_check and cancel_check():
                    self.stop(log_callback)
                    return {"success": False, "message": "已取消", "output_count": len(all_output)}

                line = line.strip()
                if line:
                    all_output.append(line)
                    if log_callback:
                        log_callback(line)

                    # 检测 EULA 提示
                    if "eula.txt" in line.lower() or "eula" in line.lower():
                        if not seen_eula_prompt and "false" in line.lower():
                            seen_eula_prompt = True
                            if log_callback:
                                log_callback("[提示] 检测到 EULA 未同意，服务端将自动停止。"
                                             "请编辑 eula.txt 将 eula=false 改为 eula=true")

                    # 检测服务端启动成功（关键日志）
                    if ("Done!" in line and "For help" in line) or \
                       ("Timing Reset" in line and "initialized" in line.lower()) or \
                       ("Starting minecraft server version" in line) or \
                       ("Preparing level" in line):
                        server_started = True

            return_code = self._process.wait(timeout=5)
        except Exception as e:
            return_code = -1
            if log_callback:
                log_callback(f"[错误] 读取输出出错: {e}")

        self._running = False

        if log_callback:
            log_callback("-" * 60)
            log_callback(f"[停止] 服务端进程退出码: {return_code}")

        # 自动生成 server.properties 的检测
        prop_path = self.output_dir / "server.properties"
        props_generated = prop_path.exists()

        if props_generated and log_callback:
            log_callback(f"[成功] 已生成 server.properties: {prop_path}")

        return {
            "success": return_code == 0 or server_started,
            "message": "服务端运行结束" if return_code == 0 else f"退出码 {return_code}",
            "output_count": len(all_output),
            "server_started": server_started,
            "eula_prompted": seen_eula_prompt,
            "properties_generated": props_generated,
        }

    def stop(self, log_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        安全停止服务端。
        优先通过 stdin 发送 "stop" 命令；失败则终止进程。
        """
        if not self._process or self._process.poll() is not None:
            self._running = False
            return

        if log_callback:
            log_callback("[停止] 正在发送 stop 命令...")

        # 尝试发送 stop 命令（优雅停止）
        try:
            if self._process.stdin:
                self._process.stdin.write("stop\n")
                self._process.stdin.flush()
                # 等待最多 15 秒让服务端优雅停止
                try:
                    self._process.wait(timeout=15)
                    if log_callback:
                        log_callback("[停止] 服务端已优雅停止")
                    self._running = False
                    return
                except subprocess.TimeoutExpired:
                    if log_callback:
                        log_callback("[停止] 优雅停止超时，强制终止...")
        except Exception as e:
            if log_callback:
                log_callback(f"[停止] 发送 stop 命令失败: {e}")

        # 强制终止
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            if log_callback:
                log_callback("[停止] 服务端进程已终止")
        except Exception as e:
            if log_callback:
                log_callback(f"[停止] 终止进程失败: {e}")

        self._running = False

    def _build_start_command(self, java_exe: str = "java") -> Tuple[Optional[object], Path]:
        """
        根据加载器类型构建启动命令。
        返回 (命令, 工作目录)。命令可能是 list（java -jar ...）或字符串（脚本路径）。
        """
        work_dir = self.output_dir

        if self.loader_type in ("forge", "neoforge"):
            # 优先官方 run.bat，其次 start.bat
            for script_name in ("run.bat", "start.bat"):
                script = work_dir / script_name
                if script.exists():
                    return str(script), work_dir
            # 退而求其次：直接用 java 调用（极个别情况下）
            user_jvm = work_dir / "user_jvm_args.txt"
            if user_jvm.exists():
                cmd = [java_exe, f"@{user_jvm}",
                       f"@libraries/net/{self.loader_type}/{self.loader_type}/"
                       f"{self.mc_version}-{self.loader_version}/win_args.txt",
                       "nogui"]
                return cmd, work_dir
            return None, work_dir

        elif self.loader_type == "fabric":
            # Fabric: start.bat 或直接 java -jar fabric-server-*.jar nogui
            for script_name in ("start.bat", "run.bat"):
                script = work_dir / script_name
                if script.exists():
                    return str(script), work_dir
            # 回退：查找 fabric-server-*.jar
            for jar in work_dir.glob("fabric-server-*.jar"):
                return [java_exe, "-jar", str(jar), "nogui"], work_dir
            return None, work_dir

        else:  # vanilla
            for script_name in ("start.bat", "run.bat"):
                script = work_dir / script_name
                if script.exists():
                    return str(script), work_dir
            for jar in work_dir.glob("server-*.jar"):
                return [java_exe, "-Xmx4G", "-Xms1G", "-jar", str(jar), "nogui"], work_dir
            return None, work_dir


# ------------------------------------------------------------------
# 便捷函数：一次性启动服务端
# ------------------------------------------------------------------

def run_server_once(
    output_dir: Path,
    loader_type: str,
    mc_version: str,
    loader_version: str,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, object]:
    """
    启动一次服务端（用于首次生成配置文件）。
    实际上是对 ServerProcess 的封装：启动后检测到 server.properties 生成即返回，
    或等待用户通过 cancel_check 请求停止。
    """
    server = ServerProcess(output_dir, loader_type, mc_version, loader_version)
    return server.start(log_callback=log_callback, cancel_check=cancel_check)


# ------------------------------------------------------------------
# 便捷函数：检查目录内容
# ------------------------------------------------------------------

def get_server_status(output_dir: Path) -> Dict[str, object]:
    """
    检查输出目录中服务端文件的完整程度。
    返回每个关键文件/目录的存在状态。
    """
    output_dir = Path(output_dir)
    return {
        "output_dir_exists": output_dir.exists(),
        "eula_txt": (output_dir / "eula.txt").exists(),
        "server_properties": (output_dir / "server.properties").exists(),
        "libraries_dir": (output_dir / "libraries").exists(),
        "mods_dir": (output_dir / "mods").exists(),
        "config_dir": (output_dir / "config").exists(),
        "run_bat": (output_dir / "run.bat").exists(),
        "start_bat": (output_dir / "start.bat").exists(),
        "user_jvm_args": (output_dir / "user_jvm_args.txt").exists(),
    }
