# scanner.py —— 游戏目录扫描模块
# 职责：
#   1. 从目录下的 .jar / .json 文件配对识别整合包名称
#   2. 从 JSON 文件解析 MC 版本、加载器类型/版本
#   3. 仅扫描当前目录下的 mods 文件夹
#   4. 仅检测当前目录下的配置文件夹
#   5. 返回结构化扫描结果

import json
import re
from pathlib import Path
from typing import Optional, Dict, List


def scan_game_directory(game_dir: Path) -> Dict[str, object]:
    """
    扫描游戏版本目录，返回完整的识别信息。

    新逻辑：
        1. 在当前目录下寻找 .jar 和 .json 同名配对
           例: 1.21.1-NeoForge_21.1.222.jar + 1.21.1-NeoForge_21.1.222.json
           整合包名称 = 1.21.1-NeoForge
        2. 从 JSON 文件读取版本/加载器信息
        3. 仅扫描当前目录下的 mods/
        4. 仅检测当前目录下的子文件夹

    返回：
        {
            "pack_name": str,            # 整合包名称
            "mc_version": str,           # 如 "1.21.1"
            "loader_type": str,          # "forge" / "fabric" / "neoforge" / "vanilla"
            "loader_version": str,       # 如 "21.1.221"
            "mod_count": int,
            "mod_files": [str, ...],     # 所有 .jar 模组文件的绝对路径
            "config_folders": [str, ...],# 检测到的配置文件夹名称
            "all_folders": [str, ...],   # 当前目录下所有子文件夹名称
            "game_dir": str,
        }
    """
    if not game_dir.exists():
        raise FileNotFoundError(f"游戏目录不存在: {game_dir}")

    # ================================================================
    # 第一步：在当前目录下寻找 .jar / .json 同名配对
    # ================================================================
    jar_files = list(game_dir.glob("*.jar"))
    json_files = list(game_dir.glob("*.json"))

    pack_name = ""
    mc_version = ""
    loader_type = "vanilla"
    loader_version = "unknown"
    matched_json = None

    # 寻找同名配对（不含扩展名）
    for jar in jar_files:
        jar_stem = jar.stem  # 不含 .jar 的文件名
        for js in json_files:
            if js.stem == jar_stem:
                # 找到同名配对！
                matched_json = js
                pack_name = jar_stem
                break
        if matched_json:
            break

    if not pack_name:
        # 没有找到配对，使用目录名作为 pack_name
        pack_name = game_dir.name

    # ================================================================
    # 第二步：从 JSON 文件读取版本/加载器信息
    # ================================================================
    if matched_json:
        vj_info = _parse_version_json_from_file(matched_json)
        if vj_info:
            mc_version = vj_info.get("mc_version", "")
            loader_type = vj_info.get("loader_type", "vanilla")
            loader_version = vj_info.get("loader_version", "unknown")

    # 如果 JSON 没提供足够信息，从 pack_name 解析
    if not mc_version:
        mc_version = _extract_mc_from_name(pack_name)
    if loader_type == "vanilla" and loader_version == "unknown":
        lt, lv = _extract_loader_from_name(pack_name)
        if lt != "vanilla":
            loader_type = lt
            loader_version = lv

    # ================================================================
    # 第三步：仅扫描当前目录下的 mods 文件夹
    # ================================================================
    mods_dir = game_dir / "mods"
    mod_files = []
    if mods_dir.exists() and mods_dir.is_dir():
        mod_files = sorted(
            [str(f) for f in mods_dir.glob("*.jar") if f.is_file()],
            key=lambda x: Path(x).name.lower(),
        )

    # ================================================================
    # 第四步：检测当前目录下的所有子文件夹（供用户手动选择复制）
    # ================================================================
    all_folders = []
    if game_dir.exists():
        for item in sorted(game_dir.iterdir()):
            if item.is_dir():
                name = item.name
                all_folders.append(name)

    return {
        "pack_name": pack_name,
        "mc_version": mc_version or "未知",
        "loader_type": loader_type,
        "loader_version": loader_version,
        "mod_count": len(mod_files),
        "mod_files": mod_files,
        "all_folders": all_folders,
        "game_dir": str(game_dir),
    }


def _parse_version_json_from_file(json_path: Path) -> Optional[Dict[str, str]]:
    """从指定 JSON 文件解析版本/加载器信息"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    result = {}

    # 优先从 arguments.game 解析
    fml_info = _parse_fml_arguments(data)
    if fml_info:
        result.update(fml_info)

    # MC 版本
    if "mc_version" not in result:
        if "inheritsFrom" in data:
            result["mc_version"] = data["inheritsFrom"]
        elif "id" in data:
            result["mc_version"] = data["id"]

    # 加载器类型
    if "loader_type" not in result:
        main_class = data.get("mainClass", "")
        if "fabricmc" in main_class.lower() or "fabric-loader" in main_class.lower():
            result["loader_type"] = "fabric"
        elif "neoforged" in main_class.lower() or "neoforge" in main_class.lower():
            result["loader_type"] = "neoforge"
        elif "net.minecraftforge" in main_class or "cpw.mods" in main_class:
            result["loader_type"] = "forge"

    # 加载器版本
    if "loader_version" not in result:
        loader_version = _extract_loader_version_from_json(data)
        if loader_version:
            result["loader_version"] = loader_version

    return result


def _parse_fml_arguments(data: dict) -> Dict[str, str]:
    """从 arguments.game 数组中解析 FML 参数"""
    result = {}
    args = data.get("arguments", {})
    if isinstance(args, dict):
        game_args = args.get("game", [])
    else:
        game_args = []

    if not game_args or not isinstance(game_args, list):
        return result

    for i, arg in enumerate(game_args):
        if not isinstance(arg, str):
            continue
        if arg.startswith("--fml.") and i + 1 < len(game_args):
            value = str(game_args[i + 1])
            if arg == "--fml.mcVersion":
                result["mc_version"] = value
            elif arg == "--fml.neoForgeVersion":
                result["loader_type"] = "neoforge"
                result["loader_version"] = value
            elif arg == "--fml.forgeVersion":
                result["loader_type"] = "forge"
                result["loader_version"] = value
            elif arg == "--fml.fabricVersion":
                result["loader_type"] = "fabric"
                result["loader_version"] = value

    # 从 launchTarget 推断
    for i, arg in enumerate(game_args):
        if isinstance(arg, str) and arg == "--launchTarget" and i + 1 < len(game_args):
            lt = str(game_args[i + 1]).lower()
            if "loader_type" not in result:
                if "neoforge" in lt or "neo" in lt:
                    result["loader_type"] = "neoforge"
                elif "forge" in lt:
                    result["loader_type"] = "forge"
                elif "fabric" in lt:
                    result["loader_type"] = "fabric"
            break

    return result


def _extract_loader_version_from_json(data: dict) -> str:
    """从 version JSON 的 libraries 列表提取加载器版本"""
    libraries = data.get("libraries", [])
    for lib in libraries:
        if isinstance(lib, dict):
            name = lib.get("name", "")
            m = re.search(
                r"(?:net\.minecraftforge:forge|net\.neoforged:neoforge):([0-9.]+(?:-[0-9.]+)?)",
                name,
            )
            if m:
                return m.group(1)
            m = re.search(r"net\.fabricmc:fabric-loader:([0-9.]+)", name)
            if m:
                return m.group(1)
    return ""


def _extract_mc_from_name(name: str) -> str:
    """从名称中提取 MC 版本号"""
    m = re.search(r'(\d+\.\d+(?:\.\d+)?)', name)
    return m.group(1) if m else ""


def _extract_loader_from_name(name: str) -> tuple:
    """从名称中提取加载器类型和版本"""
    name_lower = name.lower()
    # NeoForge: xxx-NeoForge_21.1.222
    m = re.search(r'neoforge[_-](\d+\.\d+(?:\.\d+)?)', name_lower)
    if m:
        return ("neoforge", m.group(1))
    # Forge: xxx-forge-47.2.0 或 xxx-Forge_47.2.0
    m = re.search(r'forge[_-](\d+\.\d+(?:\.\d+)?)', name_lower)
    if m:
        return ("forge", m.group(1))
    # Fabric: xxx-fabric-0.15.7
    m = re.search(r'fabric[_-](\d+\.\d+(?:\.\d+)?)', name_lower)
    if m:
        return ("fabric", m.group(1))
    return ("vanilla", "unknown")