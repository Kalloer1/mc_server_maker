# MC Server Maker - 计划：UI 优化、功能增强

## 摘要
对 MC Server Maker 的 UI 进行多项改进：增强模组列表（筛选、版本号）、删除工具按钮、添加 Java 版本检测与选择、修复安装器运行、配置文件增加服务器图标和 MOTD。

---

## 一、当前状态分析

### 1.1 模组列表（ui/main_window.py L333-462）
- 表格 4 列：`✓` / `文件名` / `ModID` / `类型`
- 无筛选功能，无法按类型过滤
- 无版本号列（可从 jar 内 `[[mods]].version` 字段提取）
- 有「💾 保存模组信息」按钮需要删除

### 1.2 工具按钮（ui/main_window.py L468-492）
- `_build_tool_buttons` 方法包含三个按钮：
  - `📋 版本管理` → 调用 `_on_manage_versions` → 打开 ModIDDialog（需删除）
  - `📦 离线模式` → 调用 `_on_select_offline_core`（需删除）
  - `🖼️ 服务器图标` → 调用 `_on_select_icon`（需删除，因为图标功能会移到配置文件区）
- `__init__` 中 `_server_icon_pixmap` 相关逻辑（需删除/重构）

### 1.3 操作区（ui/main_window.py L496-591）
- `_build_action_buttons` 包含：输出目录、内存选择、分离按钮、运行安装器、启动/停止服务端、编辑配置等
- 无 Java 版本选择

### 1.4 mod_filter.py 分析结果
- `mod_details` 字典目前只包含 `modid` 和 `side`
- `[[mods]].version`（版本号）和 `[[mods]].authors`（作者）字段在 toml 中存在
- 未知类型（`side == "unknown"`）默认保留到服务端，需改为提示用户自行判断

### 1.5 server_runner.py Java 检测
- `check_java_available()` 已实现：返回 (bool, version_string)
- 无多 Java 版本管理

---

## 二、详细实施计划

### 2.1 模组列表增强

#### 文件: `core/mod_filter.py`

**修改 `_filter_mods` 的 `mod_details` 结构：**
```python
mod_details[mod_path] = {
    "modid": modid or "(未识别)",
    "side": side,          # "client" / "server" / "both" / "unknown"
    "version": version,     # 新增：版本号
    "author": author,       # 新增：作者
}
```

**新增函数 `_extract_full_mod_info(jar_path)`：**
- 读取 `META-INF/neoforge.mods.toml` → 提取 `modId`、`version`、`authors`
- 读取 `META-INF/mods.toml` → 提取 `modId`、`version`、`authors`
- 读取 `fabric.mod.json` → 提取 `id`、`version`（fabric 的 version 字段在 loader.version）
- 返回 `{"modid", "version", "author", "side"}`

**修改 `filter_mods` 函数：**
- 循环中对每个 jar 调用 `_extract_full_mod_info`
- 未知类型（`side == "unknown"`）时，日志提示用户自行判断是服务端还是客户端模组

#### 文件: `ui/main_window.py`

**修改 `_build_mods_list_section`（L333）：**
- 表格改为 5 列：`✓` / `文件名` / `ModID` / `版本` / `类型`
- 列宽调整：文件名(拉伸)、ModID(130)、版本(100)、类型(60)
- 新增筛选区（top_row 右侧）：
  - `QComboBox`：全部 / 客户端 / 服务端 / 双端 / 未知
  - 筛选时隐藏对应行
- 删除「💾 保存模组信息」按钮
- 「恢复默认」按钮功能不变

**修改 `_populate_mods_list`（L695）：**
- 填充时同时填入版本号列（第 4 列）

**修改 `_on_mod_analysis_finished`（L767）：**
- mod_details 包含 version 和 author
- 填入第 4 列（版本号）
- 未知类型行：添加黄色背景提示

**新增 `_filter_mods_table(filter_type: str)`：**
- 根据筛选类型（all/client/server/both/unknown）隐藏/显示对应行
- 连接筛选 ComboBox 的 `currentIndexChanged` 信号

**删除方法：**
- `_save_mod_info`（L420）— 整体删除

---

### 2.2 删除工具按钮区域

#### 文件: `ui/main_window.py`

**删除 `_build_tool_buttons` 方法（L468-492）：**
- 整个 `_build_tool_buttons` 调用链全部删除
- `__init__` 中删除 `self._build_tool_buttons(layout)` 调用

**删除状态变量：**
- `self._server_icon_pixmap: QPixmap | None = None`（L63 附近）

**删除相关方法：**
- `_on_manage_versions`（L1420）
- `_on_select_offline_core`（L1428）
- `_on_select_icon`（L1437）
- `_set_server_icon` 及其调用

---

### 2.3 Java 版本检测与选择

#### 文件: `core/java_manager.py`（新增）

**功能：**
- `find_all_java_installations()` — 扫描系统中所有 Java 安装：
  - Windows: `C:\Program Files\Java\`, `C:\Program Files (x86)\Java\`
  - 从 PATH 环境变量中 `where java` 获取
  - 从注册表读取（`HKLM\SOFTWARE\JavaSoft\Java Development Kit`）
  - 提取每个 java.exe 的版本信息（`java -version` 解析）
- `get_java_version(java_path)` — 获取指定 java 的版本号
- `check_java_for_mc_version(mc_version)` — 判断该 Java 是否支持指定 MC 版本
  - MC 1.17+ 需要 Java 16+
  - MC 1.18+ 需要 Java 17+
  - MC 1.20.5+ 建议 Java 21（NeoForge 推荐）
  - 返回 (bool, reason)
- `format_java_choice(javainfo)` — 格式化显示字符串 `"Java 21 (21.0.3) - C:\Program Files\Java\jdk-21\bin\java.exe"`

**Java 需求参考：**
| MC 版本 | 最低 Java | 推荐 Java |
|---------|-----------|-----------|
| 1.12.2 | Java 8 | Java 8/11 |
| 1.16.5 | Java 8 | Java 11/16 |
| 1.18+ | Java 17 | Java 17/21 |
| 1.20.4+ | Java 17 | Java 21 |
| 1.21+ | Java 21 | Java 21 |

#### 文件: `ui/main_window.py`

**在 `_build_action_buttons` 的 out_row 中间添加 Java 选择：**
```python
# 在"输出目录"行或"内存"选择器旁边添加
self._combo_java = QComboBox()
self._combo_java.setToolTip("选择运行服务端使用的 Java 版本")
self._combo_java.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
# 填充 Java 列表
self._refresh_java_list()
# 添加分隔符和手动输入路径选项
layout.addWidget(QLabel("Java:"))
layout.addWidget(self._combo_java)
```

**新增方法 `_refresh_java_list()`：**
- 调用 `find_all_java_installations()`
- 填充 `_combo_java`，每个选项存储 (java_path, version)
- 检测当前 MC 版本兼容性，不兼容的显示警告

**新增方法 `_on_check_java()`：**
- 调用 `check_java_available()`
- 显示当前 Java 版本信息弹窗
- 提示用户确认

**在 `_collect_generation_config` 中：**
- 新增返回 `java_path`（从 `_combo_java` 读取选中项的 java 路径）
- 如果 MC 版本需要更高 Java 版本但未选择，弹窗警告

---

### 2.4 配置文件区增加服务器图标和 MOTD

#### 文件: `ui/main_window.py`

**在 `_build_config_folders_section` 后新增 `_build_server_profile_section`：**
```python
def _build_server_profile_section(self, parent_layout: QVBoxLayout):
    # 服务器图标 + MOTD 配置区
    group = QGroupBox("🖥️ 服务器配置（图标/MOTD）")
    layout = QVBoxLayout(group)

    # 第一行：图标选择
    icon_row = QHBoxLayout()
    btn_icon = QPushButton("🖼️ 选择服务器图标（64×64 PNG）")
    btn_icon.clicked.connect(self._on_select_icon)
    icon_row.addWidget(btn_icon)
    self._icon_preview = QLabel("无图标")
    self._icon_preview.setFixedSize(64, 64)
    self._icon_preview.setStyleSheet("border: 1px solid #555; background: #333;")
    self._icon_preview.setAlignment(Qt.AlignCenter)
    icon_row.addWidget(self._icon_preview)
    icon_row.addStretch()
    layout.addLayout(icon_row)

    # 第二行：MOTD 输入
    motd_row = QHBoxLayout()
    motd_row.addWidget(QLabel("MOTD（服务器名称）:"))
    self._edit_motd = QLineEdit()
    self._edit_motd.setPlaceholderText("A Minecraft Server")
    self._edit_motd.setMaxLength(59)  # MC 限制
    motd_row.addWidget(self._edit_motd, 1)
    layout.addLayout(motd_row)

    # 第三行：MOTD 预览
    preview_label = QLabel("预览:")
    preview_label.setStyleSheet("color: #888; font-size: 12px;")
    layout.addWidget(preview_label)
    self._motd_preview = QLabel("  A Minecraft Server")
    self._motd_preview.setStyleSheet(
        "background: #1a1a1a; color: white; padding: 8px; "
        "border-radius: 4px; font-family: 'Arial'; font-size: 14px;"
    )
    self._motd_preview.setMinimumHeight(40)
    self._motd_preview.setAlignment(Qt.AlignCenter)
    layout.addWidget(self._motd_preview)

    # MOTD 实时预览
    self._edit_motd.textChanged.connect(self._on_motd_changed)

    parent_layout.addWidget(group)
```

**新增方法 `_on_select_icon`：**
- 打开文件选择对话框（`*.png`）
- 验证 64×64 像素
- 显示预览图到 `_icon_preview`
- 存储 `self._server_icon_pixmap`

**新增方法 `_on_motd_changed(text)`：**
- 更新 `_motd_preview` 显示

**修改 `_collect_generation_config`：**
- 从 `self._edit_motd.text()` 读取 motd
- 从 `self._server_icon_pixmap` 读取图标（不为 None 时传入）

---

### 2.5 确认安装器命令

**问题根因：** Forge/NeoForge 安装器命令是 `java -jar installer.jar --installServer`

**`core/server_runner.py` 中的 `run_installer` 函数（L53）：**
- 已正确实现：`cmd = ["java", "-jar", str(installer_jar), "--installServer"]`
- 无需修改

**唯一潜在问题：** `java` 命令需要使用正确的 Java 版本（而非系统默认）。在 `_on_run_installer` 中调用时需要支持指定 Java 路径。

**修改 `server_runner.py` 的 `run_installer` 和 `ServerProcess`：**
- 新增参数 `java_path: Optional[str] = None`
- 如果提供了 `java_path`，使用 `java_path` 而非 `java`

**修改 `ui/main_window.py` 的 `_on_run_installer`：**
- 从 `_combo_java` 获取选中的 java 路径
- 传递给 `InstallerWorker` 和 `ServerRunWorker`

---

## 三、文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `core/mod_filter.py` | 提取 version/author 字段，增强 mod_details |
| 修改 | `ui/main_window.py` | 筛选、版本号列、删除工具按钮、Java 选择、服务器配置区 |
| 修改 | `ui/worker.py` | `InstallerWorker`/`ServerRunWorker` 支持 java_path 参数 |
| 修改 | `core/server_runner.py` | `run_installer`/`ServerProcess` 支持 java_path |
| 新增 | `core/java_manager.py` | Java 版本扫描、兼容性检测 |

---

## 四、实施顺序

1. ✅ `core/java_manager.py`（新增，独立功能）
2. ✅ `core/mod_filter.py`（新增 version/author 提取）
3. ✅ `ui/main_window.py` — 删除工具按钮区域
4. ✅ `ui/main_window.py` — 模组列表筛选 + 版本号
5. ✅ `ui/main_window.py` — Java 版本选择
6. ✅ `ui/main_window.py` — 服务器配置区（图标+MOTD）
7. ✅ `core/server_runner.py` — java_path 参数支持
8. ✅ `ui/worker.py` — Worker 支持 java_path
9. ✅ 测试编译检查

---

## 五、验证步骤

1. 运行 `python -m py_compile` 检查所有文件语法
2. 运行 `python -c "import ..."` 检查所有模块导入
3. 启动程序，测试：
   - 选择一个包含模组的目录，验证模组列表显示版本号
   - 使用筛选下拉框过滤模组
   - 检查"保存模组信息"按钮是否已删除
   - 检查工具按钮区是否已删除
   - 检查 Java 版本选择是否显示
   - 选择服务器图标验证预览
   - 修改 MOTD 验证实时预览
