# main_window.py —— 主窗口 UI
# 布局：
#   1. 选择来源     ——  游戏目录 + 检测 + MC版本/加载器覆盖
#   2. 配置文件夹   ——  可折叠列表 + 手动添加 + 保存默认
#   3. 模组列表     ——  可折叠表格 + 保存模组信息
#   4. 工具按钮     ——  版本管理 / 离线模式
#   5. 操作区       ——  输出目录 + 分离服务器基础文件 / 停止
#   6. 进度与日志

import os
import sys
import json
import datetime
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QTextEdit, QPushButton, QProgressBar,
    QComboBox, QCheckBox, QFileDialog, QMessageBox, QScrollArea,
    QFrame, QRadioButton, QSizePolicy, QSpacerItem, QGridLayout,
    QSplitter, QButtonGroup, QDialog, QDialogButtonBox, QListWidget,
    QListWidgetItem, QAbstractItemView, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog,
)
from PySide6.QtCore import Qt, QTimer, QEvent, QObject
from PySide6.QtGui import QFont, QPixmap, QIcon, QAction

from core.scanner import scan_game_directory
from core.mod_db import ModDatabase
from utils.motd_colors import parse_motd_to_html, convert_motd_to_server_properties
from ui.worker import ScanWorker, GenerateWorker, ModFilterWorker
from utils.constants import SERVER_ICON_SIZE, SERVER_ICON_FILENAME


# 加载全局样式表
def load_stylesheet(app_or_widget):
    """加载全局样式表"""
    qss_path = Path(__file__).parent.parent / "theme" / "theme.qss"
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            app_or_widget.setStyleSheet(f.read())
    except Exception:
        pass  # 样式文件不存在时使用默认样式


def log_timestamp() -> str:
    return datetime.datetime.now().strftime("[%H:%M:%S]")


class WheelBlockFilter(QObject):
    """事件过滤器：阻止 QComboBox 的鼠标滚轮事件"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return super().eventFilter(obj, event)


class MainWindow(QMainWindow):
    """MC Server Maker 主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MC Server Maker v2")
        self.resize(900, 900)  # 增加窗口高度以容纳更大预览
        self.setMinimumWidth(800)

        self._game_dir: Path | None = None
        self._scan_result: dict | None = None
        self._mod_db = ModDatabase()
        self._current_worker = None
        self._last_output_dir: Path | None = None
        self._server_icon_pixmap: QPixmap | None = None
        self._config_data: dict = {}
        self._wheel_filter = WheelBlockFilter(self)
        self._mod_analysis_result: dict | None = None

        self._build_ui()
        self._load_user_config()
        self._init_log()

    # ═══════════════════════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)  # 统一间距 12px

        self._build_source_section(layout)
        self._build_config_folders_section(layout)
        self._build_mods_list_section(layout)
        self._build_server_profile_section(layout)
        self._build_action_buttons(layout)
        self._build_progress_log(layout)

        layout.addStretch()
        scroll.setWidget(central)
        self.setCentralWidget(scroll)
        self._install_wheel_filter(central)

    # ───────────────────────────────────────────────────────────────────
    # 1. 选择来源
    # ───────────────────────────────────────────────────────────────────

    def _build_source_section(self, parent_layout: QVBoxLayout):
        group = QGroupBox("📁 选择来源（游戏目录）")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._game_dir_label = QLabel("尚未选择游戏目录")
        self._game_dir_label.setObjectName("gameDirLabel")
        self._game_dir_label.setWordWrap(True)
        self._game_dir_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(self._game_dir_label, 1)

        btn = QPushButton("📂 浏览文件夹...")
        btn.setToolTip("选择一个已安装的 Minecraft 版本目录")
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.clicked.connect(self._on_browse_folder)
        row.addWidget(btn)

        self._btn_detect = QPushButton("🔍 检测")
        self._btn_detect.setObjectName("btn_detect")
        self._btn_detect.setToolTip("检测整合包名称、MC 版本、加载器类型、模组数量")
        self._btn_detect.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btn_detect.setEnabled(False)
        self._btn_detect.clicked.connect(self._on_detect)
        row.addWidget(self._btn_detect)
        layout.addLayout(row)

        tags = QHBoxLayout()
        self._info_mc_version = QLabel("MC 版本: —")
        self._info_loader = QLabel("加载器: —")
        self._info_mod_count = QLabel("模组: —")
        for w in (self._info_mc_version, self._info_loader, self._info_mod_count):
            w.setObjectName("infoTag")
            tags.addWidget(w)
        tags.addStretch()
        layout.addLayout(tags)

        self._config_folders_label = QLabel("配置文件夹: —")
        self._config_folders_label.setObjectName("gameDirLabel")
        self._config_folders_label.setWordWrap(True)
        layout.addWidget(self._config_folders_label)

        override_row = QHBoxLayout()
        override_row.addWidget(QLabel("MC版本:"))
        self._edit_mc_version = QLineEdit()
        self._edit_mc_version.setToolTip("自动检测的 MC 版本，可手动修改（检测成功后自动填充）")
        self._edit_mc_version.setPlaceholderText("如 1.21.1")
        self._edit_mc_version.setEnabled(False)
        override_row.addWidget(self._edit_mc_version, 1)

        override_row.addWidget(QLabel("加载器:"))
        self._combo_loader_override = QComboBox()
        self._combo_loader_override.setObjectName("loader_combo")
        self._combo_loader_override.setToolTip("自动检测的加载器类型，可手动修改")
        self._combo_loader_override.addItems(["vanilla", "forge", "fabric", "neoforge"])
        self._combo_loader_override.setEnabled(False)
        self._combo_loader_override.installEventFilter(self._wheel_filter)
        override_row.addWidget(self._combo_loader_override, 1)

        override_row.addWidget(QLabel("加载器版本:"))
        self._edit_loader_version = QLineEdit()
        self._edit_loader_version.setToolTip("自动检测的加载器版本，可手动修改")
        self._edit_loader_version.setPlaceholderText("如 21.1.221")
        self._edit_loader_version.setEnabled(False)
        override_row.addWidget(self._edit_loader_version, 1)
        layout.addLayout(override_row)

        layout.addWidget(QLabel("请选择 .minecraft/versions/ 下的具体版本文件夹"))
        parent_layout.addWidget(group)

    # ───────────────────────────────────────────────────────────────────
    # 2. 配置文件夹（可折叠 + 保存默认）
    # ───────────────────────────────────────────────────────────────────

    def _build_config_folders_section(self, parent_layout: QVBoxLayout):
        self._config_folders_group = QGroupBox("📂 服务端要复制的文件夹（手动勾选）")
        self._config_folders_group.setVisible(False)
        layout = QVBoxLayout(self._config_folders_group)

        collapse_row = QHBoxLayout()
        self._config_folders_collapse_btn = QPushButton("▲ 折叠")
        self._config_folders_collapse_btn.setToolTip("点击折叠/展开配置文件夹列表")
        self._config_folders_collapse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._config_folders_collapse_btn.clicked.connect(self._toggle_config_folders_collapse)
        collapse_row.addWidget(self._config_folders_collapse_btn)
        collapse_row.addStretch()
        layout.addLayout(collapse_row)

        self._config_folders_content = QWidget()
        content_layout = QVBoxLayout(self._config_folders_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._config_folders_list = QListWidget()
        self._config_folders_list.setToolTip("勾选要复制到服务端的文件夹（可点击选择后按移除")
        self._config_folders_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._config_folders_list.setMaximumHeight(150)
        content_layout.addWidget(self._config_folders_list)

        btn_row = QHBoxLayout()
        btn_select_all = QPushButton("全选")
        btn_select_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_select_all.clicked.connect(lambda: self._toggle_config_folders_check(True))
        btn_row.addWidget(btn_select_all)
        btn_deselect_all = QPushButton("取消全选")
        btn_deselect_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_deselect_all.clicked.connect(lambda: self._toggle_config_folders_check(False))
        btn_row.addWidget(btn_deselect_all)
        btn_save_default = QPushButton("💾 保存为默认")
        btn_save_default.setToolTip("将当前勾选的文件夹列表保存为默认配置")
        btn_save_default.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_save_default.clicked.connect(self._save_default_folders)
        btn_row.addWidget(btn_save_default)
        btn_add = QPushButton("➕ 手动添加")
        btn_add.setToolTip("手动添加游戏目录下的其他文件夹")
        btn_add.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_add.clicked.connect(self._on_add_custom_folder)
        btn_row.addWidget(btn_add)
        btn_remove = QPushButton("➖ 移除")
        btn_remove.setToolTip("从列表中移除选中的文件夹（不删除源目录）")
        btn_remove.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_remove.clicked.connect(self._on_remove_selected_folder)
        btn_row.addWidget(btn_remove)
        btn_add_text = QPushButton("✏️ 按名称添加")
        btn_add_text.setToolTip("按文件夹名称手动添加（例如 'world'、'libraries'）")
        btn_add_text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_add_text.clicked.connect(self._on_add_folder_by_name)
        btn_row.addWidget(btn_add_text)
        btn_row.addStretch()
        content_layout.addLayout(btn_row)

        layout.addWidget(self._config_folders_content)
        parent_layout.addWidget(self._config_folders_group)

    def _toggle_config_folders_collapse(self):
        collapsed = self._config_folders_content.isVisible()
        self._config_folders_content.setVisible(not collapsed)
        self._config_folders_collapse_btn.setText("▼ 展开" if collapsed else "▲ 折叠")

    def _toggle_config_folders_check(self, checked: bool):
        for i in range(self._config_folders_list.count()):
            item = self._config_folders_list.item(i)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _save_default_folders(self):
        selected = self._get_selected_config_folders()
        self._save_config_value("default_folders", selected)
        self._log(f"[配置] 已保存默认文件夹: {', '.join(selected)}")
        QMessageBox.information(self, "保存成功",
            f"已保存 {len(selected)} 个文件夹为默认配置：\n{', '.join(selected)}")

    def _load_default_folders(self) -> list:
        return self._config_data.get("default_folders", [])

    def _get_selected_config_folders(self) -> list:
        selected = []
        for i in range(self._config_folders_list.count()):
            item = self._config_folders_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def _on_add_custom_folder(self):
        if not self._game_dir:
            QMessageBox.warning(self, "提示", "请先选择游戏目录。")
            return
        game_dir = Path(self._game_dir)
        all_folders = sorted(
            [d.name for d in game_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        )
        existing = set()
        for i in range(self._config_folders_list.count()):
            existing.add(self._config_folders_list.item(i).text())
        available = [f for f in all_folders if f not in existing]
        if not available:
            QMessageBox.information(self, "提示", "没有可添加的文件夹。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("手动添加文件夹")
        dialog.setMinimumSize(300, 350)
        d_layout = QVBoxLayout(dialog)
        d_layout.addWidget(QLabel("选择要添加的文件夹（来自当前游戏目录）："))
        list_widget = QListWidget()
        for name in available:
            list_widget.addItem(name)
        list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        d_layout.addWidget(list_widget)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        d_layout.addWidget(btn_box)
        if dialog.exec() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                folder_name = selected_items[0].text()
                item = QListWidgetItem(folder_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setToolTip(f"手动添加: {folder_name} 文件夹")
                self._config_folders_list.addItem(item)
                self._log(f"[配置] 手动添加文件夹: {folder_name}")

    def _on_remove_selected_folder(self):
        items = self._config_folders_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先在列表中选择要移除的文件夹。")
            return
        for item in items:
            self._config_folders_list.takeItem(self._config_folders_list.row(item))
        self._log(f"[配置] 已从列表移除 {len(items)} 个文件夹")

    def _on_add_folder_by_name(self):
        text, ok = QInputDialog.getText(self, "按名称添加文件夹",
            "输入要添加的文件夹名称（多个用逗号分隔）：\n例如：world, libraries, schematics")
        if ok and text.strip():
            names = [n.strip() for n in text.split(",") if n.strip()]
            existing = {self._config_folders_list.item(i).text()
                        for i in range(self._config_folders_list.count())}
            added = 0
            for name in names:
                if name in existing:
                    continue
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setToolTip(f"按名称添加: {name}")
                self._config_folders_list.addItem(item)
                added += 1
            if added > 0:
                self._config_folders_group.setVisible(True)
            self._log(f"[配置] 按名称添加了 {added} 个文件夹（{len(names) - added} 个已存在）")

    # ───────────────────────────────────────────────────────────────────
    # 3. 模组列表（可折叠表格）
    # ───────────────────────────────────────────────────────────────────

    def _build_mods_list_section(self, parent_layout: QVBoxLayout):
        self._mods_list_group = QGroupBox("📦 模组列表（选择要包含的模组，client 默认不勾选）")
        self._mods_list_group.setVisible(False)
        layout = QVBoxLayout(self._mods_list_group)

        top_row = QHBoxLayout()
        self._mods_collapse_btn = QPushButton("▲ 折叠")
        self._mods_collapse_btn.setToolTip("点击折叠/展开模组列表")
        self._mods_collapse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._mods_collapse_btn.clicked.connect(self._toggle_mods_list_collapse)
        top_row.addWidget(self._mods_collapse_btn)
        self._mods_stats_label = QLabel("模组: 0 个")
        self._mods_stats_label.setObjectName("statusLabel")
        top_row.addWidget(self._mods_stats_label)
        self._combo_mod_filter = QComboBox()
        self._combo_mod_filter.addItems(["全部", "客户端", "服务端", "双端", "未知"])
        self._combo_mod_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._combo_mod_filter.currentIndexChanged.connect(self._on_mod_filter_changed)
        top_row.addWidget(QLabel("筛选:"))
        top_row.addWidget(self._combo_mod_filter)
        top_row.addStretch()
        layout.addLayout(top_row)

        self._mods_list_content = QWidget()
        content_layout = QVBoxLayout(self._mods_list_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._mods_table = QTableWidget()
        self._mods_table.setColumnCount(5)
        self._mods_table.setHorizontalHeaderLabels(["✓", "文件名", "ModID", "版本", "类型"])
        self._mods_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._mods_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._mods_table.setMaximumHeight(200)
        self._mods_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hh = self._mods_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self._mods_table.setColumnWidth(0, 30)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self._mods_table.setColumnWidth(2, 130)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self._mods_table.setColumnWidth(3, 100)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self._mods_table.setColumnWidth(4, 60)
        self._mods_table.verticalHeader().setVisible(False)
        content_layout.addWidget(self._mods_table)

        btn_row = QHBoxLayout()
        btn_select_all = QPushButton("全选")
        btn_select_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_select_all.clicked.connect(lambda: self._toggle_all_mods(True))
        btn_row.addWidget(btn_select_all)
        btn_deselect_all = QPushButton("取消全选")
        btn_deselect_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_deselect_all.clicked.connect(lambda: self._toggle_all_mods(False))
        btn_row.addWidget(btn_deselect_all)
        btn_default = QPushButton("恢复默认")
        btn_default.setToolTip("恢复默认勾选：client 模组不勾选，其余勾选")
        btn_default.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_default.clicked.connect(self._reset_mods_to_default)
        btn_row.addWidget(btn_default)
        btn_unknown = QPushButton("❓ 未知模组管理")
        btn_unknown.setToolTip("查看和导出无法识别环境的模组")
        btn_unknown.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_unknown.clicked.connect(self._on_manage_unknown_mods)
        btn_row.addWidget(btn_unknown)
        btn_row.addStretch()
        content_layout.addLayout(btn_row)

        layout.addWidget(self._mods_list_content)
        parent_layout.addWidget(self._mods_list_group)

    def _toggle_mods_list_collapse(self):
        collapsed = self._mods_list_content.isVisible()
        self._mods_list_content.setVisible(not collapsed)
        self._mods_collapse_btn.setText("▼ 展开" if collapsed else "▲ 折叠")

    SIDE_LABEL_MAP = {"client": "客户端", "server": "服务端", "both": "双端", "unknown": "未知"}

    def _toggle_all_mods(self, checked: bool):
        for row in range(self._mods_table.rowCount()):
            item = self._mods_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._update_mods_stats()

    def _reset_mods_to_default(self):
        for row in range(self._mods_table.rowCount()):
            item = self._mods_table.item(row, 0)
            type_item = self._mods_table.item(row, 4)
            if item and type_item:
                is_client = type_item.text() == "客户端"
                item.setCheckState(Qt.Unchecked if is_client else Qt.Checked)
        self._update_mods_stats()

    def _update_mods_stats(self):
        total = self._mods_table.rowCount()
        checked = sum(1 for row in range(total)
                      if self._mods_table.item(row, 0)
                      and self._mods_table.item(row, 0).checkState() == Qt.Checked)
        unknown_count = sum(1 for row in range(total)
                            if self._mods_table.item(row, 4)
                            and self._mods_table.item(row, 4).text() == "未知")
        text = f"模组: {total} 个 (已选 {checked} 个)"
        if unknown_count > 0:
            text += f"  ⚠ {unknown_count} 个类型未知，请自行检查"
        self._mods_stats_label.setText(text)

    def _on_mod_filter_changed(self, index: int):
        filter_map = {
            0: "all",
            1: "客户端",
            2: "服务端",
            3: "双端",
            4: "未知",
        }
        filter_val = filter_map.get(index, "all")
        for row in range(self._mods_table.rowCount()):
            type_item = self._mods_table.item(row, 4)
            if filter_val == "all":
                self._mods_table.setRowHidden(row, False)
            elif type_item:
                self._mods_table.setRowHidden(row, type_item.text() != filter_val)
        self._update_mods_stats()

    def _get_selected_mod_paths(self) -> list:
        selected = []
        for row in range(self._mods_table.rowCount()):
            item = self._mods_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected

    # ───────────────────────────────────────────────────────────────────
    # 4. 服务器配置（图标/MOTD）
    # ───────────────────────────────────────────────────────────────────

    def _build_server_profile_section(self, parent_layout: QVBoxLayout):
        group = QGroupBox("🖥️ 服务器配置（图标/MOTD）")
        layout = QVBoxLayout(group)

        icon_row = QHBoxLayout()
        btn_icon = QPushButton("🖼️ 选择服务器图标（64×64 PNG）")
        btn_icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_icon.clicked.connect(self._on_select_icon)
        icon_row.addWidget(btn_icon)
        self._icon_preview = QLabel("无图标")
        self._icon_preview.setFixedSize(64, 64)
        self._icon_preview.setStyleSheet("border: 1px solid #555; background: #333; border-radius: 8px;")
        self._icon_preview.setAlignment(Qt.AlignCenter)
        icon_row.addWidget(self._icon_preview)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        motd_row = QHBoxLayout()
        motd_row.addWidget(QLabel("MOTD:"))
        self._edit_motd = QLineEdit()
        self._edit_motd.setPlaceholderText("A Minecraft Server")
        self._edit_motd.setMaxLength(118)
        motd_row.addWidget(self._edit_motd, 1)
        btn_color_help = QPushButton("🎨")
        btn_color_help.setFixedSize(32, 28)
        btn_color_help.setToolTip("颜色代码帮助")
        btn_color_help.clicked.connect(self._show_color_help)
        motd_row.addWidget(btn_color_help)
        layout.addLayout(motd_row)

        # MOTD预览框 - 放大一倍
        self._motd_preview_container = QWidget()
        self._motd_preview_container.setObjectName("motd_preview_container")
        self._motd_preview_container.setMinimumHeight(120)  # 放大一倍
        self._motd_preview_container.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);
            border-radius: 8px;
            border: 2px solid #3d3d5c;
        """)
        preview_layout = QHBoxLayout(self._motd_preview_container)
        preview_layout.setContentsMargins(16, 16, 16, 16)

        # 图标预览
        self._motd_icon_preview = QLabel()
        self._motd_icon_preview.setObjectName("motd_icon_preview")
        self._motd_icon_preview.setFixedSize(64, 64)
        self._motd_icon_preview.setStyleSheet("background: #2a2a4a; border-radius: 4px;")
        self._motd_icon_preview.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self._motd_icon_preview)

        # 文字信息
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(12, 0, 0, 0)
        text_layout.setSpacing(8)

        self._motd_server_name = QLabel("A Minecraft Server")
        self._motd_server_name.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        self._motd_server_name.setTextFormat(Qt.RichText)
        text_layout.addWidget(self._motd_server_name)

        # 在线人数文字加粗
        self._motd_server_info = QLabel("● 在线 | 0/100")
        self._motd_server_info.setStyleSheet("""
            color: #55ff55;
            font-size: 14px;
            font-weight: 700;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        text_layout.addWidget(self._motd_server_info)

        preview_layout.addWidget(text_container, 1)
        layout.addWidget(self._motd_preview_container)
        self._edit_motd.textChanged.connect(self._on_motd_changed)

        parent_layout.addWidget(group)

    # ───────────────────────────────────────────────────────────────────
    # 5. 操作区
    # ───────────────────────────────────────────────────────────────────

    def _build_action_buttons(self, parent_layout: QVBoxLayout):
        # 输出目录 + 内存 + Java（横向对齐，统一高度）
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("输出目录:"))
        self._edit_output_dir = QLineEdit()
        self._edit_output_dir.setToolTip("服务端生成位置，留空则自动生成")
        self._edit_output_dir.setPlaceholderText("留空自动生成，或输入/浏览自定义目录")
        out_row.addWidget(self._edit_output_dir, 1)
        btn_browse_out = QPushButton("📂 浏览...")
        btn_browse_out.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_browse_out.clicked.connect(self._on_browse_output_dir)
        out_row.addWidget(btn_browse_out)

        out_row.addWidget(QLabel("内存:"))
        self._combo_memory = QComboBox()
        self._combo_memory.addItems(["2G", "4G", "6G", "8G", "12G", "16G", "自定义"])
        self._combo_memory.setCurrentText("4G")
        self._combo_memory.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._combo_memory.setMinimumHeight(36)  # 统一高度
        out_row.addWidget(self._combo_memory)

        out_row.addWidget(QLabel("Java:"))
        self._combo_java = QComboBox()
        self._combo_java.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._combo_java.setMinimumHeight(36)  # 统一高度
        self._refresh_java_list()
        out_row.addWidget(self._combo_java)
        parent_layout.addLayout(out_row)

        # 开始生成 + 停止按钮
        row = QHBoxLayout()
        self._btn_generate = QPushButton("🚀 开始生成")
        self._btn_generate.setObjectName("btn_generate")
        self._btn_generate.setToolTip("下载服务端核心 → 复制模组和配置 → 生成启动脚本")
        self._btn_generate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_generate.setMinimumHeight(48)  # 增加高度
        self._btn_generate.clicked.connect(self._on_generate)
        self._btn_generate.setEnabled(False)
        row.addWidget(self._btn_generate)

        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btn_stop.setMinimumHeight(48)  # 统一高度
        self._btn_stop.setToolTip("停止当前正在运行的操作")
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        row.addWidget(self._btn_stop)

        parent_layout.addLayout(row)

        # 完成后打开说明文件按钮 + 教程按钮
        btn_row = QHBoxLayout()
        self._btn_open_readme = QPushButton("📄 打开启动说明")
        self._btn_open_readme.setObjectName("btn_open_readme")
        self._btn_open_readme.setToolTip("生成完成后，点击查看服务端启动说明和配置指南")
        self._btn_open_readme.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_open_readme.clicked.connect(self._on_open_readme)
        self._btn_open_readme.setMinimumHeight(40)
        btn_row.addWidget(self._btn_open_readme)

        self._btn_tutorial = QPushButton("📖 使用教程")
        self._btn_tutorial.setObjectName("btn_tutorial")
        self._btn_tutorial.setToolTip("查看软件使用教程和服务器搭建指南")
        self._btn_tutorial.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn_tutorial.clicked.connect(self._on_open_tutorial)
        self._btn_tutorial.setMinimumHeight(40)
        btn_row.addWidget(self._btn_tutorial)
        
        parent_layout.addLayout(btn_row)

    # ───────────────────────────────────────────────────────────────────
    # 6. 进度与日志
    # ───────────────────────────────────────────────────────────────────

    def _build_progress_log(self, parent_layout: QVBoxLayout):
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("就绪")
        parent_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("statusLabel")
        parent_layout.addWidget(self._status_label)

        # 日志框容器（包含清空按钮）
        log_container = QVBoxLayout()
        log_container.setSpacing(8)
        
        # 日志框头部（清空按钮）
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("日志输出"))
        log_header.addStretch()
        btn_clear_log = QPushButton("🗑️ 清空")
        btn_clear_log.setToolTip("清空日志内容")
        btn_clear_log.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_clear_log.clicked.connect(self._on_clear_log)
        log_header.addWidget(btn_clear_log)
        log_container.addLayout(log_header)

        self._log_view = QTextEdit()
        self._log_view.setObjectName("log_view")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(180)
        self._log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 使用等宽字体
        log_font = QFont("Consolas", 11)
        self._log_view.setFont(log_font)
        log_container.addWidget(self._log_view)
        
        parent_layout.addLayout(log_container)

    def _on_clear_log(self):
        """清空日志内容"""
        self._log_view.clear()

    # ═══════════════════════════════════════════════════════════════════
    # 事件处理
    # ═══════════════════════════════════════════════════════════════════

    def _on_browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择游戏版本目录",
            str(Path.home() / "AppData" / "Roaming" / ".minecraft" / "versions")
        )
        if folder:
            self._game_dir = Path(folder)
            self._game_dir_label.setText(f"已选择: {self._game_dir}")
            self._log(f"已选择目录: {self._game_dir}")
            self._btn_detect.setEnabled(True)
            self._scan_result = None
            self._mod_analysis_result = None
            self._info_mc_version.setText("MC 版本: —")
            self._info_loader.setText("加载器: —")
            self._info_mod_count.setText("模组: —")
            self._config_folders_label.setText("配置文件夹: —")
            self._edit_mc_version.setText("")
            self._edit_mc_version.setEnabled(False)
            self._combo_loader_override.setCurrentIndex(0)
            self._combo_loader_override.setEnabled(False)
            self._edit_loader_version.setText("")
            self._edit_loader_version.setEnabled(False)
            self._config_folders_group.setVisible(False)
            self._config_folders_list.clear()
            self._mods_list_group.setVisible(False)
            self._mods_table.setRowCount(0)
            self._btn_open_readme.setEnabled(True)
            self._set_status("目录已选择，请点击「🔍 检测」按钮开始分析。")

    def _on_browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择服务端输出目录", "")
        if folder:
            self._edit_output_dir.setText(folder)

    def _on_detect(self):
        self._disable_ui_for_work()
        self._set_status("正在扫描游戏目录...")
        self._log("[扫描] 开始扫描游戏目录...")
        self._worker = ScanWorker(str(self._game_dir))
        self._worker.signals.log.connect(self._log)
        self._worker.signals.finished.connect(self._on_scan_finished)
        self._worker.signals.error.connect(self._on_scan_error)
        self._worker.start()
        self._current_worker = self._worker

    def _on_scan_finished(self, result: dict):
        self._scan_result = result
        self._current_worker = None
        pack_name = result.get("pack_name", "")
        self._info_mc_version.setText(f"MC 版本: {result['mc_version']}")
        self._info_loader.setText(f"加载器: {result['loader_type']} {result['loader_version']}")
        self._info_mod_count.setText(f"模组: {result['mod_count']} 个")
        all_folders = result.get("all_folders", [])
        self._config_folders_label.setText(f"文件夹: {', '.join(all_folders)}" if all_folders else "文件夹: (无)")
        self._log(f"[检测] 整合包: {pack_name}, MC: {result['mc_version']}, "
                  f"加载器: {result['loader_type']} {result['loader_version']}")

        # 自动填充版本输入框并高亮提示
        mc_ver = result.get("mc_version", "")
        loader_ver = result.get("loader_version", "")
        lt = result.get("loader_type", "vanilla")

        self._edit_mc_version.setEnabled(True)
        self._edit_mc_version.setText(mc_ver)
        self._edit_mc_version.setStyleSheet("""
            background-color: #2382DE;
            color: white;
            border: 2px solid #3498eb;
            border-radius: 8px;
            padding: 10px 12px;
            font-weight: 600;
        """)
        # 2秒后恢复默认样式
        QTimer.singleShot(2000, lambda: self._edit_mc_version.setStyleSheet(""))

        self._combo_loader_override.setEnabled(True)
        idx = self._combo_loader_override.findText(lt)
        if idx >= 0:
            self._combo_loader_override.setCurrentIndex(idx)
        self._edit_loader_version.setEnabled(True)
        self._edit_loader_version.setText(loader_ver)

        self._populate_config_folders(all_folders)
        self._populate_mods_list(result.get("mod_files", []))
        self._start_mod_analysis(result.get("mod_files", []))

        self._enable_ui_after_work()
        self._set_status("扫描完成，可以开始分离服务器基础文件。")

    def _on_scan_error(self, message: str):
        self._current_worker = None
        self._enable_ui_after_work()
        QMessageBox.warning(self, "扫描失败", message)

    def _populate_config_folders(self, folders: list):
        self._config_folders_list.clear()
        if not folders:
            self._config_folders_group.setVisible(False)
            return
        self._config_folders_group.setVisible(True)
        default_folders = self._load_default_folders()
        from utils.constants import PRESERVED_FOLDERS, CLIENT_ONLY_FOLDERS
        for folder_name in folders:
            item = QListWidgetItem(folder_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if folder_name in default_folders:
                should_check = True
                tip = f"复制 {folder_name} 文件夹到服务端（用户默认配置）"
            elif folder_name in CLIENT_ONLY_FOLDERS:
                should_check = False
                tip = f"客户端文件夹（默认不复制）：{folder_name}"
            elif folder_name in PRESERVED_FOLDERS:
                should_check = True
                tip = f"服务端常用文件夹（默认复制）：{folder_name}"
            else:
                should_check = False
                tip = f"可选：复制 {folder_name} 文件夹到服务端（手动勾选）"
            item.setCheckState(Qt.Checked if should_check else Qt.Unchecked)
            item.setToolTip(tip)
            self._config_folders_list.addItem(item)

    def _populate_mods_list(self, mod_files: list):
        self._mods_table.setRowCount(0)
        if not mod_files:
            self._mods_list_group.setVisible(False)
            return
        self._mods_list_group.setVisible(True)
        self._mods_table.setRowCount(len(mod_files))
        for i, mod_path in enumerate(mod_files):
            p = Path(mod_path)
            check_item = QTableWidgetItem()
            check_item.setFlags(check_item.flags() | Qt.ItemIsUserCheckable)
            check_item.setCheckState(Qt.Checked)
            check_item.setData(Qt.UserRole, mod_path)
            self._mods_table.setItem(i, 0, check_item)
            self._mods_table.setItem(i, 1, QTableWidgetItem(p.name))
            self._mods_table.setItem(i, 2, QTableWidgetItem("分析中..."))
            self._mods_table.setItem(i, 3, QTableWidgetItem(""))
            self._mods_table.setItem(i, 4, QTableWidgetItem("分析中..."))
        self._update_mods_stats()

    def _start_mod_analysis(self, mod_files: list):
        if not mod_files:
            self._mod_analysis_result = None
            return
        self._log("[模组分析] 正在进入 jar 内部文件解析 modid 和类型...")
        self._worker = ModFilterWorker(mod_files, self._mod_db)
        self._worker.signals.mod_progress.connect(
            lambda name: self._log(f"[模组分析] {name}"))
        self._worker.signals.finished.connect(self._on_mod_analysis_finished)
        self._worker.signals.error.connect(lambda msg: self._log(f"[模组分析] 错误: {msg}"))
        self._worker.start()
        self._current_worker = self._worker

    def _on_mod_analysis_finished(self, result: dict):
        self._current_worker = None
        self._mod_analysis_result = result
        client_mods = set(Path(p).name for p in result.get("client_mods", []))
        server_mods = set(Path(p).name for p in result.get("server_mods", []))
        mod_details = result.get("mod_details", {})

        for row in range(self._mods_table.rowCount()):
            check_item = self._mods_table.item(row, 0)
            name_item = self._mods_table.item(row, 1)
            if not check_item or not name_item:
                continue
            mod_name = name_item.text()
            mod_path = check_item.data(Qt.UserRole)
            detail = mod_details.get(mod_path, {})
            modid = detail.get("modid", "(未识别)")
            side = detail.get("side", "unknown")
            version = detail.get("version", "")
            self._mods_table.setItem(row, 2, QTableWidgetItem(str(modid)))
            self._mods_table.setItem(row, 3, QTableWidgetItem(str(version)))
            type_label = self.SIDE_LABEL_MAP.get(side, "未知")
            self._mods_table.setItem(row, 4, QTableWidgetItem(type_label))
            if mod_name in client_mods and mod_name not in server_mods:
                check_item.setCheckState(Qt.Unchecked)
            else:
                check_item.setCheckState(Qt.Checked)

        self._update_mods_stats()
        self._log(f"[模组分析] 完成: 服务端={len(server_mods)} 个, 客户端={len(client_mods)} 个")
        self._set_status("模组分析完成，请检查模组列表的勾选状态。")

    # ═══════════════════════════════════════════════════════════════════
    # 生成 / 分离
    # ═══════════════════════════════════════════════════════════════════

    def _on_generate(self):
        if not self._scan_result:
            QMessageBox.warning(self, "提示", "请先扫描游戏目录。")
            return
        self._disable_ui_for_work()
        config = self._collect_generation_config()
        self._log("[分离] ====== 开始分离服务器基础文件 ======")
        self._worker = GenerateWorker(config)
        self._worker.signals.progress.connect(self._set_progress)
        self._worker.signals.status.connect(self._set_status)
        self._worker.signals.log.connect(self._log)
        self._worker.signals.finished.connect(self._on_generate_finished)
        self._worker.signals.error.connect(self._on_generate_error)
        self._worker.signals.manual_download_needed.connect(self._on_manual_download_needed)
        self._worker.start()
        self._current_worker = self._worker

    def _collect_generation_config(self) -> dict:
        scan = self._scan_result
        memory = self._combo_memory.currentText()
        if memory == "自定义":
            memory = self._config_data.get("custom_memory", "4G")
        mc_version = self._edit_mc_version.text().strip() or scan["mc_version"]
        loader_type = self._combo_loader_override.currentText() or scan["loader_type"]
        loader_version = self._edit_loader_version.text().strip() or scan["loader_version"]
        selected_mods = self._get_selected_mod_paths()
        selected_folders = self._get_selected_config_folders()
        output_dir = self._edit_output_dir.text().strip()
        return {
            "game_dir": str(self._game_dir),
            "pack_name": scan.get("pack_name", ""),
            "mc_version": mc_version,
            "loader_type": loader_type,
            "loader_version": loader_version,
            "mod_files": selected_mods,
            "memory": memory,
            "server_icon_pixmap": self._server_icon_pixmap,
            "custom_sources": self._config_data.get("custom_sources", []),
            "offline_core_path": self._config_data.get("offline_core_path", None),
            "selected_folders": selected_folders,
            "output_dir": output_dir,
            "java_path": self._combo_java.currentData(Qt.UserRole) if hasattr(self, '_combo_java') else None,
            "motd": self._edit_motd.text().strip() if hasattr(self, '_edit_motd') else None,
        }

    def _on_generate_finished(self, result: dict):
        self._current_worker = None
        self._last_output_dir = Path(result["output_dir"])
        self._enable_ui_after_work()

        scan = self._scan_result or {}
        loader_type = scan.get("loader_type", "vanilla")
        mc_version = scan.get("mc_version", "")
        loader_version = scan.get("loader_version", "")
        download_failed = result.get("download_failed", False)
        download_info = result.get("download_info")

        if download_failed and download_info:
            self._set_progress(100, "⚠ 生成完成，但服务端核心下载失败")
            filename = download_info.get("filename", "未知文件")
            placement_dir = download_info.get("placement_dir", "")
            suggested_urls = download_info.get("suggested_urls", [])
            detail = (
                f"服务端已生成到:\n{self._last_output_dir}\n\n"
                f"但服务端核心下载失败，请手动下载：\n\n"
                f"文件名: {filename}\n"
                f"放置目录: {placement_dir}\n"
            )
            if suggested_urls:
                detail += "\n建议下载地址:\n"
                for url in suggested_urls[:3]:
                    detail += f"  • {url}\n"
            detail += "\n下载后放到上述目录，然后点击「打开启动说明」查看如何继续。"
            QMessageBox.warning(self, "生成完成（需手动下载服务端核心）", detail)
            self._btn_open_readme.setEnabled(True)
        else:
            self._set_progress(100, "✅ 生成完毕！")
            self._generate_readme(self._last_output_dir, loader_type, mc_version, loader_version)
            self._btn_open_readme.setEnabled(True)
            QMessageBox.information(self, "生成完成",
                f"服务端已生成到:\n{self._last_output_dir}\n\n"
                "已自动生成启动说明文档（README.md）\n\n"
                "请点击「打开启动说明」查看详细的配置和启动指南。")

    def _generate_readme(self, output_dir: Path, loader_type: str, mc_version: str, loader_version: str):
        """生成服务端启动说明文档"""
        readme_path = output_dir / "README.md"
        
        loader_names = {
            "forge": "Forge",
            "neoforge": "NeoForge",
            "fabric": "Fabric",
            "vanilla": "Vanilla"
        }
        loader_name = loader_names.get(loader_type, loader_type.title())

        installer_filename = ""
        if loader_type == "forge":
            installer_filename = f"forge-{mc_version}-{loader_version}-installer.jar"
        elif loader_type == "neoforge":
            installer_filename = f"neoforge-{loader_version}-installer.jar"

        from utils.paths import get_resource_path
        template_path = get_resource_path("data/readme_template.md")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
        except Exception:
            template_content = self._get_default_readme_template()

        content = template_content.format(
            loader_name=loader_name,
            mc_version=mc_version,
            loader_version=loader_version,
            generate_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            output_dir=output_dir,
            installer_filename=installer_filename,
        )

        try:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"[文档] 已生成启动说明: {readme_path.name}")
        except Exception as e:
            self._log(f"[文档] 生成说明文档失败: {e}")

    def _get_default_readme_template(self) -> str:
        """内置的默认 README 模板"""
        return """# Minecraft {loader_name} 服务端

> 本文档由 MC Server Maker 自动生成

## 服务器信息

| 项目 | 内容 |
|------|------|
| 游戏版本 | {mc_version} |
| 加载器 | {loader_name} {loader_version} |
| 生成时间 | {generate_time} |
| 服务端目录 | `{output_dir}` |

---

## 快速启动

### 前置步骤（仅 Forge / NeoForge）

由于 Forge 和 NeoForge 的服务端核心文件需要通过安装器安装，您需要先执行以下步骤：

1. **找到安装器文件**：在服务端目录中找到 `{installer_filename}`
2. **运行安装器**：
   ```bash
   # Windows 系统
   java -jar {installer_filename} --installServer

   # Linux / Mac 系统
   java -jar {installer_filename} --installServer
   ```
3. **等待安装完成**：安装器会自动解压服务端核心文件和依赖库
4. **删除安装器**（可选）：安装完成后可以删除 `{installer_filename}`

### Windows 系统
1. 双击运行 `start.bat`
2. 等待服务端启动完成

### Linux / Mac 系统
```bash
chmod +x start.sh
./start.sh
```

---

## 重要配置文件

### server.properties（服务器配置）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server-port` | 25565 | 服务器端口 |
| `motd` | A Minecraft Server | 服务器名称 |
| `max-players` | 100 | 最大玩家数 |
| `online-mode` | true | 正版验证 |
| `difficulty` | easy | 游戏难度 |

### eula.txt
本文件已自动设置为同意 EULA（`eula=true`）。

### user_jvm_args.txt（JVM 参数）
```
-Xms2G
-Xmx4G
```

---

## 常见问题

### Q: Forge/NeoForge 安装器运行失败？
- 确保使用正确的 Java 版本（推荐 Java 17 或更高）
- 检查安装器文件是否完整

---
*MC Server Maker - 让服务端部署更简单*
"""

    def _on_open_readme(self):
        """打开当前服务端的 README.md 说明文件"""
        if not self._last_output_dir:
            QMessageBox.warning(self, "提示", "请先生成服务端")
            return
        
        readme_path = self._last_output_dir / "README.md"
        if not readme_path.exists():
            QMessageBox.warning(self, "文件不存在", f"未找到说明文件:\n{readme_path}")
            return
        
        try:
            import subprocess
            if sys.platform == "win32":
                os.startfile(str(readme_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(readme_path)])
            else:
                subprocess.run(["xdg-open", str(readme_path)])
            self._log(f"[文档] 已打开: {readme_path}")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{e}")

    def _on_open_tutorial(self):
        """打开教程说明窗口"""
        from ui.tutorial_window import TutorialWindow
        tutorial = TutorialWindow(self)
        tutorial.exec()

    def _on_generate_error(self, message: str):
        self._current_worker = None
        self._enable_ui_after_work()
        QMessageBox.warning(self, "分离失败", message)

    def _on_manual_download_needed(self, info: dict):
        self._current_worker = None
        self._enable_ui_after_work()
        filename = info.get("filename", "未知文件")
        placement_dir = info.get("placement_dir", "")
        suggested_urls = info.get("suggested_urls", [])
        message = info.get("message", "自动下载失败，请手动下载核心文件。")
        detail = f"{message}\n\n文件名: {filename}\n放置目录: {placement_dir}"
        if suggested_urls:
            detail += "\n\n建议下载地址:"
            for url in suggested_urls[:3]:
                detail += f"\n  • {url}"
        reply = QMessageBox.warning(
            self, "需要手动下载", detail,
            QMessageBox.Open | QMessageBox.Cancel, QMessageBox.Open
        )
        if reply == QMessageBox.Open:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择已下载的核心文件", placement_dir,
                "JAR 文件 (*.jar);;所有文件 (*.*)"
            )
            if file_path:
                dest = Path(placement_dir) / filename
                try:
                    shutil.copy2(file_path, dest)
                    self._log(f"[手动下载] 已复制 {file_path} → {dest}")
                    self._set_status("核心文件已就绪，请再次点击「分离服务器基础文件」。")
                    QMessageBox.information(self, "就绪",
                        f"核心文件已放置到:\n{dest}\n\n请再次点击「分离服务器基础文件」继续。")
                except Exception as e:
                    QMessageBox.warning(self, "复制失败", f"复制文件失败: {e}")

    def _on_stop(self):
        if self._current_worker:
            self._log("[操作] 用户请求停止运行...")
            self._current_worker.cancel()
            self._set_status("正在停止...")
            self._btn_stop.setEnabled(False)

    # ═══════════════════════════════════════════════════════════════════
    # UI 辅助
    # ═══════════════════════════════════════════════════════════════════

    def _on_select_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择服务器图标", "",
            "PNG 图片 (*.png);;所有文件 (*.*)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "加载失败", "无法加载图片，请检查文件格式。")
                return
            scaled = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._server_icon_pixmap = scaled
            self._icon_preview.setPixmap(scaled)
            self._motd_icon_preview.setPixmap(scaled)
            self._log(f"[图标] 已选择: {Path(file_path).name}")

    def _on_motd_changed(self, text: str):
        display = text.strip() if text.strip() else "A Minecraft Server"
        html = parse_motd_to_html(display)
        self._motd_server_name.setText(html)

    def _on_manage_unknown_mods(self):
        """未知模组管理对话框"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QFileDialog
        import webbrowser

        # 确保数据库已加载未知模组
        self._mod_db.load_unknown_mods()
        unknown_mods = self._mod_db.get_unknown_mods()
        count = self._mod_db.get_unknown_mods_count()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"❓ 未知模组管理（共 {count} 个）")
        dialog.setMinimumSize(550, 450)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        # 说明文字
        info = QLabel("以下是无法从 jar 内部和在线数据库识别环境的模组。"
                     "您可以导出后手动提交到社区数据库。")
        info.setWordWrap(True)
        info.setStyleSheet("color: #a0a0b0; padding: 8px;")
        layout.addWidget(info)

        # 列表显示
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e32;
                color: #e0e0e0;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)

        if unknown_mods:
            lines = []
            for modid, info in unknown_mods.items():
                name = info.get("name", "")
                version = info.get("version", "")
                author = info.get("author", "")
                lines.append(f"• {modid}")
                if name:
                    lines.append(f"   文件: {name}")
                if version:
                    lines.append(f"   版本: {version}")
                if author:
                    lines.append(f"   作者: {author}")
                lines.append("")
            text_edit.setText("\n".join(lines))
        else:
            text_edit.setText("暂无未知模组记录。\n\n扫描游戏目录后，无法识别环境的模组会显示在这里。")

        layout.addWidget(text_edit, 1)

        # 按钮行
        btn_layout = QHBoxLayout()

        btn_open_repo = QPushButton("🌐 查看社区数据库")
        btn_open_repo.setToolTip("在浏览器中打开未知模组数据仓库")
        btn_open_repo.clicked.connect(
            lambda: webbrowser.open(self._mod_db.get_unknown_mods_repo_url())
        )
        btn_layout.addWidget(btn_open_repo)

        btn_layout.addStretch()

        btn_export = QPushButton("📤 导出 JSON")
        btn_export.setToolTip("导出未知模组为 JSON 文件，可用于手动提交 PR")
        btn_export.clicked.connect(lambda: self._export_unknown_mods(dialog))
        btn_layout.addWidget(btn_export)

        btn_clear = QPushButton("🗑️ 清空")
        btn_clear.setToolTip("清空本地未知模组记录")
        btn_clear.clicked.connect(lambda: self._clear_unknown_mods(dialog))
        btn_layout.addWidget(btn_clear)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _export_unknown_mods(self, parent_dialog):
        """导出未知模组为 JSON 文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            parent_dialog, "导出未知模组", "unknown_mods.json", "JSON 文件 (*.json)"
        )
        if file_path:
            success, msg = self._mod_db.export_unknown_mods(file_path)
            if success:
                QMessageBox.information(parent_dialog, "导出成功", msg +
                    "\n\n您可以将此文件提交到 GitHub 社区数据库，帮助完善模组环境识别。")
            else:
                QMessageBox.warning(parent_dialog, "导出失败", msg)

    def _clear_unknown_mods(self, parent_dialog):
        """清空未知模组记录"""
        reply = QMessageBox.question(
            parent_dialog, "确认清空", "确定要清空本地未知模组记录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._mod_db.clear_unknown_mods()
            parent_dialog.accept()
            QMessageBox.information(parent_dialog, "已清空", "未知模组记录已清空。")

    def _show_color_help(self):
        """显示 MOTD 颜色代码帮助对话框"""
        from utils.motd_colors import MINECRAFT_COLORS, MINECRAFT_FORMATS
        
        dialog = QDialog(self)
        dialog.setWindowTitle("MOTD 颜色代码帮助")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        
        info = QLabel("在 MOTD 中使用 & 或 § 加代码来添加颜色和格式：")
        info.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(info)
        
        color_grid = QGridLayout()
        color_grid.setSpacing(4)
        
        row, col = 0, 0
        for code, color in MINECRAFT_COLORS.items():
            label = QLabel(f" &{code} ")
            label.setStyleSheet(f"background: {color}; color: white; padding: 4px; border-radius: 3px; font-weight: bold;")
            label.setAlignment(Qt.AlignCenter)
            color_grid.addWidget(label, row, col)
            col += 1
            if col > 7:
                col = 0
                row += 1
        
        layout.addLayout(color_grid)
        
        format_label = QLabel("\n格式代码：")
        format_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(format_label)
        
        format_info = QLabel(
            "  &l - 加粗    &o - 斜体    &n - 下划线    &m - 删除线    &r - 重置"
        )
        format_info.setStyleSheet("color: #aaa; font-family: monospace;")
        layout.addWidget(format_info)
        
        example_label = QLabel("\n示例：")
        example_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(example_label)
        
        example_input = QLabel("  &c欢迎 &a来到 &b我的服务器")
        example_input.setStyleSheet("color: #888; font-family: monospace;")
        layout.addWidget(example_input)
        
        example_output = QLabel()
        example_output.setStyleSheet("background: #2a2a3a; padding: 8px; border-radius: 4px;")
        example_output.setTextFormat(Qt.RichText)
        example_output.setText(parse_motd_to_html("&c欢迎 &a来到 &b我的服务器"))
        layout.addWidget(example_output)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)
        
        dialog.exec()

    def _refresh_java_list(self):
        from core.java_manager import find_all_java_installations
        try:
            javas = find_all_java_installations()
        except Exception as e:
            self._log(f"[Java] 扫描 Java 安装时出错: {e}")
            javas = []
        self._combo_java.clear()
        self._combo_java.addItem("系统默认 Java")
        self._combo_java.setItemData(0, None, Qt.UserRole)
        for idx, j in enumerate(javas):
            display = j.get("display_name", f"Java {j.get('major_version', '?')}")
            path = j.get("java_path", "")
            self._combo_java.addItem(f"{display}")
            self._combo_java.setItemData(idx + 1, path, Qt.UserRole)
        if not javas:
            self._combo_java.setToolTip("未检测到已安装的 Java，使用系统默认")
        else:
            self._combo_java.setCurrentIndex(1 if len(javas) >= 1 else 0)
            self._combo_java.setToolTip("选择运行服务端使用的 Java 版本")

    # ═══════════════════════════════════════════════════════════════════
    # UI 辅助
    # ═══════════════════════════════════════════════════════════════════

    def _install_wheel_filter(self, widget):
        for child in widget.findChildren(QComboBox):
            child.installEventFilter(self._wheel_filter)

    def _set_progress(self, value: int, text: str = ""):
        self._progress_bar.setValue(value)
        if text:
            self._progress_bar.setFormat(text)

    def _set_status(self, text: str):
        self._status_label.setText(text)

    def _log(self, text: str):
        ts = log_timestamp()
        self._log_view.append(f"{ts} {text}")

    def _init_log(self):
        self._log("====== MC Server Maker v2 启动 ======")

    def _disable_ui_for_work(self):
        self._btn_generate.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_detect.setEnabled(False)

    def _enable_ui_after_work(self):
        self._btn_generate.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_detect.setEnabled(True)

    # ═══════════════════════════════════════════════════════════════════
    # 配置持久化
    # ═══════════════════════════════════════════════════════════════════

    def _load_user_config(self):
        import sys
        if getattr(sys, 'frozen', False):
            config_dir = Path(sys.executable).parent / "data"
        else:
            config_dir = Path(__file__).parent.parent / "data"
        self._config_path = config_dir / "user_config.json"
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
        except Exception:
            self._config_data = {}

    def _save_config_value(self, key: str, value):
        self._config_data[key] = value
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"[配置] 保存失败: {e}")

    def closeEvent(self, event):
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            self._current_worker.wait(3000)
        event.accept()
