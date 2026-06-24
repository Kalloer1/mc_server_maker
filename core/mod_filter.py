# mod_filter.py —— 智能模组分离模块
# 职责：
#   1. 遍历所有模组 jar 文件，提取 modId
#   2. 查询数据库获取环境侧（client / server / both）
#   3. 数据库未知时，从 jar 内部解析 side 字段
#   4. 仍无法确定时，使用黑名单进行文件名模糊匹配
#   5. 将分离结果返回，同时自动记录新发现到 local_discoveries.json
#
# 查询优先级：
#   在线数据库缓存 → 本地发现 → jar 内 side 字段解析 → 黑名单匹配 → 保留（按 server 处理）

import re
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple

from utils.constants import MOD_BLACKLIST_KEYWORDS
from utils.file_utils import read_zip_entry
from core.mod_db import ModDatabase


def filter_mods(
    mod_files: List[str],
    mod_db: ModDatabase,
    progress_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, List[str]]:
    """
    智能分离模组：判断每个模组是客户端还是服务端环境。

    参数：
        mod_files: 所有模组 jar 文件的路径字符串列表
        mod_db: ModDatabase 实例
        progress_callback: 每个模组处理完成时的回调，参数为模组文件名
        cancel_check: 取消检查回调

    返回：
        {
            "server_mods": [str, ...],    # 服务端保留的模组路径
            "client_mods": [str, ...],    # 纯客户端模组路径（不复制）
            "unknown_mods": [str, ...],   # 无法确定环境的模组路径
            "mod_details": {              # 每个模组的详细信息
                "path/to/mod.jar": {
                    "modid": "jei",
                    "side": "client",   # client / server / both / unknown
                    "version": "15.3.0",  # 模组版本号
                    "author": " mezz",    # 作者
                },
                ...
            }
        }
    """
    server_mods = []
    client_mods = []
    unknown_mods = []
    mod_details = {}
    unknown_count = 0

    total = len(mod_files)

    for idx, mod_path in enumerate(mod_files):
        if cancel_check and cancel_check():
            raise InterruptedError("模组过滤已被取消")

        mod_file = Path(mod_path)
        mod_name = mod_file.name

        # ---- 步骤 1：进入 jar 内部读取 modId、版本号、作者 ----
        mod_info = _extract_full_mod_info(mod_file)
        modid = mod_info.get("modid", "")
        version = mod_info.get("version", "")
        author = mod_info.get("author", "")

        if progress_callback:
            if modid:
                hint = f"→ {modid}"
                if version:
                    hint += f" v{version}"
                progress_callback(f"[{idx + 1}/{total}] {mod_name} {hint}")
            else:
                progress_callback(f"[{idx + 1}/{total}] {mod_name} → 无法从jar内读取，回退到文件名")

        # ---- 步骤 2：查询数据库 ----
        side = mod_db.get_mod_side(modid) if modid else "unknown"

        # ---- 步骤 3：数据库未知 → jar 内解析 side 字段 ----
        if side == "unknown" and modid:
            jar_side = _parse_side_from_jar(mod_file)
            if jar_side != "unknown":
                side = jar_side
                # 自动记录到本地发现
                mod_db.add_local_discovery(modid, side)

        # ---- 步骤 4：仍未知 → 黑名单匹配 ----
        if side == "unknown":
            side = _match_blacklist(mod_name, modid or "")

        # ---- 步骤 5：分类 ----
        if side == "client":
            client_mods.append(mod_path)
        elif side == "server" or side == "both":
            server_mods.append(mod_path)
        else:
            # 无法确定，默认保留（按 both 处理），但记录数量供后续提示
            unknown_mods.append(mod_path)
            server_mods.append(mod_path)
            unknown_count += 1

        # 记录详细信息
        mod_details[mod_path] = {
            "modid": modid or "(未识别)",
            "side": side,
            "version": version,
            "author": author,
        }

    return {
        "server_mods": server_mods,
        "client_mods": client_mods,
        "unknown_mods": unknown_mods,
        "unknown_count": unknown_count,
        "mod_details": mod_details,
    }


# ============================================================
# modId / 版本号 / 作者 提取
# ============================================================

def _extract_full_mod_info(jar_path: Path) -> dict:
    """
    从 jar 文件中提取完整的模组信息。

    NeoForge 模组：读取 META-INF/neoforge.mods.toml
    Forge 模组：读取 META-INF/mods.toml
    Fabric 模组：读取 fabric.mod.json
    回退：从文件名中提取

    返回：
        {"modid": str, "version": str, "author": str}
    """
    result = {"modid": "", "version": "", "author": ""}

    # 尝试 NeoForge 的 neoforge.mods.toml（优先）
    neoforge_toml = read_zip_entry(jar_path, "META-INF/neoforge.mods.toml")
    if neoforge_toml:
        info = _parse_forge_mod_info_from_toml(neoforge_toml)
        if info.get("modid"):
            return info

    # 尝试 Forge 的 mods.toml
    forge_toml = read_zip_entry(jar_path, "META-INF/mods.toml")
    if forge_toml:
        info = _parse_forge_mod_info_from_toml(forge_toml)
        if info.get("modid"):
            return info

    # 尝试 Fabric 的 fabric.mod.json
    json_content = read_zip_entry(jar_path, "fabric.mod.json")
    if json_content:
        info = _parse_fabric_mod_info_from_json(json_content)
        if info.get("modid"):
            return info

    # 回退：从文件名推断 modid
    result["modid"] = _extract_mod_id_from_filename(jar_path.name)
    return result


def _extract_mod_id(jar_path: Path) -> str:
    """仅提取 modId（保留兼容性）"""
    return _extract_full_mod_info(jar_path).get("modid", "")


def _extract_mod_id_from_filename(filename: str) -> str:
    """
    从模组文件名推断 modId。

    常见格式：
        jei-1.20.1-15.3.0.8.jar → jei
        appleskin-forge-1.20.1-2.5.1.jar → appleskin
        JustEnoughItems-1.20.1-15.3.0.8.jar → justenoughitems
    """
    name = filename
    # 移除 .jar 后缀
    if name.lower().endswith(".jar"):
        name = name[:-4]

    # 尝试移除版本号后缀（数字开头或包含数字的版本号）
    # 格式: modname-1.20.1-15.3.0.8 或 modname-15.3.0.8
    m = re.match(r'^(.+?)-(\d+\.\d+.*)$', name)
    if m:
        return m.group(1).strip().lower()

    return name.strip().lower()


def _parse_forge_mod_id_from_toml(content: str) -> str:
    """仅提取 modId（保留兼容性，内部调用完整解析函数）"""
    info = _parse_forge_mod_info_from_toml(content)
    return info.get("modid", "")


def _parse_forge_mod_info_from_toml(content: str) -> dict:
    """
    从 mods.toml 内容中提取 [[mods]] 段下的 modId、version、authors。

    格式示例：
        [[mods]]
        modId="acceleratedrecoiling"
        version="21.1.13-alpha"
        displayName="AcceleratedRecoiling"
        authors="wiyuka"
        description='''A mod aabb collision optimization.'''
    """
    result = {"modid": "", "version": "", "author": ""}

    # 提取 [[mods]] 段
    mods_section = re.search(
        r'\[\[mods\]\]\s*\n(.*?)(?=\n\[\[|\Z)',
        content, re.DOTALL | re.IGNORECASE
    )
    section_text = mods_section.group(1) if mods_section else content

    # 提取 modId
    m = re.search(
        r'^\s*modId\s*=\s*["\']([^"\']+)["\']',
        section_text, re.MULTILINE | re.IGNORECASE
    )
    if m:
        result["modid"] = m.group(1).strip()
    else:
        # 回退：全局搜索
        m = re.search(r'modId\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
        if m:
            result["modid"] = m.group(1).strip()

    # 提取 version（在 [[mods]] 段内）
    m = re.search(
        r'^\s*version\s*=\s*["\']([^"\']+)["\']',
        section_text, re.MULTILINE | re.IGNORECASE
    )
    if m:
        result["version"] = m.group(1).strip()

    # 提取 authors（可能在同一行或跨行）
    m = re.search(
        r'^\s*authors\s*=\s*["\']([^"\']+)["\']',
        section_text, re.MULTILINE | re.IGNORECASE
    )
    if m:
        result["author"] = m.group(1).strip()

    return result


def _parse_fabric_mod_id_from_json(content: str) -> str:
    """仅提取 modId（保留兼容性）"""
    info = _parse_fabric_mod_info_from_json(content)
    return info.get("modid", "")


def _parse_fabric_mod_info_from_json(content: str) -> dict:
    """
    从 fabric.mod.json 内容中提取 id、version 字段。

    Fabric 格式：
    {
        "schemaVersion": 1,
        "id": "modid",
        "version": "1.0.0",
        "name": "Mod Name",
        "authors": [...],
        ...
    }
    """
    import json
    result = {"modid": "", "version": "", "author": ""}
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            modid = data.get("id", "")
            if modid:
                result["modid"] = str(modid).strip()
            version = data.get("version", "")
            if version:
                result["version"] = str(version).strip()
            # authors 可能是列表或字符串
            authors = data.get("authors")
            if isinstance(authors, list):
                result["author"] = ", ".join(str(a) for a in authors)
            elif isinstance(authors, str):
                result["author"] = authors.strip()
    except json.JSONDecodeError:
        pass
    return result


# ============================================================
# jar 内 side 字段解析
# ============================================================

def _parse_side_from_jar(jar_path: Path) -> str:
    """
    直接从 jar 内部元数据解析环境侧。

    NeoForge (neoforge.mods.toml)：side 字段，值为 BOTH / CLIENT / SERVER
    Forge (mods.toml)：side 字段，值为 BOTH / CLIENT / SERVER / DEDICATED_SERVER
    Fabric (fabric.mod.json)：environment 字段，值为 * / client / server

    返回：
        "client" / "server" / "both" / "unknown"
    """
    # NeoForge: 读取 neoforge.mods.toml 的 side 字段
    neoforge_toml = read_zip_entry(jar_path, "META-INF/neoforge.mods.toml")
    if neoforge_toml:
        side = _parse_forge_side_from_toml(neoforge_toml)
        if side != "unknown":
            return side

    # Forge: 读取 mods.toml 的 side 字段
    forge_toml = read_zip_entry(jar_path, "META-INF/mods.toml")
    if forge_toml:
        side = _parse_forge_side_from_toml(forge_toml)
        if side != "unknown":
            return side

    # Fabric: 读取 environment 字段
    json_content = read_zip_entry(jar_path, "fabric.mod.json")
    if json_content:
        side = _parse_fabric_environment_from_json(json_content)
        if side != "unknown":
            return side

    return "unknown"


def _parse_forge_side_from_toml(content: str) -> str:
    """
    从 mods.toml 的 [[mods]] 段解析 side 字段。

    side 可能的值：BOTH / CLIENT / SERVER / DEDICATED_SERVER
    """
    # 在 [[mods]] 段中查找 side
    mods_section = re.search(
        r'\[\[mods\]\]\s*\n(.*?)(?=\n\[\[|\Z)',
        content, re.DOTALL | re.IGNORECASE
    )
    if mods_section:
        m = re.search(
            r'^\s*side\s*=\s*["\']([^"\']+)["\']',
            mods_section.group(1), re.MULTILINE | re.IGNORECASE
        )
        if m:
            raw_side = m.group(1).upper().strip()
            if raw_side == "CLIENT":
                return "client"
            elif raw_side in ("SERVER", "DEDICATED_SERVER"):
                return "server"
            elif raw_side == "BOTH":
                return "both"

    # 回退：全局搜索
    m = re.search(r'side\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if m:
        raw_side = m.group(1).upper().strip()
        if raw_side == "CLIENT":
            return "client"
        elif raw_side in ("SERVER", "DEDICATED_SERVER"):
            return "server"
        elif raw_side == "BOTH":
            return "both"
    return "unknown"


def _parse_fabric_environment_from_json(content: str) -> str:
    """
    从 fabric.mod.json 解析 environment 字段。

    environment 可能的值："*" (both), "client", "server"
    结构可能在不同位置（顶层或 custom 字段下的某处）
    """
    import json
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return "unknown"

        # 优先从顶层取
        env = data.get("environment", "")
        if isinstance(env, str):
            env = env.strip().lower()
            if env in ("client",):
                return "client"
            elif env in ("server",):
                return "server"
            elif env in ("*", "both", "all"):
                return "both"

        # 某些模组把 environment 放在 entrypoints 或 depends 等字段中
        # 额外兼容：检查 mixes 或 custom 中的 side 字段
        for key in ("custom", "mixins", "entrypoints"):
            sub = data.get(key, {})
            if isinstance(sub, dict):
                env = sub.get("environment", "")
                if isinstance(env, str):
                    env = env.strip().lower()
                    if env in ("client",):
                        return "client"
                    elif env in ("server",):
                        return "server"
                    elif env in ("*", "both", "all"):
                        return "both"
    except json.JSONDecodeError:
        pass

    return "unknown"


# ============================================================
# 黑名单模糊匹配
# ============================================================

def _match_blacklist(mod_name: str, modid: str) -> str:
    """
    使用文件名和 modId 与黑名单关键字进行模糊匹配。

    参数：
        mod_name: 模组文件名（如 "jei-1.20.1-15.3.0.8.jar"）
        modid: 已提取的 modId（可能为空）

    返回：
        匹配到黑名单 → "client"，未匹配 → "unknown"
    """
    search_target = (mod_name + " " + modid).lower()

    for keyword in MOD_BLACKLIST_KEYWORDS:
        if keyword in search_target:
            return "client"

    return "unknown"


class InterruptedError(Exception):
    """模组过滤被用户主动取消的内部异常"""
    pass