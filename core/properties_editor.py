# properties_editor.py —— server.properties 解析与编辑模块
# 职责：
#   1. 读取 server.properties 文件，解析为 key=value 列表
#   2. 提供常用项的类型安全的 get/set 接口
#   3. 保存时保留原始行顺序和注释
#   4. 提供选项元数据（说明、类型、可选值）供 UI 使用
#
# server.properties 格式：
#   # 这是注释（以 # 开头）
#   key=value
#   空行被保留
#
# 设计要点：
#   - 行顺序敏感：保存时保持原始顺序
#   - 注释保留：# 开头的行和空行都保留
#   - 提供元数据：每个常见 key 都有中文说明和类型提示

from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# server.properties 常用项元数据（供 UI 显示）
# ------------------------------------------------------------------

# 元数据: key -> (中文说明, 类型, 默认值, 可选值/范围)
PROPERTY_META: Dict[str, Tuple[str, str, object, Optional[List[str]]]] = {
    # 服务器基础
    "server-port": ("服务器端口（玩家连接的端口）", "int", 25565, None),
    "server-ip": ("绑定的 IP 地址（留空=全部）", "string", "", None),
    "motd": ("服务器名称（显示在多人游戏列表中）", "string", "A Minecraft Server", None),
    "max-players": ("最大在线玩家数", "int", 20, None),
    "online-mode": ("正版验证（True=必须正版登录）", "bool", True, ["true", "false"]),
    "allow-flight": ("允许飞行（作弊客户端用飞行 Mod 也需此选项）", "bool", False, ["true", "false"]),

    # 游戏模式与难度
    "gamemode": ("默认游戏模式", "enum", "survival",
                 ["survival", "creative", "adventure", "spectator"]),
    "difficulty": ("游戏难度", "enum", "easy",
                   ["peaceful", "easy", "normal", "hard"]),
    "hardcore": ("极限模式（死亡后无法复活）", "bool", False, ["true", "false"]),
    "force-gamemode": ("强制所有玩家使用默认游戏模式", "bool", False, ["true", "false"]),

    # 世界设置
    "level-name": ("世界名称（即 world 目录名）", "string", "world", None),
    "level-seed": ("世界种子（留空随机）", "string", "", None),
    "level-type": ("世界类型（minecraft\\:normal 等）", "string", "minecraft:normal", None),
    "generate-structures": ("生成建筑（村庄、地牢等）", "bool", True, ["true", "false"]),
    "spawn-npcs": ("生成 NPC 村民", "bool", True, ["true", "false"]),
    "spawn-animals": ("生成动物", "bool", True, ["true", "false"]),
    "spawn-monsters": ("生成怪物", "bool", True, ["true", "false"]),
    "spawn-protection": ("出生点保护半径（0=关闭）", "int", 16, None),
    "pvp": ("允许玩家对战（PVP）", "bool", True, ["true", "false"]),

    # 性能
    "view-distance": ("视距（区块数，影响性能）", "int", 10, None),
    "simulation-distance": ("模拟距离（实体/红石活跃范围）", "int", 10, None),
    "max-tick-time": ("单 tick 最大耗时（毫秒，-1 禁用崩溃检测）", "int", 60000, None),
    "sync-chunk-writes": ("同步写区块文件（禁用可能提高性能但有风险）", "bool", True, ["true", "false"]),
    "use-native-transport": ("使用原生 Socket 传输（提高网络性能）", "bool", True, ["true", "false"]),
    "network-compression-threshold": ("网络压缩阈值（字节，256=推荐，-1=禁用）", "int", 256, None),

    # 玩家/白名单/OP
    "enable-command-block": ("启用命令方块（创造模式玩家可放置）", "bool", False, ["true", "false"]),
    "op-permission-level": ("OP 权限等级（1=绕过出生点，2=可使用作弊命令，3=可管理他人，4=可管理服务器）", "int", 4, ["1", "2", "3", "4"]),
    "function-permission-level": ("函数执行权限等级", "int", 2, ["1", "2", "3", "4"]),
    "prevent-proxy-connections": ("阻止代理/VPN 连接", "bool", False, ["true", "false"]),
    "enforce-secure-profile": ("强制安全档案（1.19+ 聊天签名）", "bool", True, ["true", "false"]),
    "white-list": ("启用白名单（需 manual 在 whitelist.json 添加玩家）", "bool", False, ["true", "false"]),

    # 资源包
    "resource-pack": ("资源包 URL（可选）", "string", "", None),
    "resource-pack-sha1": ("资源包 SHA1 校验", "string", "", None),

    # 其他
    "enable-status": ("响应服务器列表状态查询", "bool", True, ["true", "false"]),
    "enable-query": ("启用查询协议（用于 server-query 端口）", "bool", False, ["true", "false"]),
    "query.port": ("查询端口", "int", 25565, None),
    "enable-rcon": ("启用远程控制台 RCON", "bool", False, ["true", "false"]),
    "rcon.port": ("RCON 端口", "int", 25575, None),
    "rcon.password": ("RCON 密码", "string", "", None),
    "broadcast-rcon-to-ops": ("RCON 操作广播给 OP", "bool", True, ["true", "false"]),
    "broadcast-console-to-ops": ("控制台消息广播给 OP", "bool", True, ["true", "false"]),
    "max-world-size": ("最大世界边界（区块）", "int", 29999984, None),
    "player-idle-timeout": ("玩家超时踢出（分钟，0=禁用）", "int", 0, None),
    "entity-broadcast-range-percentage": ("实体广播范围百分比（10-1000）", "int", 100, None),
    "text-filtering-config": ("文本过滤配置（路径或 URL）", "string", "", None),
    "allow-nether": ("允许下界（Nether 维度）", "bool", True, ["true", "false"]),
    "rate-limit": ("发包速率限制（每秒包数，0=禁用）", "int", 0, None),
    "log-ips": ("记录玩家连接 IP 到日志", "bool", True, ["true", "false"]),
}


# ------------------------------------------------------------------
# 核心：行级解析与保存
# ------------------------------------------------------------------

def load_properties(file_path: Path) -> Tuple[List[dict], Dict[str, str]]:
    """
    读取并解析 server.properties 文件。

    返回：
        (rows: List[dict], values: Dict[str, str])
        - rows: 按顺序的每一行数据（保留顺序和注释）
            {"type": "comment"|"blank"|"kv", "text": str, "key": str|None, "value": str|None}
        - values: key -> value 的字典（用于快速查找）
    """
    file_path = Path(file_path)
    rows: List[dict] = []
    values: Dict[str, str] = {}

    if not file_path.exists():
        return rows, values

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n").rstrip("\r")
                stripped = line.strip()

                if not stripped:
                    rows.append({"type": "blank", "text": ""})
                elif stripped.startswith("#"):
                    rows.append({"type": "comment", "text": line})
                elif "=" in stripped:
                    # key=value
                    idx = line.find("=")
                    key = line[:idx].strip()
                    value = line[idx + 1:].strip()
                    rows.append({
                        "type": "kv",
                        "text": line,
                        "key": key,
                        "value": value,
                    })
                    values[key] = value
                else:
                    # 无法解析的行，保留原样
                    rows.append({"type": "comment", "text": line})
    except Exception:
        # 文件损坏或编码问题，回退到空结果
        pass

    return rows, values


def save_properties(file_path: Path, rows: List[dict]) -> bool:
    """
    将行列表写回 server.properties 文件，保留原顺序和注释。

    参数：
        rows: 由 load_properties 返回并经过修改的行列表
    返回：
        是否成功
    """
    file_path = Path(file_path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for row in rows:
                if row["type"] == "blank":
                    f.write("\n")
                elif row["type"] == "kv":
                    key = row.get("key", "")
                    value = row.get("value", "")
                    f.write(f"{key}={value}\n")
                else:  # comment
                    f.write(f"{row.get('text', '')}\n")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------
# 便捷：get/set（基于字典）
# ------------------------------------------------------------------

def get_value(values: Dict[str, str], key: str, default: str = "") -> str:
    """获取字符串值"""
    return values.get(key, default)


def get_int(values: Dict[str, str], key: str, default: int = 0) -> int:
    """获取整数"""
    v = values.get(key, "")
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def get_bool(values: Dict[str, str], key: str, default: bool = False) -> bool:
    """获取布尔值"""
    v = values.get(key, "").strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return default


def set_value(rows: List[dict], key: str, value: str) -> bool:
    """
    在 rows 中设置 key=value（如果存在则修改，否则追加）。
    返回是否已有该键。
    """
    found = False
    for row in rows:
        if row.get("type") == "kv" and row.get("key") == key:
            row["value"] = str(value)
            found = True
            break
    if not found:
        rows.append({
            "type": "kv",
            "text": f"{key}={value}",
            "key": key,
            "value": str(value),
        })
    return found


# ------------------------------------------------------------------
# 便捷：从默认值模板创建全新 server.properties
# ------------------------------------------------------------------

def create_default_properties_rows() -> List[dict]:
    """
    创建一份默认的 server.properties（基于官方默认值）。
    用于首次启动前用户想预先编辑的场景。
    """
    rows: List[dict] = []
    rows.append({"type": "comment", "text": "# Minecraft server properties（自动生成默认值）"})
    rows.append({"type": "comment", "text": "# 请根据需要修改以下配置"})
    rows.append({"type": "blank", "text": ""})

    # 按 key 分组输出
    sections = {
        "服务器基础": ["server-port", "server-ip", "motd", "max-players",
                      "online-mode", "allow-flight"],
        "游戏模式与难度": ["gamemode", "difficulty", "hardcore", "force-gamemode"],
        "世界设置": ["level-name", "level-seed", "level-type", "generate-structures",
                      "spawn-npcs", "spawn-animals", "spawn-monsters", "spawn-protection", "pvp"],
        "性能": ["view-distance", "simulation-distance", "max-tick-time",
                "sync-chunk-writes", "use-native-transport", "network-compression-threshold"],
        "玩家与权限": ["enable-command-block", "op-permission-level",
                    "function-permission-level", "prevent-proxy-connections",
                    "enforce-secure-profile", "white-list"],
        "其他": ["enable-status", "enable-query", "query.port", "enable-rcon",
                 "rcon.port", "rcon.password", "max-world-size", "player-idle-timeout",
                 "allow-nether", "rate-limit", "log-ips"],
    }

    for section_name, keys in sections.items():
        rows.append({"type": "comment", "text": f"# === {section_name} ==="})
        for key in keys:
            if key in PROPERTY_META:
                desc, prop_type, default_value, _ = PROPERTY_META[key]
                rows.append({"type": "comment", "text": f"# {desc}"})
                value_str = str(default_value).lower() if isinstance(default_value, bool) else str(default_value)
                rows.append({"type": "kv", "text": f"{key}={value_str}", "key": key, "value": value_str})
        rows.append({"type": "blank", "text": ""})

    return rows


# ------------------------------------------------------------------
# 便捷：从元数据获取属性描述
# ------------------------------------------------------------------

def get_meta(key: str) -> Optional[dict]:
    """
    获取某个 key 的元数据。
    返回 {description, type, default, options} 或 None。
    """
    if key not in PROPERTY_META:
        return None
    desc, ptype, default, options = PROPERTY_META[key]
    return {
        "description": desc,
        "type": ptype,
        "default": default,
        "options": options,
    }


def get_all_keys_with_meta() -> List[dict]:
    """
    返回所有已知 key 及其元数据列表。
    """
    result = []
    for key, (desc, ptype, default, options) in PROPERTY_META.items():
        result.append({
            "key": key,
            "description": desc,
            "type": ptype,
            "default": default,
            "options": options,
        })
    return result
