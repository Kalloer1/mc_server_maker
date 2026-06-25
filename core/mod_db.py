# mod_db.py —— 社区 ModID 环境数据库管理模块
# 职责：
#   1. 从远程 URL 下载最新的 mod_id.json，缓存到本地用户数据目录
#   2. 管理本地发现记录（local_discoveries.json），格式与在线数据库一致
#   3. 提供 get_mod_side(modid) 查询接口，按优先级返回 client/server/both/unknown
#   4. 支持强制刷新、导入本地 JSON、清空本地发现记录等操作
#
# 查询优先级（从高到低）：
#   在线数据库缓存 → 本地发现记录 → 待定（返回 unknown，由 mod_filter 进行 jar 内分析）

import json
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from utils.constants import (
    USER_DATA_DIR,
    CACHED_DB_PATH,
    LOCAL_DISCOVERIES_PATH,
    DEFAULT_MOD_DB_URL,
    FALLBACK_MOD_DB_URLS,
    BUILTIN_MOD_DB_PATH,
    LOCAL_UNKNOWN_MODS_PATH,
    UNKNOWN_MODS_REPO_URL,
)
from utils.downloader import Downloader


class ModDatabase:
    """
    ModID 环境数据库管理器。

    线程安全（写入本地发现记录时加锁），所有公开方法可在多线程环境调用。
    """

    def __init__(self, builtin_db_path: str = BUILTIN_MOD_DB_PATH):
        """
        初始化数据库管理器。

        参数：
            builtin_db_path: 内置数据库路径（相对于项目根目录，或绝对路径）
        """
        # 确保用户数据目录存在
        os.makedirs(os.path.join(USER_DATA_DIR, "db"), exist_ok=True)

        # 数据库（内存中的缓存）
        self._cache_db: Dict[str, str] = {}   # modid → client/server/both
        self._local_discoveries: Dict[str, str] = {}  # modid → client/server/both
        self._unknown_mods: Dict[str, dict] = {}  # modid → {modid, name, version, author, source}
        self._db_version: str = ""           # 在线数据库版本（若有）

        # 本地发现记录写入锁（防止多线程并发写入冲突）
        self._discovery_lock = threading.Lock()
        # 未知模组写入锁
        self._unknown_lock = threading.Lock()

        # 内置数据库路径（解析为绝对路径以便在打包后找到）
        self._builtin_db_path = Path(builtin_db_path)
        if not self._builtin_db_path.is_absolute():
            # 相对于项目根目录解析
            project_root = Path(__file__).resolve().parent.parent
            self._builtin_db_path = project_root / builtin_db_path

        # 统计信息
        self._online_count = 0
        self._local_count = 0
        self._loaded = False

    # ----------------------------------------------------------------
    # 初始化与加载
    # ----------------------------------------------------------------

    def initialize(self) -> bool:
        """
        初始化数据库：优先加载缓存，若无则加载内置。

        返回：
            True 表示成功加载数据，False 表示无任何可用数据
        """
        # 1. 尝试从缓存加载
        cached_loaded = self._load_from_file(CACHED_DB_PATH, into="cache")

        # 2. 若无缓存，尝试从内置数据库加载
        if not cached_loaded:
            builtin_loaded = self._load_from_file(
                str(self._builtin_db_path), into="cache"
            )
            if builtin_loaded:
                # 将内置数据也写入缓存，方便后续更新
                self._save_cache_db()
                self._online_count = len(self._cache_db)
        else:
            self._online_count = len(self._cache_db)

        # 3. 加载本地发现记录
        self._load_local_discoveries()

        self._loaded = True
        return len(self._cache_db) > 0 or len(self._local_discoveries) > 0

    def _load_from_file(self, filepath: str, into: str = "cache") -> bool:
        """
        从 JSON 文件加载数据库到内存。

        参数：
            filepath: JSON 文件路径
            into: "cache" 或 "local"，决定加载到哪个字典

        返回：
            True 表示成功加载，False 表示文件不存在或格式错误
        """
        path = Path(filepath)
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return False
                data = json.loads(content)
        except (json.JSONDecodeError, IOError):
            return False

        # 支持两种格式：
        #   格式 A：{"<modid>": "client/server/both", ...}  （纯字典）
        #   格式 B：{"version": "...", "mods": {"<modid>": "...", ...}}  （带版本）
        if isinstance(data, dict):
            # 检查是否是格式 B
            if "mods" in data and isinstance(data["mods"], dict):
                entries = data["mods"]
                if "version" in data:
                    self._db_version = str(data["version"])
            else:
                # 格式 A：纯字典，排除可能的 version 键
                entries = {}
                for k, v in data.items():
                    if k == "version":
                        self._db_version = str(v)
                    elif isinstance(v, str) and v.lower() in ("client", "server", "both"):
                        entries[k] = v.lower()
        else:
            return False

        # 过滤无效值
        valid = {"client", "server", "both"}
        filtered = {}
        for modid, side in entries.items():
            s = str(side).lower().strip()
            if s in valid:
                filtered[modid] = s

        if into == "cache":
            self._cache_db.update(filtered)
        else:
            self._local_discoveries.update(filtered)

        return len(filtered) > 0

    def _load_local_discoveries(self):
        """加载本地发现记录到内存"""
        loaded = self._load_from_file(LOCAL_DISCOVERIES_PATH, into="local")
        if loaded:
            self._local_count = len(self._local_discoveries)

    # ----------------------------------------------------------------
    # 查询接口
    # ----------------------------------------------------------------

    def get_mod_side(self, modid: str) -> str:
        """
        查询指定 modId 的环境类型。

        查询优先级：在线数据库缓存 → 本地发现记录 → unknown

        参数：
            modid: 模组 ID（字符串，大小写不敏感）

        返回：
            "client" / "server" / "both" / "unknown"
        """
        if not self._loaded:
            self.initialize()

        key = modid.lower().strip()

        # 1. 在线数据库缓存
        if key in self._cache_db:
            return self._cache_db[key]

        # 2. 本地发现记录
        if key in self._local_discoveries:
            return self._local_discoveries[key]

        # 3. 无法确定
        return "unknown"

    def add_local_discovery(self, modid: str, side: str):
        """
        将新发现的 modId 和 side 记录到本地发现文件。

        参数：
            modid: 模组 ID
            side: "client" / "server" / "both"
        """
        key = modid.lower().strip()
        side = side.lower().strip()

        if side not in ("client", "server", "both"):
            return

        # 更新内存
        self._local_discoveries[key] = side
        self._local_count = len(self._local_discoveries)

        # 加锁写入磁盘
        with self._discovery_lock:
            self._save_local_discoveries()

    def _save_cache_db(self):
        """将缓存数据库写入磁盘"""
        db_dir = os.path.dirname(CACHED_DB_PATH)
        os.makedirs(db_dir, exist_ok=True)
        try:
            with open(CACHED_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cache_db, f, ensure_ascii=False, indent=2)
        except IOError:
            pass  # 静默失败，下次启动时会从内置数据库恢复

    def _save_local_discoveries(self):
        """将本地发现记录写入磁盘（调用方必须持有锁）"""
        db_dir = os.path.dirname(LOCAL_DISCOVERIES_PATH)
        os.makedirs(db_dir, exist_ok=True)
        try:
            with open(LOCAL_DISCOVERIES_PATH, "w", encoding="utf-8") as f:
                json.dump(self._local_discoveries, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    # ----------------------------------------------------------------
    # 在线数据库刷新
    # ----------------------------------------------------------------

    def refresh_from_url(
        self,
        url: str = DEFAULT_MOD_DB_URL,
        progress_callback=None,
        status_callback=None,
    ) -> Tuple[bool, str]:
        """
        从指定 URL 下载最新的 mod_id.json 并替换本地缓存。

        参数：
            url: 数据库 URL
            progress_callback: 进度回调
            status_callback: 状态回调

        返回：
            (success: bool, message: str)
        """
        downloader = Downloader(
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

        # 构造下载 URL 列表（主 URL + 备用）
        url_list = [(f"在线数据库 ({url})", url)]
        for fallback_url in FALLBACK_MOD_DB_URLS:
            if fallback_url != url:
                url_list.append((f"备用 ({fallback_url})", fallback_url))

        try:
            source_name, content = downloader.download_small(
                url_list, timeout=20
            )
            # 解析 JSON
            data = json.loads(content.decode("utf-8"))

            # 提取有效条目（支持格式 A 和格式 B）
            if "mods" in data and isinstance(data["mods"], dict):
                entries = data["mods"]
                version = data.get("version", "")
            else:
                entries = {}
                version = ""
                for k, v in data.items():
                    if k == "version":
                        version = str(v)
                    elif isinstance(v, str):
                        v_lower = v.lower()
                        if v_lower in ("client", "server", "both"):
                            entries[k] = v_lower

            if not entries:
                return False, "在线数据库中没有有效条目。"

            # 更新内存和磁盘缓存
            self._cache_db.clear()
            self._cache_db.update({
                k: v.lower() for k, v in entries.items()
            })
            self._online_count = len(self._cache_db)
            self._db_version = str(version) if version else "未知"

            self._save_cache_db()

            return True, (
                f"数据库刷新成功！\n"
                f"  源: {source_name}\n"
                f"  条目数: {self._online_count}\n"
                f"  版本: {self._db_version}"
            )
        except Exception as e:
            return False, f"数据库刷新失败: {e}"

    # ----------------------------------------------------------------
    # 本地发现管理
    # ----------------------------------------------------------------

    def clear_local_discoveries(self) -> bool:
        """清空本地发现记录（内存 + 磁盘）"""
        self._local_discoveries.clear()
        self._local_count = 0

        with self._discovery_lock:
            try:
                if os.path.exists(LOCAL_DISCOVERIES_PATH):
                    os.remove(LOCAL_DISCOVERIES_PATH)
                return True
            except IOError:
                return False

    def import_local_json(
        self,
        filepath: str,
        merge: bool = True,
    ) -> Tuple[bool, str]:
        """
        从本地 JSON 文件导入数据库。

        参数：
            filepath: JSON 文件路径
            merge: True=合并去重（重复 key 保留现有值），False=完全替换

        返回：
            (success: bool, message: str)
        """
        path = Path(filepath)
        if not path.exists():
            return False, f"文件不存在: {filepath}"

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"JSON 格式错误: {e}"
        except IOError as e:
            return False, f"无法读取文件: {e}"

        # 提取有效条目
        if "mods" in data and isinstance(data["mods"], dict):
            entries = data["mods"]
        elif isinstance(data, dict):
            entries = {}
            for k, v in data.items():
                if k == "version":
                    pass  # 忽略版本字段
                elif isinstance(v, str) and v.lower() in ("client", "server", "both"):
                    entries[k] = v.lower()
        else:
            return False, "JSON 格式不正确：需要 dict 或包含 'mods' 键的对象。"

        if not entries:
            return False, "JSON 中没有找到有效的模组条目。"

        old_count = self._online_count

        if merge:
            # 合并模式：已存在的 key 保留现有值
            new_keys = 0
            for modid, side in entries.items():
                if modid not in self._cache_db:
                    self._cache_db[modid] = side
                    new_keys += 1
            self._online_count = len(self._cache_db)
            self._save_cache_db()
            return True, (
                f"合并导入成功！\n"
                f"  原有条目: {old_count}\n"
                f"  新增条目: {new_keys}\n"
                f"  总计: {self._online_count}"
            )
        else:
            # 替换模式
            self._cache_db.clear()
            self._cache_db.update(entries)
            self._online_count = len(self._cache_db)
            self._save_cache_db()
            return True, f"替换导入成功！条目数: {self._online_count}"

    # ----------------------------------------------------------------
    # 统计与信息接口
    # ----------------------------------------------------------------

    @property
    def online_count(self) -> int:
        """在线数据库缓存条目数"""
        return self._online_count

    @property
    def local_discovery_count(self) -> int:
        """本地发现记录数"""
        return self._local_count

    @property
    def db_version(self) -> str:
        """在线数据库版本号"""
        return self._db_version or "未知"

    def get_stats(self) -> Dict[str, object]:
        """返回数据库统计信息"""
        return {
            "online_count": self._online_count,
            "local_count": self._local_count,
            "db_version": self._db_version or "未知",
            "cache_path": CACHED_DB_PATH,
            "discovery_path": LOCAL_DISCOVERIES_PATH,
            "builtin_path": str(self._builtin_db_path),
        }

    def get_db_dir(self) -> str:
        """返回数据库文件所在目录"""
        return os.path.dirname(CACHED_DB_PATH)

    # ----------------------------------------------------------------
    # 未知模组管理
    # ----------------------------------------------------------------

    def add_unknown_mod(
        self,
        modid: str,
        mod_name: str = "",
        version: str = "",
        author: str = "",
        source: str = "jar_unknown",
    ):
        """
        记录一个未知模组到本地未知模组列表。

        参数：
            modid: 模组 ID
            mod_name: 模组文件名
            version: 模组版本
            author: 作者
            source: 来源标识（jar_unknown / db_unknown / blacklist）
        """
        key = modid.lower().strip()
        if not key:
            return

        with self._unknown_lock:
            if key not in self._unknown_mods:
                self._unknown_mods[key] = {
                    "modid": modid,
                    "name": mod_name,
                    "version": version,
                    "author": author,
                    "source": source,
                    "count": 1,
                }
            else:
                self._unknown_mods[key]["count"] += 1
            self._save_unknown_mods()

    def batch_add_unknown_mods(self, mod_list: List[dict]):
        """
        批量添加未知模组。

        参数：
            mod_list: 模组信息列表，每个元素为 dict，至少包含 modid 字段
        """
        with self._unknown_lock:
            for mod_info in mod_list:
                modid = mod_info.get("modid", "").lower().strip()
                if not modid:
                    continue
                if modid not in self._unknown_mods:
                    self._unknown_mods[modid] = {
                        "modid": mod_info.get("modid", ""),
                        "name": mod_info.get("name", ""),
                        "version": mod_info.get("version", ""),
                        "author": mod_info.get("author", ""),
                        "source": mod_info.get("source", "jar_unknown"),
                        "count": 1,
                    }
                else:
                    self._unknown_mods[modid]["count"] += 1
            self._save_unknown_mods()

    def get_unknown_mods(self) -> Dict[str, dict]:
        """获取所有未知模组"""
        return dict(self._unknown_mods)

    def get_unknown_mods_count(self) -> int:
        """获取未知模组数量"""
        return len(self._unknown_mods)

    def load_unknown_mods(self) -> bool:
        """从本地文件加载未知模组列表"""
        path = Path(LOCAL_UNKNOWN_MODS_PATH)
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._unknown_mods.clear()
                for k, v in data.items():
                    if isinstance(v, dict):
                        self._unknown_mods[k] = v
                return len(self._unknown_mods) > 0
        except (json.JSONDecodeError, IOError):
            pass
        return False

    def _save_unknown_mods(self):
        """保存未知模组到本地文件（调用方必须持有锁）"""
        db_dir = os.path.dirname(LOCAL_UNKNOWN_MODS_PATH)
        os.makedirs(db_dir, exist_ok=True)
        try:
            with open(LOCAL_UNKNOWN_MODS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._unknown_mods, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def export_unknown_mods(self, output_path: str) -> Tuple[bool, str]:
        """
        导出未知模组为 JSON 文件（方便用户手动提交 PR）。

        参数：
            output_path: 输出文件路径

        返回：
            (success, message)
        """
        if not self._unknown_mods:
            return False, "没有未知模组可以导出。"

        try:
            # 导出为简洁格式：modid → 建议类型(unknown) + 基本信息
            export_data = {}
            for modid, info in self._unknown_mods.items():
                export_data[modid] = {
                    "modid": info.get("modid", ""),
                    "name": info.get("name", ""),
                    "version": info.get("version", ""),
                    "author": info.get("author", ""),
                    "suggested_side": "unknown",
                }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            return True, f"已导出 {len(export_data)} 个未知模组到：\n{output_path}"
        except IOError as e:
            return False, f"导出失败: {e}"

    def clear_unknown_mods(self) -> bool:
        """清空未知模组列表（内存 + 磁盘）"""
        self._unknown_mods.clear()
        with self._unknown_lock:
            try:
                if os.path.exists(LOCAL_UNKNOWN_MODS_PATH):
                    os.remove(LOCAL_UNKNOWN_MODS_PATH)
                return True
            except IOError:
                return False

    def get_unknown_mods_repo_url(self) -> str:
        """获取未知模组提交仓库地址"""
        return UNKNOWN_MODS_REPO_URL