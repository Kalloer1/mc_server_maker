# constants.py —— 全局常量与配置项
# 所有硬编码的 URL、列表、映射表集中在此文件，方便统一维护

# ============================================================
# 应用元信息
# ============================================================
APP_NAME = "MC-Server-Maker"
APP_VERSION = "2.0.0"

# ============================================================
# 默认在线数据库 URL
# ============================================================
# 远程社区 ModID 环境数据库（可被用户修改）
DEFAULT_MOD_DB_URL = (
    "https://raw.githubusercontent.com/Kalloer1/mc_server_maker/main/data/mod_id.json"
)
# 备用 URL（当主 URL 不可用时尝试）
FALLBACK_MOD_DB_URLS = [
    "https://raw.githubusercontent.com/Kalloer1/mc_server_maker/main/data/mod_id.json",
    "https://cdn.jsdelivr.net/gh/Kalloer1/mc_server_maker@main/data/mod_id.json",
]

# ============================================================
# 内置数据库路径（相对于项目根目录）
# ============================================================
BUILTIN_MOD_DB_PATH = "data/mod_id.json"

# ============================================================
# 用户数据目录（Windows: %APPDATA%/MCServerMaker；Linux/Mac: ~/.MCServerMaker）
# ============================================================
import os
import sys

if sys.platform == "win32":
    USER_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MCServerMaker")
elif sys.platform == "darwin":
    USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MCServerMaker")
else:
    USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".MCServerMaker")

# 缓存数据库路径
CACHED_DB_PATH = os.path.join(USER_DATA_DIR, "db", "mod_id.json")
# 本地发现记录路径
LOCAL_DISCOVERIES_PATH = os.path.join(USER_DATA_DIR, "db", "local_discoveries.json")
# 用户配置文件路径
USER_CONFIG_PATH = os.path.join(USER_DATA_DIR, "config.json")

# ============================================================
# 下载源模板列表
# ============================================================
# 支持占位符：
#   {mc_version}  — 例如 "1.20.1"
#   {loader}      — 例如 "forge", "fabric", "neoforge"
#   {loader_ver}  — 加载器版本，例如 "47.2.0"
# 每个条目：{"name": str, "url": str, "enabled": bool}
DOWNLOAD_SOURCES = {
    "forge": [
        {
            "name": "Forge 官方 (安装器)",
            "url": "https://maven.minecraftforge.net/net/minecraftforge/forge/{mc_version}-{loader_ver}/forge-{mc_version}-{loader_ver}-installer.jar",
        },
        {
            "name": "BMCLAPI (Forge 安装器)",
            "url": "https://bmclapi2.bangbang93.com/maven/net/minecraftforge/forge/{mc_version}-{loader_ver}/forge-{mc_version}-{loader_ver}-installer.jar",
        },
    ],
    "fabric": [
        {
            "name": "Fabric 官方",
            "url": "https://meta.fabricmc.net/v2/versions/loader/{mc_version}/{loader_ver}/server/jar",
        },
        {
            "name": "BMCLAPI (Fabric)",
            "url": "https://bmclapi2.bangbang93.com/fabric-meta/v2/versions/loader/{mc_version}/{loader_ver}/server/jar",
        },
    ],
    "neoforge": [
        {
            "name": "NeoForge 官方 (安装器)",
            "url": "https://maven.neoforged.net/releases/net/neoforged/neoforge/{loader_ver}/neoforge-{loader_ver}-installer.jar",
        },
        {
            "name": "BMCLAPI (NeoForge 安装器)",
            "url": "https://bmclapi2.bangbang93.com/maven/net/neoforged/neoforge/{loader_ver}/neoforge-{loader_ver}-installer.jar",
        },
    ],
    "vanilla": [
        {
            "name": "Mojang 官方",
            "url": "https://piston-data.mojang.com/v1/objects/{vanilla_hash}/server.jar",
        },
        {
            "name": "BMCLAPI (原版)",
            "url": "https://bmclapi2.bangbang93.com/version/{mc_version}/server",
        },
    ],
}

# 原版服务端哈希需要从 version_manifest.json 获取
VANILLA_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

# 连接测试用小文件（BMCLAPI 的 favicon，体积极小）
TEST_CONNECTION_URLS = [
    "https://bmclapi2.bangbang93.com/favicon.ico",
    "https://www.minecraft.net/favicon.ico",
]

# ============================================================
# 下载器默认参数
# ============================================================
DOWNLOAD_TIMEOUT = 30       # 单个请求超时（秒）
DOWNLOAD_RETRIES = 2        # 每个源的额外重试次数
DOWNLOAD_CHUNK_SIZE = 8192  # 流式下载块大小（字节）

# ============================================================
# 模组文件名模糊匹配黑名单
# ============================================================
# 当所有方法都无法确定模组环境时，用这些关键字辅助判断
# 匹配到任一关键字的模组将被判定为 CLIENT_ONLY
MOD_BLACKLIST_KEYWORDS = [
    # 知名客户端模组特征关键字
    "sodium",                # 渲染优化
    "iris",                  # 光影
    "optifine",              # OptiFine
    "optifabric",            # OptiFine + Fabric 兼容
    "lambdynamiclights",     # 动态光源
    "dynamiclights",         # 动态光源变体
    "shaders",               # 光影相关
    "replaymod",             # 回放模组
    "camerautils",           # 摄像机工具
    "freelook",              # 自由视角
    "zoom",                  # 缩放
    "wi_zoom",               # WI Zoom
    "ok_zoomer",             # OK Zoomer
    "jade-addon",            # Jade 插件可能是客户端的
    "appleskin",             # AppleSkin
    "betterfps",             # BetterFPS
    "betterfpsdist",         # BetterFPS Distance
    "betterbiomeblend",      # 生物群系过渡
    "betterclouds",          # 云优化
    "betterfoliage",         # 植被
    "entityculling",         # 实体剔除
    "entity_texture_features",  # ETF
    "entity_model_features",    # EMF
    "continuity",            # 连接纹理
    "connectivity",          # 连接纹理 Fabric
    "indium",                # Sodium 渲染 API 补充
    "animatica",             # 动画纹理
    "citicorp",              # CIT/CIT Resewn
    "colormatic",            # 颜色
    "customizableplayer",    # 自定义玩家模型
    "3dskinlayers",          # 3D 皮肤层
    "emotecraft",            # 表情
    "ears",                  # 耳朵皮肤
    "firstperson",           # 第一人称模型
    "notenoughanimations",   # 动画增强
    "physicsmod",            # 物理模组客户端
    "presencefootsteps",     # 脚步声
    "dynmus",                # 动态音乐
    "ambientsounds",         # 环境音效
    "extrasounds",           # 额外音效
    "sound_physics",         # 声音物理
    "soundfilters",          # 音效滤镜
    "inventoryhud",          # 背包 HUD
    "minimap",               # 小地图
    "journeymap",            # JourneyMap
    "xaerominimap",          # Xaero 小地图
    "xaero_worldmap",        # Xaero 世界地图
    "maptool",               # 地图工具
    "mousetweaks",           # 鼠标手势
    "mousewheelie",          # 鼠标滚轮
    "itemscroller",          # 物品滚动
    "litematica",            # 投影
    "minihud",               # MiniHUD
    "tweakeroo",             # Tweakeroo
    "inventoryprofiles",     # 背包整理
    "ipn",                   # Inventory Profiles Next
    "invhud",                # 背包 HUD 简写
    "roughlyenoughitems",    # REI (Fabric)
    "jei",                   # JEI (Forge)
    "emi",                   # EMI
    "rei",                   # REI 简写
    "nei",                   # NEI
    "craftguide",            # CraftGuide
    "craftpresence",         # Discord Rich Presence
    "discordrpc",            # Discord RPC
    "tip_the_scales",        # 字体缩放
    "smoothboot",            # 平滑启动
    "smoothscrolling",       # 平滑滚动
    "tooltipfix",            # 工具提示修复
    "tooltip_customizer",    # 工具提示定制
    "keybindings",           # 按键设置增强
    "keymod",                # 按键模组
    "controlling",           # Controlling
    "textrues",              # 字体/文本
    "loadingbackgrounds",    # 加载背景
    "panorama",              # 全景图
    "splashscreen",          # 启动画面
    "titlechanger",          # 标题修改
    "window_title_changer",  # 窗口标题
    "borderlesswindow",      # 无边框窗口
    "blur",                  # 模糊效果
    "fallingleaves",         # 落叶
    "particulardamage",      # 粒子伤害
    "effectsleft",           # 效果剩余
    "chat_heads",            # 聊天头像
    "chatanimation",         # 聊天动画
    "compactchat",           # 紧凑聊天
    "tabbychat",             # TabbyChat
    "chattabs",              # 聊天标签
    "fpsdisplay",            # FPS显示
    "fps_monitor",           # FPS监控
    "fpsplus",               # FPS+
    "fpsreducer",            # FPS Reducer
    "torohealth",            # ToroHealth
    "healthindicator",       # 血量显示
    "damageindicator",       # 伤害显示
    "configured",            # Configured（配置界面）
    "catalogue",             # Catalogue（模组菜单）
    "modmenu",               # Mod Menu (Fabric)
    "menulens",              # Menu Lens
    "custommainmenu",        # 自定义主菜单
    "fancymenu",             # FancyMenu
    "drippyloading",         # Drippy Loading
    "respackopts",           # 资源包选项
    "yacl",                  # YetAnotherConfigLib
    "cloth_config",          # Cloth Config
    "capes",                 # 披风
    "cosmetica",             # Cosmetica
    "morechathistory",       # 聊天历史
    "chatpatches",           # 聊天补丁
    "farsight",              # FarSight
    "distanthorizons",       # Distant Horizons
    "bobby",                 # Bobby（视距缓存）
    "nvidium",               # Nvidium（NVIDIA 渲染）
    "vulkanmod",             # VulkanMod
    "nochatreports",         # 禁止举报
    "guifollow",             # GUI跟随
    "inventorysorter",       # 背包排序
    "itemframeshader",       # 物品框着色器
    "shaderoptions",         # 着色器选项
    "shader_toggle",         # 着色器切换
    "showmeyourskin",        # SMYS
    "waveycapes",            # Wavey Capes
]

# ============================================================
# 必须保留的文件夹（从客户端目录复制到服务端）
# ============================================================
PRESERVED_FOLDERS = [
    "config",
    "defaultconfigs",
    "kubejs",
    "scripts",
    "structures",
    "mods",
    "global_packs",
    "worldshape",
    "datapacks",
]

# ============================================================
# 明确排除的纯客户端文件夹（不会被复制到服务端）
# ============================================================
CLIENT_ONLY_FOLDERS = [
    "shaderpacks",
    "resourcepacks",
    "screenshots",
    "logs",
    "crash-reports",
    "crash_reports",
    "saves",
    "server-resource-packs",
    "blueprints",
    "dumps",
    "patchouli_books",
    "backups",
    "downloads",
    "emotes",
    "gist",
    "irisUpdateInfo",
    "local",
    "notifications",
    "replay_recordings",
    "replay_videos",
    "schematics",
    "videos",
    "XaeroWaypoints",
    "xaerowaypoints",
    "betterloading",
    "cached_images",
    "fancymenu_data",
    "fancymenu_dlc",
    "mod_data",
    "Nvidium",
]

# ============================================================
# Server.properties 默认值
# ============================================================
DEFAULT_SERVER_PROPERTIES = {
    "server-port": "25565",
    "online-mode": "true",
    "allow-flight": "false",
    "gamemode": "survival",
    "difficulty": "easy",
    "max-players": "20",
    "motd": "A Minecraft Server",
    "server-name": "Unknown Server",
    "enable-command-block": "false",
    "spawn-protection": "16",
    "view-distance": "10",
    "simulation-distance": "10",
    "max-tick-time": "60000",
    "allow-nether": "true",
    "spawn-npcs": "true",
    "spawn-animals": "true",
    "spawn-monsters": "true",
    "pvp": "true",
    "force-gamemode": "false",
    "hardcore": "false",
    "enable-status": "true",
    "enable-query": "false",
    "generate-structures": "true",
    "max-build-height": "256",
    "network-compression-threshold": "256",
    "max-world-size": "29999984",
    "level-name": "world",
    "level-type": "minecraft\\:normal",
    "level-seed": "",
    "enforce-secure-profile": "true",
    "prevent-proxy-connections": "false",
    "use-native-transport": "true",
}

# ============================================================
# 内存分配选项
# ============================================================
MEMORY_OPTIONS = ["1G", "2G", "4G", "6G", "8G", "12G", "16G", "自定义"]

# ============================================================
# 游戏模式选项
# ============================================================
GAMEMODE_OPTIONS = ["survival", "creative", "adventure", "spectator"]

# ============================================================
# 难度选项
# ============================================================
DIFFICULTY_OPTIONS = ["peaceful", "easy", "normal", "hard"]

# ============================================================
# MOTD 颜色代码映射表
# ============================================================
# § 后跟一个字符，映射到对应的 HTML 颜色
MOTD_COLOR_MAP = {
    "0": "#000000",  # 黑色
    "1": "#0000AA",  # 深蓝色
    "2": "#00AA00",  # 深绿色
    "3": "#00AAAA",  # 深水蓝色
    "4": "#AA0000",  # 深红色
    "5": "#AA00AA",  # 深紫色
    "6": "#FFAA00",  # 金色
    "7": "#AAAAAA",  # 灰色
    "8": "#555555",  # 深灰色
    "9": "#5555FF",  # 蓝色
    "a": "#55FF55",  # 绿色
    "b": "#55FFFF",  # 水蓝色
    "c": "#FF5555",  # 红色
    "d": "#FF55FF",  # 品红色
    "e": "#FFFF55",  # 黄色
    "f": "#FFFFFF",  # 白色
}

# MOTD 格式代码映射表（§l, §o, §n, §m, §k, §r）
MOTD_FORMAT_CODES = {
    "l": "bold",       # 粗体
    "o": "italic",     # 斜体
    "n": "underline",  # 下划线
    "m": "strikethrough",  # 删除线
    "k": "obfuscated",  # 乱码（随机字符）
    "r": "reset",       # 重置所有格式
}

# ============================================================
# 启动脚本模板
# ============================================================
# Windows 启动脚本 (Forge / NeoForge / Fabric)
# 注意：直接运行服务端核心文件，无需安装器
START_BAT_FORGE_TEMPLATE = """@echo off
title Minecraft {loader_name} Server
java @user_jvm_args.txt -jar {core_jar} nogui
pause
"""

START_BAT_NEOFORGE_TEMPLATE = """@echo off
title Minecraft NeoForge Server
java @user_jvm_args.txt -jar {core_jar} nogui
pause
"""

START_BAT_FABRIC_TEMPLATE = """@echo off
title Minecraft Fabric Server
java @user_jvm_args.txt -jar {core_jar} nogui
pause
"""

START_BAT_VANILLA_TEMPLATE = """@echo off
title Minecraft Vanilla Server
java @user_jvm_args.txt -jar {core_jar} nogui
pause
"""

# Linux/Mac 启动脚本 (Forge / NeoForge / Fabric)
START_SH_FORGE_TEMPLATE = """#!/bin/sh
java @user_jvm_args.txt -jar {core_jar} nogui
echo "Minecraft 服务器已停止。"
"""

START_SH_NEOFORGE_TEMPLATE = """#!/bin/sh
java @user_jvm_args.txt -jar {core_jar} nogui
echo "Minecraft 服务器已停止。"
"""

START_SH_FABRIC_TEMPLATE = """#!/bin/sh
java @user_jvm_args.txt -jar {core_jar} nogui
echo "Minecraft 服务器已停止。"
"""

START_SH_VANILLA_TEMPLATE = """#!/bin/sh
java @user_jvm_args.txt -jar {core_jar} nogui
echo "Minecraft 服务器已停止。"
"""

# user_jvm_args.txt 默认模板
USER_JVM_ARGS_TEMPLATE = """# 服务器 JVM 参数（可手动编辑）
# 内存分配（由 MCServerMaker 生成）
-Xms{min_mem}
-Xmx{max_mem}
"""

# ============================================================
# EULA 模板
# ============================================================
EULA_CONTENT = """# 通过修改下面的设置来表明您是否接受 Minecraft EULA
# （https://account.mojang.com/documents/minecraft_eula）。
# 此值还必须设为 true，服务器启动脚本才能工作。
# 2026年06月21日 星期日 20时41分18秒 CST
eula=true
"""

# ============================================================
# 服务器图标限制
# ============================================================
SERVER_ICON_SIZE = 64       # 像素（宽高均为 64）
SERVER_ICON_FORMAT = "PNG"
SERVER_ICON_FILENAME = "server-icon.png"