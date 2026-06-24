# launch_args.py —— 启动参数管理模块
# 职责：
#   1. 管理 JVM 堆内存设置（-Xmx / -Xms）
#   2. 管理额外 JVM 参数（-XX:+UseG1GC 等）
#   3. 管理服务端额外启动参数（nogui / --port 等）
#   4. 读写 user_jvm_args.txt
#   5. 提供常用参数模板供用户一键应用
#
# Forge/NeoForge 启动流程：
#   java @user_jvm_args.txt @libraries/net/neoforge/neoforge/.../win_args.txt nogui
#   - 其中 user_jvm_args.txt 由我们管理
#
# Fabric/Vanilla 启动流程：
#   java -Xmx4G -Xms1G -jar fabric-server-xxx.jar nogui
#   - JVM 参数直接写入 start.bat

from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# 常用 JVM 参数模板（预设方案，一键应用）
# ------------------------------------------------------------------

JVM_PRESETS: Dict[str, Dict[str, object]] = {
    "default": {
        "name": "默认（推荐）",
        "description": "平衡性能与稳定性，适合大多数服务器",
        "xmx": "4G",
        "xms": "1G",
        "extra_args": [
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
        ],
    },
    "performance": {
        "name": "性能优化（大服）",
        "description": "针对大服务器的激进优化参数，需要更多内存",
        "xmx": "8G",
        "xms": "4G",
        "extra_args": [
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=8M",
            "-XX:G1ReservePercent=20",
            "-XX:+UseLargePagesInMetaspace",
            "-XX:InitiatingHeapOccupancyPercent=50",
            "-XX:G1MixedGCLiveThresholdPercent=90",
            "-XX:G1RSetUpdatingPauseTimePercent=5",
            "-XX:SurvivorRatio=32",
            "-XX:+PerfDisableSharedMem",
            "-XX:MaxTenuringThreshold=1",
            "-Dusing.aikars.flags=https://mcflags.emc.gs",
            "-Daikars.new.flags=true",
        ],
    },
    "compact": {
        "name": "紧凑（小服/测试）",
        "description": "低内存占用，适合测试服或小服务器",
        "xmx": "2G",
        "xms": "1G",
        "extra_args": [
            "-XX:+UseG1GC",
            "-XX:MaxGCPauseMillis=200",
        ],
    },
    "minimal": {
        "name": "最小化（原始）",
        "description": "仅设置内存，无额外优化参数",
        "xmx": "4G",
        "xms": "2G",
        "extra_args": [],
    },
}


# ------------------------------------------------------------------
# JVM 参数读写
# ------------------------------------------------------------------

def parse_user_jvm_args(file_path: Path) -> Dict[str, object]:
    """
    解析 user_jvm_args.txt。

    返回：
        {
            "xmx": "4G",                    # 最大堆内存
            "xms": "1G",                    # 初始堆内存
            "extra_args": [str, ...],       # 其他参数
            "raw_lines": [str, ...],        # 原始行（含注释）
        }
    """
    file_path = Path(file_path)
    result = {
        "xmx": "4G",
        "xms": "1G",
        "extra_args": [],
        "raw_lines": [],
    }

    if not file_path.exists():
        return result

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                result["raw_lines"].append(line)

                if not line or line.startswith("#"):
                    continue

                if line.startswith("-Xmx"):
                    result["xmx"] = line[4:]
                elif line.startswith("-Xms"):
                    result["xms"] = line[4:]
                else:
                    result["extra_args"].append(line)
    except Exception:
        pass

    return result


def write_user_jvm_args(
    file_path: Path,
    xmx: str,
    xms: str,
    extra_args: Optional[List[str]] = None,
    header_comment: Optional[str] = None,
) -> bool:
    """
    写入 user_jvm_args.txt。

    参数：
        file_path: 文件路径
        xmx: 最大堆内存，如 "4G"
        xms: 初始堆内存，如 "1G"
        extra_args: 其他 JVM 参数列表
        header_comment: 文件顶部的注释

    返回：
        是否成功
    """
    file_path = Path(file_path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            if header_comment:
                for line in header_comment.split("\n"):
                    f.write(f"# {line}\n")
                f.write("\n")
            f.write(f"-Xms{xms}\n")
            f.write(f"-Xmx{xmx}\n")
            if extra_args:
                for arg in extra_args:
                    f.write(f"{arg}\n")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------
# 内存值解析与格式化
# ------------------------------------------------------------------

def parse_memory_value(value: str) -> Optional[int]:
    """
    解析内存值为 MB 整数。
    支持的格式：4G / 4096M / 4g / 4096m
    返回：MB 整数；解析失败返回 None
    """
    if not value:
        return None
    value = value.strip().upper()
    try:
        if value.endswith("G"):
            return int(float(value[:-1]) * 1024)
        if value.endswith("M"):
            return int(float(value[:-1]))
        # 纯数字（按 MB 处理）
        return int(float(value))
    except (ValueError, TypeError):
        return None


def format_memory_value(mb: int) -> str:
    """将 MB 整数格式化为 "4G" 或 "512M" 字符串"""
    if mb <= 0:
        return "1G"
    if mb >= 1024 and mb % 1024 == 0:
        return f"{mb // 1024}G"
    return f"{mb}M"


# ------------------------------------------------------------------
# 应用预设模板
# ------------------------------------------------------------------

def apply_preset(preset_key: str) -> Optional[Dict[str, object]]:
    """
    从预设模板获取配置。
    返回一个可直接传给 write_user_jvm_args 的字典。
    """
    if preset_key not in JVM_PRESETS:
        return None

    preset = JVM_PRESETS[preset_key]
    return {
        "xmx": preset["xmx"],
        "xms": preset["xms"],
        "extra_args": list(preset["extra_args"]),
    }


# ------------------------------------------------------------------
# 验证 JVM 参数合法性
# ------------------------------------------------------------------

def validate_memory_value(value: str) -> Tuple[bool, str]:
    """
    验证内存值格式是否合法。
    返回：(是否合法, 说明信息)
    """
    if not value or not value.strip():
        return False, "不能为空"
    parsed = parse_memory_value(value)
    if parsed is None:
        return False, f"格式错误：{value}（应为如 4G、2048M 等）"
    if parsed < 512:
        return False, "内存过小（至少 512M）"
    if parsed > 65536:
        return False, "内存过大（超过 64G）"
    return True, f"✓ {format_memory_value(parsed)} ({parsed} MB)"


# ------------------------------------------------------------------
# 便捷：写入 Forge/NeoForge 风格的 user_jvm_args.txt
# ------------------------------------------------------------------

def apply_memory_to_user_jvm_args(
    file_path: Path,
    memory: str,
    preset_key: str = "default",
) -> bool:
    """
    根据内存值和预设模板，写入 user_jvm_args.txt。
    这是最常见的用户操作：选择一个内存大小 → 自动生成合理的参数。

    参数：
        file_path: user_jvm_args.txt 路径
        memory: 内存值，如 "4G"、"8G"
        preset_key: 预设模板名（default / performance / compact / minimal）

    返回：
        是否成功
    """
    # 解析内存值
    xmx_val = parse_memory_value(memory) or 4096
    xms_val = max(512, xmx_val // 2)  # 初始内存设为最大内存的一半

    # 获取预设
    preset = apply_preset(preset_key) or apply_preset("default")
    preset["xmx"] = format_memory_value(xmx_val)
    preset["xms"] = format_memory_value(xms_val)

    header = (
        "服务器 JVM 参数（由 MC Server Maker 生成）",
        f"-Xms{preset['xms']} = 初始堆内存",
        f"-Xmx{preset['xmx']} = 最大堆内存",
        "其他参数为性能优化建议，如不了解请勿修改",
    )

    return write_user_jvm_args(
        file_path,
        xmx=preset["xmx"],
        xms=preset["xms"],
        extra_args=preset["extra_args"],
        header_comment="\n".join(header),
    )


# ------------------------------------------------------------------
# 额外的服务端启动参数（直接传递给 MC 服务端）
# ------------------------------------------------------------------

def format_extra_server_args(args: Dict[str, object]) -> List[str]:
    """
    将字典形式的额外参数转换为命令行参数列表。

    常见的 MC 服务端参数：
        nogui               # 不显示 GUI 控制台
        --port 25565        # 指定端口（覆盖 server.properties）
        --host 0.0.0.0      # 指定绑定 IP
        --world world       # 指定世界名
        --bukkit-settings   # 指定 Bukkit 配置（仅 Bukkit 系）

    示例输入：
        {"nogui": True, "--port": "25565", "--host": "127.0.0.1"}

    示例输出：
        ["nogui", "--port", "25565", "--host", "127.0.0.1"]
    """
    result = []
    for key, value in args.items():
        if isinstance(value, bool):
            if value:
                # 无值的标志（如 nogui）
                result.append(key if not key.startswith("-") else key)
        else:
            # 有值的参数
            result.append(key)
            result.append(str(value))
    return result
