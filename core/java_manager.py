# java_manager.py —— Java 版本管理模块
# 职责：
#   1. 扫描系统中所有 Java 安装
#   2. 检测每个 Java 的版本号
#   3. 判断 Java 是否与指定 MC 版本兼容
#   4. 提供多版本选择供用户使用
#
# Windows Java 扫描策略：
#   - 从 PATH 中查找 java 命令
#   - 从常见安装目录扫描（C:\Program Files\Java\）
#   - 从注册表读取 JavaSoft 安装信息

import os
import re
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ------------------------------------------------------------------
# MC 版本对 Java 版本的要求
# ------------------------------------------------------------------

JAVA_REQUIREMENTS = {
    # MC 1.12.2 及以下
    (1, 12): {"min": 8, "recommended": 8, "note": "Java 8 推荐"},
    # MC 1.13-1.16
    (1, 13): {"min": 8, "recommended": 11, "note": "Java 11 推荐"},
    (1, 14): {"min": 8, "recommended": 11, "note": "Java 11 推荐"},
    (1, 15): {"min": 8, "recommended": 11, "note": "Java 11 推荐"},
    (1, 16): {"min": 8, "recommended": 16, "note": "Java 16 推荐"},
    # MC 1.17+ 需要 Java 16+
    (1, 17): {"min": 16, "recommended": 17, "note": "Java 17 推荐"},
    (1, 18): {"min": 17, "recommended": 18, "note": "Java 18 推荐"},
    (1, 19): {"min": 17, "recommended": 19, "note": "Java 19 推荐"},
    (1, 20): {"min": 17, "recommended": 21, "note": "Java 21 推荐"},
    # MC 1.21+ 需要 Java 21+
    (1, 21): {"min": 21, "recommended": 21, "note": "Java 21 必需"},
}


def _parse_mc_version(mc_version: str) -> Tuple[int, int, int]:
    """
    解析 MC 版本字符串为 (major, minor, patch) 元组。
    例如 "1.20.1" -> (1, 20, 1)，"1.21" -> (1, 21, 0)
    """
    parts = mc_version.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (1, 20, 0)  # 默认值


def _parse_java_version(version_output: str) -> Tuple[int, int, int]:
    """
    从 java -version 输出解析 Java 主版本号。
    格式示例：
        openjdk version "21.0.5" ...
        java version "17.0.12" ...
        java version "1.8.0_361"
    返回：(major, minor, patch)
    """
    # 格式: "21.0.5" 或 "17.0.17" 或 "1.8.0_361"
    # 注意：不要求结尾必须是 [._]，因为新格式可能直接以 " 结尾
    m = re.search(r'"(\d+)\.(\d+)\.(\d+)', version_output)
    if m:
        first = int(m.group(1))
        second = int(m.group(2))
        third = int(m.group(3))
        if first == 1:
            # 旧格式: "1.8.0_361" → Java 8
            return (second, third, 0)
        else:
            # 新格式: "17.0.17", "21.0.5"
            return (first, second, third)

    # 格式: "21" (纯主版本)
    m = re.search(r'"(\d+)"', version_output)
    if m:
        return (int(m.group(1)), 0, 0)

    return (0, 0, 0)


def _run_java_version(java_path: str) -> Optional[str]:
    """执行 java -version 并返回 stderr 输出"""
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace"
        )
        return result.stderr.strip() or result.stdout.strip() or None
    except Exception:
        return None


# ------------------------------------------------------------------
# Java 安装扫描
# ------------------------------------------------------------------

def find_all_java_installations() -> List[Dict[str, object]]:
    """
    扫描系统中所有可用的 Java 安装。

    返回：
        List[{
            "java_path": str,     # java.exe 完整路径
            "version": str,       # 原始版本字符串（"21.0.5"）
            "major_version": int, # 主版本号（21）
            "display_name": str,  # 显示名称（"Java 21 (21.0.5)"）
            "source": str,        # 来源（"PATH" / "INSTALL_DIR" / "REGISTRY"）
        }]
    """
    found = {}  # java_path -> info，避免重复

    # 1. 从 PATH 中查找
    java_from_path = shutil.which("java")
    if java_from_path:
        info = _probe_java(java_from_path, "PATH")
        if info:
            found[java_from_path] = info

    # 2. 从常见安装目录扫描
    common_dirs = []
    if os.environ.get("ProgramFiles"):
        common_dirs.append(os.path.join(os.environ["ProgramFiles"], "Java"))
    if os.environ.get("ProgramFiles(x86)"):
        common_dirs.append(os.path.join(os.environ["ProgramFiles(x86)"], "Java"))
    # JDK 当前用户安装位置
    user_java = os.path.join(os.path.expanduser("~"), "Java")
    if os.path.exists(user_java):
        common_dirs.append(user_java)

    for base_dir in common_dirs:
        if not os.path.isdir(base_dir):
            continue
        try:
            for subdir in os.listdir(base_dir):
                jdk_dir = os.path.join(base_dir, subdir, "bin", "java.exe")
                if os.path.isfile(jdk_dir) and jdk_dir not in found:
                    info = _probe_java(jdk_dir, "INSTALL_DIR")
                    if info:
                        found[jdk_dir] = info
        except PermissionError:
            continue

    # 3. 从注册表扫描（Windows）
    if hasattr(os, "startfile"):  # Windows
        _scan_registry_java(found)

    result = list(found.values())
    # 按主版本降序排序（最新的在前）
    result.sort(key=lambda x: x["major_version"], reverse=True)
    return result


def _probe_java(java_path: str, source: str) -> Optional[Dict[str, object]]:
    """探测单个 Java 安装的版本信息"""
    if not os.path.isfile(java_path):
        return None

    version_output = _run_java_version(java_path)
    if not version_output:
        return None

    major, minor, patch = _parse_java_version(version_output)
    if major == 0:
        return None

    version_str = f"{major}.{minor}.{patch}" if patch > 0 else f"{major}.{minor}"

    display_name = f"Java {major}"
    if minor > 0 or patch > 0:
        display_name += f" ({version_str})"
    if major >= 11:
        display_name += f" [{_get_java_name(major)}]"

    return {
        "java_path": java_path,
        "version": version_str,
        "major_version": major,
        "display_name": display_name,
        "source": source,
    }


def _get_java_name(major: int) -> str:
    """获取 Java 代号名称"""
    names = {
        8: "LTS",
        11: "LTS",
        17: "LTS",
        21: "LTS",
        22: "Latest",
    }
    return names.get(major, f"{major}")


def _scan_registry_java(found: dict):
    """从 Windows 注册表扫描 Java 安装"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\JavaSoft\Java Development Kit",
            0, winreg.KEY_READ
        )
        try:
            i = 0
            while True:
                subkey_name = winreg.EnumKey(key, i)
                version = subkey_name
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                        java_exe = os.path.join(java_home, "bin", "java.exe")
                        if os.path.isfile(java_exe) and java_exe not in found:
                            info = _probe_java(java_exe, "REGISTRY")
                            if info:
                                found[java_exe] = info
                    except WindowsError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                except WindowsError:
                    pass
                i += 1
        except WindowsError:
            pass
        finally:
            winreg.CloseKey(key)
    except WindowsError:
        pass

    # 也扫描 JRE
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\JavaSoft\Java Runtime Environment",
            0, winreg.KEY_READ
        )
        try:
            i = 0
            while True:
                subkey_name = winreg.EnumKey(key, i)
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                        java_exe = os.path.join(java_home, "bin", "java.exe")
                        if os.path.isfile(java_exe) and java_exe not in found:
                            info = _probe_java(java_exe, "REGISTRY")
                            if info:
                                found[java_exe] = info
                    except WindowsError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                except WindowsError:
                    pass
                i += 1
        except WindowsError:
            pass
        finally:
            winreg.CloseKey(key)
    except WindowsError:
        pass


# ------------------------------------------------------------------
# MC 版本兼容性检测
# ------------------------------------------------------------------

def check_java_for_mc_version(java_major: int, mc_version: str) -> Tuple[bool, str]:
    """
    判断指定的 Java 版本是否适合运行指定版本的 Minecraft 服务端。

    参数：
        java_major: Java 主版本号（如 17, 21）
        mc_version: MC 版本字符串（如 "1.20.1"）

    返回：
        (是否兼容, 说明字符串)
    """
    major, minor, patch = _parse_mc_version(mc_version)
    key = (major, minor)

    # 查找最接近的需求
    req = None
    for version_key, requirement in sorted(JAVA_REQUIREMENTS.items()):
        if version_key <= key:
            req = requirement
        else:
            break

    if req is None:
        # 新版本 MC，未知需求
        if java_major >= 21:
            return True, f"Java {java_major} 应支持 MC {mc_version}（未经测试的新版本，建议使用 Java 21）"
        else:
            return False, f"MC {mc_version} 可能需要更高版本的 Java，建议使用 Java 21"

    min_java = req["min"]
    recommended = req["recommended"]

    if java_major < min_java:
        return False, (
            f"Java {java_major} 版本过低！MC {mc_version} 最低需要 Java {min_java}。\n"
            f"建议使用 Java {recommended} 或更高版本。"
        )
    elif java_major == recommended:
        return True, f"✅ Java {java_major} 是 MC {mc_version} 的推荐版本 ✓"
    elif java_major > recommended:
        if java_major >= 21 and recommended < 21:
            return True, f"✅ Java {java_major} 满足要求（NeoForge 推荐 Java 21）✓"
        return True, f"✅ Java {java_major} 满足要求 ✓"
    else:
        return True, f"⚠ Java {java_major} 可以运行 MC {mc_version}，但推荐 Java {recommended}"


def check_system_java() -> Tuple[bool, str, int]:
    """
    检测系统默认 Java 是否可用及版本。

    返回：
        (是否可用, 版本信息字符串, 主版本号)
    """
    java_path = shutil.which("java")
    if not java_path:
        return False, "未找到 Java", 0

    version_output = _run_java_version(java_path)
    if not version_output:
        return False, f"Java 路径: {java_path}，但无法读取版本", 0

    major, _, _ = _parse_java_version(version_output)
    return True, version_output, major


def format_java_choice(javainfo: dict, mc_version: Optional[str] = None) -> str:
    """
    格式化 Java 选择项的显示字符串。

    参数：
        javainfo: find_all_java_installations() 返回的字典
        mc_version: 可选，MC 版本号用于显示兼容性

    返回：
        显示字符串
    """
    display = javainfo["display_name"]

    if mc_version:
        compatible, note = check_java_for_mc_version(javainfo["major_version"], mc_version)
        if not compatible:
            display = f"⚠ {display}（不兼容）"
        elif "推荐" in note or "✅" in note:
            display = f"✓ {display}"

    return display
