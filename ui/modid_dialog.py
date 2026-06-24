# modid_dialog.py —— ModID 环境数据库管理对话框（暗色主题 v2）
# 提供：云端 URL 输入 + 刷新、统计显示、打开文件夹、导入 JSON、清空发现记录

import os
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QFormLayout, QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt

from core.mod_db import ModDatabase
from ui.worker import DBRefreshWorker
from utils.constants import DEFAULT_MOD_DB_URL


class ModIDDialog(QDialog):
    """ModID 环境数据库管理对话框"""

    def __init__(self, mod_db: ModDatabase, parent=None):
        super().__init__(parent)
        self._mod_db = mod_db
        self._worker = None

        self.setWindowTitle("ModID 环境数据库管理")
        self.setMinimumSize(550, 420)
        self._build_ui()
        self._refresh_stats()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 云端连接设置 ──────────────────────────────────────────
        cloud = QGroupBox("☁️ 云端连接设置")
        cl = QVBoxLayout(cloud)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("数据库 URL:"))
        self._url_edit = QLineEdit()
        self._url_edit.setToolTip("在线 mod_id.json 数据库的下载地址，可从 GitHub Raw 或其他 CDN 获取")
        self._url_edit.setText(DEFAULT_MOD_DB_URL)
        url_row.addWidget(self._url_edit, 1)

        self._btn_refresh = QPushButton("🔄 刷新数据库")
        self._btn_refresh.setObjectName("btnRefresh")
        self._btn_refresh.setToolTip("从上述 URL 下载最新的 ModID 数据库并替换本地缓存")
        self._btn_refresh.clicked.connect(self._on_refresh)
        url_row.addWidget(self._btn_refresh)

        cl.addLayout(url_row)
        self._refresh_status_label = QLabel("")
        self._refresh_status_label.setStyleSheet("color: #A6ADC8; font-style: italic;")
        cl.addWidget(self._refresh_status_label)
        layout.addWidget(cloud)

        # ── 统计信息 ──────────────────────────────────────────────
        stats = QGroupBox("📊 数据库统计")
        sf = QFormLayout(stats)
        self._lbl_online = QLabel("-"); self._lbl_local = QLabel("-")
        self._lbl_version = QLabel("-"); self._lbl_cache = QLabel("-")
        self._lbl_cache.setWordWrap(True)
        sf.addRow("在线数据库条目数:", self._lbl_online)
        sf.addRow("在线数据库版本:", self._lbl_version)
        sf.addRow("本地发现记录数:", self._lbl_local)
        sf.addRow("缓存路径:", self._lbl_cache)
        layout.addWidget(stats)

        # ── 操作按钮 ──────────────────────────────────────────────
        ops = QGroupBox("🔧 操作")
        ol = QVBoxLayout(ops)

        r1 = QHBoxLayout()
        btn_open = QPushButton("📂 打开数据库文件夹")
        btn_open.setToolTip("在系统文件管理器中打开数据库缓存所在的文件夹")
        btn_open.clicked.connect(self._on_open_db_folder)
        r1.addWidget(btn_open)

        btn_import = QPushButton("📥 导入本地 JSON")
        btn_import.setToolTip("从本地 JSON 文件导入 ModID 数据（支持合并或替换）")
        btn_import.clicked.connect(self._on_import_json)
        r1.addWidget(btn_import)
        ol.addLayout(r1)

        r2 = QHBoxLayout()
        btn_clear = QPushButton("🗑 清空本地发现记录")
        btn_clear.setToolTip("删除所有从 jar 文件自动解析并保存的本地 ModID 发现记录")
        btn_clear.setStyleSheet("color: #F38BA8;")
        btn_clear.clicked.connect(self._on_clear_local)
        r2.addWidget(btn_clear)
        r2.addStretch()
        ol.addLayout(r2)
        layout.addWidget(ops)

        # ── 关闭 ──────────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

    # ═══════════════════════════════════════════════════════════════════
    # 统计刷新
    # ═══════════════════════════════════════════════════════════════════

    def _refresh_stats(self):
        s = self._mod_db.get_stats()
        self._lbl_online.setText(str(s["online_count"]))
        self._lbl_local.setText(str(s["local_count"]))
        self._lbl_version.setText(str(s["db_version"]))
        self._lbl_cache.setText(str(s["cache_path"]))

    # ═══════════════════════════════════════════════════════════════════
    # 刷新数据库
    # ═══════════════════════════════════════════════════════════════════

    def _on_refresh(self):
        url = self._url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "输入错误", "请输入有效的数据库 URL。")
            return
        self._btn_refresh.setEnabled(False)
        self._refresh_status_label.setText("正在下载数据库...")
        self._refresh_status_label.setStyleSheet("color: #89B4FA;")

        self._worker = DBRefreshWorker(self._mod_db, url)
        self._worker.signals.finished.connect(self._on_refresh_finished)
        self._worker.signals.error.connect(self._on_refresh_error)
        self._worker.signals.log.connect(lambda m: self._refresh_status_label.setText(m))
        self._worker.start()

    def _on_refresh_finished(self, result: dict):
        self._btn_refresh.setEnabled(True)
        if result["success"]:
            self._refresh_status_label.setText("✅ " + result["message"].replace("\n", " | "))
            self._refresh_status_label.setStyleSheet("color: #A6E3A1;")
        else:
            self._refresh_status_label.setText("❌ " + result["message"])
            self._refresh_status_label.setStyleSheet("color: #F38BA8;")
        self._refresh_stats()

    def _on_refresh_error(self, message: str):
        self._btn_refresh.setEnabled(True)
        self._refresh_status_label.setText(f"❌ {message}")
        self._refresh_status_label.setStyleSheet("color: #F38BA8;")

    # ═══════════════════════════════════════════════════════════════════
    # 打开文件夹 / 导入 / 清空
    # ═══════════════════════════════════════════════════════════════════

    def _on_open_db_folder(self):
        db_dir = self._mod_db.get_db_dir()
        os.makedirs(db_dir, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(db_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", db_dir])
            else:
                subprocess.run(["xdg-open", db_dir])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件夹: {e}")

    def _on_import_json(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择 JSON 文件", "", "JSON 文件 (*.json)")
        if not fp:
            return
        reply = QMessageBox.question(
            self, "导入模式",
            "选择导入方式：\n\n【是】合并模式 — 保留现有数据，仅添加新条目\n【否】替换模式 — 完全替换现有数据库",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
        if reply == QMessageBox.Cancel:
            return
        success, message = self._mod_db.import_local_json(fp, merge=(reply == QMessageBox.Yes))
        if success:
            self._refresh_stats()
            QMessageBox.information(self, "导入结果", message)
        else:
            QMessageBox.warning(self, "导入失败", message)

    def _on_clear_local(self):
        if QMessageBox.question(
            self, "确认清空",
            f"确定要清空所有本地发现记录吗？\n当前有 {self._mod_db.local_discovery_count} 条记录。\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            success = self._mod_db.clear_local_discoveries()
            self._refresh_stats()
            if success:
                QMessageBox.information(self, "操作完成", "本地发现记录已清空。")
            else:
                QMessageBox.warning(self, "操作失败", "清空本地发现记录时发生错误。")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()