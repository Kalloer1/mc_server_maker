# generator.py —— 服务端生成模块
# 职责：
#   1. 创建服务端输出目录
#   2. 复制用户选择的模组和配置文件夹
#   3. 下载/定位服务端安装器
#   4. 生成 eula.txt / user_jvm_args.txt / 启动脚本
#   5. 复制 server-icon.png（如果用户选择了）
#   6. 生成 server.properties（包含 MOTD）

import os
import shutil
import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, List

from utils.constants import (
    START_BAT_FORGE_TEMPLATE, START_BAT_NEOFORGE_TEMPLATE,
    START_BAT_FABRIC_TEMPLATE, START_BAT_VANILLA_TEMPLATE,
    START_SH_FORGE_TEMPLATE, START_SH_NEOFORGE_TEMPLATE,
    START_SH_FABRIC_TEMPLATE, START_SH_VANILLA_TEMPLATE,
    USER_JVM_ARGS_TEMPLATE, EULA_CONTENT,
    SERVER_ICON_SIZE, SERVER_ICON_FILENAME,
    PRESERVED_FOLDERS, CLIENT_ONLY_FOLDERS,
)
from utils.file_utils import (
    ensure_dir, copy_file, copy_directory, copy_selected_folders,
    atomic_write,
)
from core.server_provider import download_server_core, _get_core_filename, DownloadError
from utils.motd_colors import convert_motd_to_server_properties


def generate_server(
    config: dict,
    status_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, str]:
    """
    生成完整的 Minecraft 服务端。

    参数：
        config: 完整配置字典，包含以下字段：
            - game_dir: 游戏版本目录路径
            - pack_name: 整合包名称
            - mc_version: MC 版本号
            - loader_type: 加载器类型
            - loader_version: 加载器版本
            - mod_files: 用户选择的模组文件路径列表
            - memory: 内存分配（如 "4G"）
            - server_icon_pixmap: QPixmap 或 None
            - custom_sources: 自定义下载源列表
            - offline_core_path: 离线核心路径（可选）
            - selected_folders: 用户选择的配置文件夹列表
            - output_dir: 用户指定的输出目录（可选，为空则自动生成）

        status_callback: 状态回调 (str)
        progress_callback: 进度回调 (int: 0~100)
        cancel_check: 取消检查回调

    返回：
        {
            "output_dir": str,
            "core_jar": str,
        }
    """
    # ----- 解析配置 -----
    game_dir = Path(config["game_dir"])
    pack_name = config.get("pack_name", game_dir.name)
    mc_version = config["mc_version"]
    loader_type = config["loader_type"]
    loader_version = config["loader_version"]
    mod_files = config.get("mod_files", [])
    memory = config.get("memory", "4G")
    server_icon_pixmap = config.get("server_icon_pixmap", None)
    custom_sources = config.get("custom_sources", [])
    offline_core_path = config.get("offline_core_path", None)
    selected_folders = config.get("selected_folders", [])
    user_output_dir = config.get("output_dir", "")
    motd = config.get("motd", None)

    # ----- 确定输出目录 -----
    if user_output_dir and user_output_dir.strip():
        # 用户指定了自定义输出目录，自动在其中创建一个新文件夹
        version_slug = pack_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        output_dir = Path(user_output_dir.strip()) / f"server_{version_slug}"
    else:
        # 自动生成：在游戏目录同级创建 server_{pack_name}
        mc_root = game_dir.parent.parent  # versions/../ → .minecraft/
        version_slug = pack_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        output_dir = Path(mc_root) / f"server_{version_slug}"
    ensure_dir(output_dir)

    if status_callback:
        status_callback(f"输出目录: {output_dir}")

    # ================================================================
    # 阶段 1/4：复制模组 (0% → 25%)
    # ================================================================
    if progress_callback:
        progress_callback(5)
    if cancel_check and cancel_check():
        raise InterruptedError("生成已被取消")

    if status_callback:
        status_callback("阶段 1/4: 复制模组...")

    if mod_files:
        server_mods_dir = output_dir / "mods"
        ensure_dir(server_mods_dir)
        total_mods = len(mod_files)
        for i, mod_path in enumerate(mod_files):
            if cancel_check and cancel_check():
                raise InterruptedError("生成已被取消")
            src = Path(mod_path)
            dst = server_mods_dir / src.name
            shutil.copy2(src, dst)
            if progress_callback and total_mods > 0:
                progress_callback(5 + int((i + 1) / total_mods * 20))
            if status_callback:
                status_callback(f"复制模组 ({i + 1}/{total_mods}): {src.name}")
    else:
        if status_callback:
            status_callback("无模组文件，跳过模组复制步骤")
        if progress_callback:
            progress_callback(25)

    # ================================================================
    # 阶段 2/4：复制配置文件夹 (25% → 45%)
    # ================================================================
    if progress_callback:
        progress_callback(25)
    if cancel_check and cancel_check():
        raise InterruptedError("生成已被取消")

    if status_callback:
        status_callback("阶段 2/4: 复制配置文件夹...")

    # 当前目录下的文件夹使用 game_dir，而非 mc_root
    if selected_folders:
        copied = 0
        for folder_name in selected_folders:
            if cancel_check and cancel_check():
                raise InterruptedError("生成已被取消")
            src = game_dir / folder_name
            dst = output_dir / folder_name
            if src.exists() and src.is_dir() and not dst.exists():
                try:
                    shutil.copytree(src, dst, symlinks=False, ignore_dangling_symlinks=True)
                    copied += 1
                    if status_callback:
                        status_callback(f"已复制文件夹 ({copied}/{len(selected_folders)}): {folder_name}")
                except Exception as e:
                    if status_callback:
                        status_callback(f"复制文件夹失败 {folder_name}: {e}")
    else:
        if status_callback:
            status_callback("无配置文件夹，跳过复制步骤")

    if progress_callback:
        progress_callback(45)

    # ================================================================
    # 阶段 3/4：下载安装器 (45% → 70%)
    # ================================================================
    if progress_callback:
        progress_callback(45)
    if cancel_check and cancel_check():
        raise InterruptedError("生成已被取消")

    if status_callback:
        status_callback("阶段 3/4: 下载服务端安装器...")

    core_filename = _get_core_filename(loader_type, mc_version, loader_version)
    core_jar_name = core_filename
    download_failed = False
    download_info = None

    try:
        core_result = download_server_core(
            loader_type=loader_type,
            mc_version=mc_version,
            loader_version=loader_version,
            dest_dir=output_dir,
            offline_core_path=offline_core_path,
            custom_sources=custom_sources,
            progress_callback=lambda p: progress_callback(int(45 + p * 25)) if progress_callback else None,
            status_callback=status_callback,
            cancel_check=cancel_check,
        )
        core_jar_name = core_result["core_filename"]
        if status_callback:
            status_callback(f"安装器就绪: {core_jar_name}")
    except DownloadError as e:
        # 下载失败，不中断流程，记录失败信息供后续提示
        from core.server_provider import get_missing_core_info
        download_info = get_missing_core_info(
            loader_type=loader_type,
            mc_version=mc_version,
            loader_version=loader_version,
            dest_dir=output_dir,
        )
        download_info["message"] = (
            f"自动下载 {loader_type}/{mc_version} 服务端核心失败。\n\n"
            f"请手动下载以下文件：\n{download_info['filename']}\n\n"
            f"并放置到：\n{download_info['placement_dir']}"
        )
        download_failed = True
        if status_callback:
            status_callback(f"⚠ 服务端核心下载失败，请手动下载: {core_filename}")
            status_callback(f"[下载] 自动下载失败: {e}")
            status_callback(f"[下载] 请手动下载: {download_info['filename']}")
            for url in download_info.get("suggested_urls", [])[:3]:
                status_callback(f"[下载]   → {url}")

    if progress_callback:
        progress_callback(70)

    # ================================================================
    # 阶段 4/4：生成启动文件 (70% → 100%)
    # ================================================================
    if progress_callback:
        progress_callback(70)
    if cancel_check and cancel_check():
        raise InterruptedError("生成已被取消")

    if status_callback:
        status_callback("阶段 4/4: 生成启动文件...")

    # 4a. eula.txt
    _write_eula(output_dir)
    if progress_callback:
        progress_callback(75)

    # 4b. user_jvm_args.txt (Forge / NeoForge 需要)
    if loader_type in ("forge", "neoforge"):
        _write_jvm_args(output_dir, memory)
    if progress_callback:
        progress_callback(82)

    # 4c. 启动脚本
    _write_start_scripts(output_dir, loader_type, mc_version, loader_version, core_jar_name)
    if progress_callback:
        progress_callback(90)

    # 4d. 服务器图标
    if server_icon_pixmap:
        _write_server_icon(output_dir, server_icon_pixmap)
    if progress_callback:
        progress_callback(92)

    # 4e. server.properties（包含 MOTD）
    if motd:
        _write_server_properties(output_dir, motd)
    if progress_callback:
        progress_callback(95)

    # 确保 mods 文件夹存在
    ensure_dir(output_dir / "mods")

    if progress_callback:
        progress_callback(100)

    if status_callback:
        if download_failed:
            status_callback("⚠ 分离完成，但安装器下载失败，请手动下载")
        else:
            status_callback("✅ 服务端生成完毕！")

    return {
        "output_dir": str(output_dir),
        "core_jar": core_jar_name,
        "download_failed": download_failed,
        "download_info": download_info,
    }


# ================================================================
# 辅助函数：写入各类配置文件
# ================================================================


def _write_eula(output_dir: Path):
    """生成 eula.txt，已同意 EULA"""
    content = EULA_CONTENT
    # 更新日期戳
    content = content.replace(
        "# 2026年06月21日 星期日 20时41分18秒 CST",
        f"# {datetime.datetime.now().strftime('%Y年%m月%d日 %A %H时%M分%S秒 CST')}"
    )
    atomic_write(output_dir / "eula.txt", content)


def _write_jvm_args(output_dir: Path, memory: str):
    """
    生成 user_jvm_args.txt（Forge / NeoForge 启动脚本引用此文件）。
    """
    # 解析内存值
    mem_value = memory.upper().replace("G", "").replace("M", "").strip()
    try:
        mem_gb = int(mem_value)
        min_mem = f"{max(1, mem_gb // 2)}G"
        max_mem = f"{mem_gb}G"
    except ValueError:
        min_mem = "2G"
        max_mem = "4G"

    content = USER_JVM_ARGS_TEMPLATE.format(
        min_mem=min_mem,
        max_mem=max_mem,
    )
    atomic_write(output_dir / "user_jvm_args.txt", content)


def _write_start_scripts(
    output_dir: Path,
    loader_type: str,
    mc_version: str,
    loader_version: str,
    core_jar_name: str,
):
    """
    根据加载器类型生成 Windows 和 Linux 启动脚本。
    直接运行服务端核心文件（server.jar），无需安装器。
    """
    # 加载器显示名
    loader_name_map = {
        "forge": "Forge",
        "neoforge": "NeoForge",
        "fabric": "Fabric",
        "vanilla": "Vanilla",
    }
    loader_name = loader_name_map.get(loader_type, loader_type.title())

    # ---- Windows 脚本 ----
    # 所有加载器现在都使用统一的模板格式
    bat_content = START_BAT_FORGE_TEMPLATE.format(
        loader_name=loader_name,
        core_jar=core_jar_name,
    ) if loader_type == "forge" else (
        START_BAT_NEOFORGE_TEMPLATE.format(core_jar=core_jar_name) if loader_type == "neoforge" else
        START_BAT_FABRIC_TEMPLATE.format(core_jar=core_jar_name) if loader_type == "fabric" else
        START_BAT_VANILLA_TEMPLATE.format(core_jar=core_jar_name)
    )

    atomic_write(output_dir / "start.bat", bat_content)

    # ---- Linux/Mac 脚本 ----
    sh_content = START_SH_FORGE_TEMPLATE.format(
        core_jar=core_jar_name,
    ) if loader_type == "forge" else (
        START_SH_NEOFORGE_TEMPLATE.format(core_jar=core_jar_name) if loader_type == "neoforge" else
        START_SH_FABRIC_TEMPLATE.format(core_jar=core_jar_name) if loader_type == "fabric" else
        START_SH_VANILLA_TEMPLATE.format(core_jar=core_jar_name)
    )

    sh_path = output_dir / "start.sh"
    atomic_write(sh_path, sh_content)

    # 确保 Linux 脚本有执行权限（仅 POSIX 系统有效）
    try:
        os.chmod(sh_path, 0o755)
    except (OSError, PermissionError):
        pass  # Windows 上忽略


def _write_server_icon(output_dir: Path, pixmap):
    """
    将用户选择的服务器图标保存为 server-icon.png。
    传入的 pixmap 已经是 64x64。
    """
    icon_path = output_dir / SERVER_ICON_FILENAME
    try:
        pixmap.save(str(icon_path), "PNG")
    except Exception as e:
        # 图标写入失败不是致命错误
        pass


def _write_server_properties(output_dir: Path, motd: str):
    """
    生成或更新 server.properties 文件，设置 MOTD。
    如果文件已存在，只更新 motd 字段；否则创建基础配置。
    """
    props_path = output_dir / "server.properties"
    
    # 将用户输入的 MOTD 转换为 server.properties 格式
    converted_motd = convert_motd_to_server_properties(motd)
    
    if props_path.exists():
        # 读取现有配置并更新 motd
        with open(props_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("motd="):
                new_lines.append(f"motd={converted_motd}\n")
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            # 如果没有 motd 行，添加到末尾
            new_lines.append(f"motd={converted_motd}\n")
        
        with open(props_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    else:
        # 创建基础 server.properties
        base_props = f"""#Minecraft server properties
#Generated by MC Server Maker
#{datetime.datetime.now().strftime('%a %b %d %H:%M:%S %Z %Y')}
enable-jmx-monitoring=false
rcon.port=25575
level-seed=
gamemode=survival
enable-command-block=false
enable-query=false
generator-settings={{""}}
enforce-secure-profile=true
level-name=world
motd={converted_motd}
query.port=25565
pvp=true
generate-structures=true
max-churn-rate=8
difficulty=easy
network-compression-threshold=256
max-tick-time=60000
require-resource-pack=false
use-native-transport=true
max-players=100
online-mode=true
enable-status=true
allow-flight=false
initial-disabled-packs=
broadcast-rcon-to-ops=true
view-distance=10
server-ip=
resource-pack-prompt=
allow-nether=true
server-port=25565
enable-rcon=false
sync-chunk-writes=true
op-permission-level=4
prevent-proxy-connections=false
hide-online-players=false
resource-pack=
entity-broadcast-range-percentage=100
rcon.password=
player-idle-timeout=0
force-gamemode=false
rate-limit=0
hardcore=false
white-list=false
broadcast-console-to-ops=true
pause-when-empty-seconds=0
spawn-npcs=true
spawn-animals=true
log-ips=true
function-permission-level=2
initial-enabled-packs=vanilla
level-type=minecraft\\:normal
text-filtering-config=
spawn-monsters=true
enforce-whitelist=false
spawn-protection=16
max-world-size=29999984
"""
        atomic_write(props_path, base_props)


class InterruptedError(Exception):
    """生成过程被用户主动取消的内部异常"""
    pass


class ManualDownloadNeeded(Exception):
    """所有下载源均失败，需要用户手动下载核心文件"""
    def __init__(self, info: dict):
        super().__init__(info.get("message", "需要手动下载核心文件"))
        self.info = info