# main.py —— MC Server Maker v2 入口文件
# 负责：Qt 应用初始化、全局暗色主题样式、主窗口创建与显示

import sys
import os

# 确保项目根目录在 sys.path 中
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

# ── 全局样式常量（集中管理，便于调色） ──────────────────────────────
# 暗色主题 - 主色调 #2382DE
C_MAIN_BG      = "#1a1a2e"   # 主背景（深蓝灰）
C_CARD_BG      = "#1e1e32"   # 卡片/面板背景
C_BORDER       = "#2a2a4a"   # 边框
C_TEXT         = "#e0e0e0"   # 主文字
C_TEXT_SUB     = "#a0a0b0"   # 次级文字
C_ACCENT       = "#2382DE"   # 强调色（主色调）
C_ACCENT_HOVER = "#3498eb"   # 按钮悬停
C_SUCCESS      = "#34c759"   # 成功/完成
C_WARNING      = "#f9e2af"   # 警告
C_ERROR        = "#dc3545"   # 错误/停止（红色）
C_PROGRESS     = "#2382DE"   # 进度条填充
C_LOG_BG       = "#1a1a2e"   # 日志区终端背景
C_INPUT_BG     = "#252540"   # 输入框背景
C_DISABLED_BG  = "#3a3a5a"   # 禁用背景
C_DISABLED_TEXT = "#666666"   # 禁用文字
C_SCROLLBAR    = "#4a4a6a"   # 滚动条滑块
C_SCROLLBAR_TR = "#252540"   # 滚动条轨道

FONT_FAMILY    = '"Microsoft YaHei UI", "Segoe UI", "Noto Sans CJK SC", sans-serif'
FONT_MONO      = '"Cascadia Code", "Consolas", "Microsoft YaHei Mono", monospace'
FONT_SIZE      = "13px"
FONT_SIZE_TITLE = "14px"
BTN_HEIGHT     = "36px"
BTN_MIN_WIDTH  = "100px"
RADIUS         = "8px"
PROGRESS_H     = "24px"


def global_stylesheet() -> str:
    """生成全局 QSS 样式表"""
    return f"""
    /* ================================================================
       全局基础
       ================================================================ */
    QMainWindow {{
        background-color: {C_MAIN_BG};
        color: {C_TEXT};
    }}
    QWidget {{
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE};
        color: {C_TEXT};
    }}

    /* ================================================================
       ScrollArea（去掉白边框，融入背景）
       ================================================================ */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* ================================================================
       GroupBox（卡片面板）
       ================================================================ */
    QGroupBox {{
        background-color: {C_CARD_BG};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        margin-top: 14px;
        padding: 18px 14px 14px 14px;
        font-weight: bold;
        font-size: {FONT_SIZE_TITLE};
        color: {C_TEXT};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 10px;
        color: {C_ACCENT};
    }}

    /* ================================================================
       按钮
       ================================================================ */
    QPushButton {{
        background-color: {C_CARD_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        padding: 6px 16px;
        min-height: {BTN_HEIGHT};
        min-width: {BTN_MIN_WIDTH};
        font-weight: normal;
    }}
    QPushButton:hover {{
        background-color: #363649;
        border-color: {C_ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: #252537;
    }}
    QPushButton:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
        border-color: {C_DISABLED_BG};
    }}

    /* 主要操作按钮（蓝色渐变） */
    QPushButton#btn_generate {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C_ACCENT}, stop:1 #1a6bc9);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        font-size: 15px;
        min-height: 44px;
    }}
    QPushButton#btn_generate:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C_ACCENT_HOVER}, stop:1 {C_ACCENT});
    }}
    QPushButton#btn_generate:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* 停止按钮（红色警示） */
    QPushButton#btn_stop {{
        background-color: {C_ERROR};
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        font-size: 15px;
        min-height: 44px;
    }}
    QPushButton#btn_stop:hover {{
        background-color: #c82333;
    }}
    QPushButton#btn_stop:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* 打开说明按钮 */
    QPushButton#btn_open_readme {{
        background-color: {C_CARD_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: 8px;
    }}
    QPushButton#btn_open_readme:hover {{
        background-color: #3a3a5a;
        border-color: {C_ACCENT};
    }}

    /* 教程按钮 */
    QPushButton#btn_tutorial {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 8px;
    }}
    QPushButton#btn_tutorial:hover {{
        background-color: {C_ACCENT_HOVER};
    }}

    /* 检测按钮 */
    QPushButton#btn_detect {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 8px;
    }}
    QPushButton#btn_detect:hover {{
        background-color: {C_ACCENT_HOVER};
    }}
    QPushButton#btn_detect:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* 刷新数据库按钮（蓝色强调） */
    QPushButton#btnRefresh {{
        background-color: {C_ACCENT};
        color: #1E1E2E;
        font-weight: bold;
    }}
    QPushButton#btnRefresh:hover {{
        background-color: {C_ACCENT_HOVER};
    }}
    QPushButton#btnRefresh:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* 小号测试按钮（不设 min-width） */
    QPushButton#btnTestSource {{
        min-width: 48px;
        padding: 4px 8px;
    }}

    /* ================================================================
       输入框
       ================================================================ */
    QLineEdit {{
        background-color: {C_INPUT_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        padding: 6px 10px;
        selection-background-color: {C_ACCENT};
        selection-color: #1E1E2E;
    }}
    QLineEdit:focus {{
        border-color: {C_ACCENT};
    }}
    QLineEdit:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* ================================================================
       多行文本框（用于 MOTD 和日志）
       ================================================================ */
    QTextEdit {{
        background-color: {C_INPUT_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        padding: 6px 10px;
        selection-background-color: {C_ACCENT};
        selection-color: #1E1E2E;
    }}
    QTextEdit:focus {{
        border-color: {C_ACCENT};
    }}

    /* 日志区专用（终端风格 - 等宽字体） */
    QTextEdit#log_view {{
        background-color: {C_LOG_BG};
        color: {C_TEXT};
        font-family: {FONT_MONO};
        font-size: 11px;
        border: 1px solid {C_BORDER};
        border-radius: 8px;
        padding: 12px;
        line-height: 1.5;
    }}

    /* ================================================================
       下拉框
       ================================================================ */
    QComboBox {{
        background-color: {C_INPUT_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        padding: 6px 10px;
        min-height: {BTN_HEIGHT};
    }}
    QComboBox:hover {{
        border-color: {C_ACCENT};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: 1px solid {C_BORDER};
        border-top-right-radius: {RADIUS};
        border-bottom-right-radius: {RADIUS};
    }}
    QComboBox QAbstractItemView {{
        background-color: {C_CARD_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: 4px;
        selection-background-color: {C_ACCENT};
        selection-color: #1E1E2E;
        outline: none;
    }}
    QComboBox:disabled {{
        background-color: {C_DISABLED_BG};
        color: {C_DISABLED_TEXT};
    }}

    /* ================================================================
       复选框 / 单选框
       ================================================================ */
    QCheckBox {{
        color: {C_TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {C_BORDER};
        border-radius: 3px;
        background-color: {C_INPUT_BG};
    }}
    QCheckBox::indicator:checked {{
        background-color: {C_ACCENT};
        border-color: {C_ACCENT};
    }}
    QCheckBox::indicator:hover {{
        border-color: {C_ACCENT_HOVER};
    }}

    QRadioButton {{
        color: {C_TEXT};
        spacing: 8px;
    }}
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {C_BORDER};
        border-radius: 9px;
        background-color: {C_INPUT_BG};
    }}
    QRadioButton::indicator:checked {{
        background-color: {C_ACCENT};
        border-color: {C_ACCENT};
    }}

    /* ================================================================
       进度条
       ================================================================ */
    QProgressBar {{
        background-color: {C_INPUT_BG};
        border: 1px solid {C_BORDER};
        border-radius: {RADIUS};
        height: {PROGRESS_H};
        text-align: center;
        color: {C_TEXT};
        font-size: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {C_PROGRESS};
        border-radius: 4px;
    }}

    /* ================================================================
       标签页 / 信息 Label
       ================================================================ */
    QLabel {{
        color: {C_TEXT};
        background: transparent;
    }}
    QLabel#statusLabel {{
        color: {C_TEXT_SUB};
        font-style: italic;
    }}
    QLabel#gameDirLabel {{
        color: {C_TEXT_SUB};
    }}
    QLabel#infoTag {{
        background-color: {C_INPUT_BG};
        color: {C_TEXT};
        border-radius: 3px;
        padding: 2px 8px;
    }}

    /* MOTD 预览区 */
    QLabel#motdPreview {{
        background-color: #2D2D2D;
        color: #FFFFFF;
        border-radius: 4px;
        padding: 8px;
    }}

    /* 图标预览区 */
    QLabel#iconPreview {{
        background-color: {C_INPUT_BG};
        border: 2px dashed {C_BORDER};
        border-radius: 4px;
        color: {C_TEXT_SUB};
    }}

    /* 步骤指示器 */
    QLabel#stepDot {{
        border-radius: 8px;
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
    }}

    /* ================================================================
       滚动条
       ================================================================ */
    QScrollBar:vertical {{
        background-color: {C_SCROLLBAR_TR};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {C_SCROLLBAR};
        min-height: 40px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: #585B70;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
    }}

    QScrollBar:horizontal {{
        background-color: {C_SCROLLBAR_TR};
        height: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {C_SCROLLBAR};
        min-width: 40px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: #585B70;
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ================================================================
       工具提示
       ================================================================ */
    QToolTip {{
        background-color: {C_CARD_BG};
        color: {C_TEXT};
        border: 1px solid {C_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
    }}

    /* ================================================================
       分割线
       ================================================================ */
    QFrame#separator {{
        background-color: {C_BORDER};
        max-height: 1px;
        min-height: 1px;
    }}
    """


def main():
    """应用程序入口"""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from ui.main_window import MainWindow
    from utils.constants import APP_NAME

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MCServerMaker")

    # 注入全局暗色主题样式表
    app.setStyleSheet(global_stylesheet())

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()