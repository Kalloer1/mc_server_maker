# tutorial_window.py —— 教程说明窗口
# 职责：提供软件使用教程和 Minecraft 服务器搭建指南

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QLabel, QPushButton, QScrollArea,
    QWidget, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from pathlib import Path


class TutorialWindow(QDialog):
    """教程说明窗口 - 展示软件使用教程和服务器搭建指南"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 MC Server Maker - 使用教程")
        self.setMinimumSize(800, 600)
        self.resize(900, 680)

        self._setup_stylesheet()
        self._build_ui()

    def _setup_stylesheet(self):
        """设置窗口样式表"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f7;
            }

            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
                border-radius: 8px;
                margin: 0px;
            }

            QTabBar {
                background-color: #f0f0f5;
                border-radius: 8px;
            }

            QTabBar::tab {
                background-color: transparent;
                color: #666666;
                padding: 10px 20px;
                margin: 6px 3px 0px 3px;
                border-radius: 6px 6px 0 0;
                font-size: 13px;
                font-weight: 500;
            }

            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2382DE;
                font-weight: 600;
                border-bottom: 3px solid #2382DE;
            }

            QTabBar::tab:hover:!selected {
                background-color: #e8e8ed;
                color: #333333;
            }

            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #e8e8ed;
            }

            QPushButton {
                background-color: #2382DE;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
                min-width: 100px;
            }

            QPushButton:hover {
                background-color: #3498eb;
            }

            QPushButton:pressed {
                background-color: #1a6bc9;
            }

            QScrollArea {
                border: none;
                background-color: #ffffff;
                border-radius: 0 0 8px 8px;
            }

            QScrollBar:vertical {
                background-color: #f5f5f7;
                width: 8px;
                border-radius: 4px;
                margin: 8px 4px;
            }

            QScrollBar::handle:vertical {
                background-color: #d0d0d5;
                border-radius: 4px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #b0b0b5;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QTextEdit {
                background-color: transparent;
                border: none;
                font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                color: #333333;
                line-height: 1.5;
                font-size: 13px;
            }
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._tab_widget = QTabWidget()
        self._tab_widget.setTabPosition(QTabWidget.North)
        self._tab_widget.setDocumentMode(True)

        self._tab_widget.addTab(self._build_software_tutorial(), "📦 软件教程")
        self._tab_widget.addTab(self._build_server_guide(), "🖥️ 服务器指南")
        self._tab_widget.addTab(self._build_faq(), "❓ 常见问题")

        layout.addWidget(self._tab_widget, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setMinimumSize(120, 40)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _build_software_tutorial(self):
        """软件使用教程页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 标题区域
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5a9fd4, stop:1 #7899d6);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)

        title = QLabel("🎮 MC Server Maker")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: bold; margin: 0;")
        subtitle = QLabel("使用教程")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 15px; margin: 0;")
        desc = QLabel("快速将 Minecraft 整合包转换为服务端，只需几个简单步骤")
        desc.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 12px;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(desc)
        layout.addWidget(header_frame)

        # 主要功能
        features_frame = QFrame()
        features_layout = QVBoxLayout(features_frame)
        features_layout.setContentsMargins(14, 12, 14, 12)
        features_layout.setSpacing(8)

        features_title = QLabel("✨ 主要功能")
        features_title.setStyleSheet("color: #1c1c1e; font-size: 14px; font-weight: 600;")
        features_layout.addWidget(features_title)

        features_grid = QHBoxLayout()
        features_grid.setSpacing(10)

        features = [
            {"icon": "🎯", "title": "自动检测", "desc": "识别版本/加载器"},
            {"icon": "📦", "title": "模组筛选", "desc": "排除客户端模组"},
            {"icon": "⚙️", "title": "灵活配置", "desc": "图标/MOTD/内存"},
            {"icon": "📄", "title": "文档生成", "desc": "启动说明文档"},
        ]

        for feat in features:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    padding: 12px;
                    border: 1px solid #e9ecef;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            icon_label = QLabel(f"<span style='font-size: 20px;'>{feat['icon']}</span>")
            title_label = QLabel(f"<strong style='color: #1c1c1e; font-size: 13px;'>{feat['title']}</strong>")
            desc_label = QLabel(f"<span style='color: #666666; font-size: 12px;'>{feat['desc']}</span>")

            card_layout.addWidget(icon_label)
            card_layout.addWidget(title_label)
            card_layout.addWidget(desc_label)
            features_grid.addWidget(card)

        features_layout.addLayout(features_grid)
        layout.addWidget(features_frame)

        # 四步操作流程
        steps_data = [
            {
                "step": 1, "icon": "📂", "title": "选择游戏目录", "color": "#34c759",
                "content": """点击「浏览文件夹...」选择 Minecraft 版本目录，通常位于：
`C:\\Users\\用户名\\AppData\\Roaming\\.minecraft\\versions\\版本名称`

选择后点击「检测」，工具会自动识别：整合包名称、MC版本、加载器类型/版本、模组列表、配置文件夹"""
            },
            {
                "step": 2, "icon": "🔍", "title": "检查模组和配置", "color": "#007aff",
                "content": """**模组列表**：自动筛选服务端兼容模组，客户端模组默认不勾选，支持按类型筛选

**配置文件夹**：勾选要复制的文件夹，支持全选/取消全选，可手动添加自定义文件夹

**服务器配置**：设置图标（64×64 PNG）和 MOTD（支持颜色代码 &a/&c 等）"""
            },
            {
                "step": 3, "icon": "🚀", "title": "开始生成", "color": "#af52de",
                "content": """点击「开始生成」，设置输出目录、内存分配、Java 版本

工具将自动完成：
1. 下载服务端安装器或核心文件
2. 复制选中的模组和配置
3. 生成启动脚本（start.bat / start.sh）
4. 生成 README.md 说明文档"""
            },
            {
                "step": 4, "icon": "✅", "title": "完成后续步骤", "color": "#ff9500",
                "content": """**Forge / NeoForge 用户**：先运行安装器 `java -jar xxx-installer.jar --installServer`，再启动

**Fabric / Vanilla 用户**：直接运行启动脚本 `start.bat`（Windows）或 `./start.sh`（Linux/Mac）

点击「打开启动说明」查看详细指南"""
            },
        ]

        for step_data in steps_data:
            step_card = self._create_step_card(**step_data)
            layout.addWidget(step_card)

        scroll.setWidget(content)
        QTimer.singleShot(100, lambda: scroll.verticalScrollBar().setValue(0))
        return scroll

    def _create_step_card(self, step: int, title: str, icon: str, color: str, content: str):
        """创建步骤卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border-radius: 10px;
                border-left: 4px solid {color};
                padding: 12px 16px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # 标题行
        header = QHBoxLayout()
        header.setSpacing(10)

        step_badge = QLabel(f"<span style='background-color: {color}; color: white; "
                           f"border-radius: 50%; width: 26px; height: 26px; "
                           f"display: inline-flex; align-items: center; "
                           f"justify-content: center; font-weight: bold; font-size: 12px;'>{step}</span>")
        step_badge.setAlignment(Qt.AlignCenter)
        header.addWidget(step_badge)

        icon_label = QLabel(f"<span style='font-size: 18px;'>{icon}</span>")
        header.addWidget(icon_label)

        title_label = QLabel(f"<strong style='color: #1c1c1e; font-size: 14px;'>{title}</strong>")
        header.addWidget(title_label)
        header.addStretch()

        layout.addLayout(header)

        # 内容
        content_edit = QTextEdit()
        content_edit.setReadOnly(True)
        content_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                color: #333333;
                line-height: 1.5;
            }
        """)
        content_edit.setText(content)
        content_edit.setMaximumHeight(140)
        layout.addWidget(content_edit)

        return card

    def _build_server_guide(self):
        """服务器搭建指南页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 标题
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5cb885, stop:1 #6d9fcf);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        title_layout = QVBoxLayout(title_frame)
        title = QLabel("🖥️ Minecraft 服务器搭建指南")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold; margin: 0;")
        desc = QLabel("搭建和管理 Minecraft 服务器的完整指南")
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px;")
        title_layout.addWidget(title)
        title_layout.addWidget(desc)
        layout.addWidget(title_frame)

        cards_data = [
            {
                "icon": "📋", "title": "准备工作", "color": "#34c759",
                "content": """**1. 安装 Java**
Minecraft 1.18+ 需要 Java 17 或更高版本
- Windows：从 [Adoptium](https://adoptium.net/) 下载
- Linux：`sudo apt install openjdk-17-jre`
- Mac：使用 Homebrew 或从 Adoptium 下载

**2. 端口准备**
- 路由器设置端口转发（默认 25565）
- 防火墙允许 Minecraft 服务
- 云服务器需配置安全组规则"""
            },
            {
                "icon": "🚀", "title": "启动服务器", "color": "#007aff",
                "content": """**Windows**：双击 `start.bat`

**Linux / Mac**：
```bash
chmod +x start.sh
./start.sh
```

**手动启动**：
```bash
java -Xmx4G -Xms2G -jar server.jar nogui
```
参数：-Xmx 最大内存 / -Xms 最小内存 / nogui 无界面

**首次启动**：生成 eula.txt 后需将 `eula=false` 改为 `eula=true`"""
            },
            {
                "icon": "⚙️", "title": "服务器配置", "color": "#af52de",
                "content": """**server.properties 常用配置**

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| server-port | 25565 | 服务器端口 |
| motd | A Minecraft Server | 服务器名称 |
| max-players | 100 | 最大玩家数 |
| online-mode | true | 正版验证 |
| difficulty | easy | 游戏难度 |
| view-distance | 10 | 视野距离 |
| pvp | true | 是否开启 PVP |

**MOTD 颜色代码**：使用 `&` + 代码，如 `&a` 绿色、`&c` 红色、`&e` 黄色等"""
            },
            {
                "icon": "🔧", "title": "管理员命令", "color": "#ff9500",
                "content": """**游戏内命令**（需 OP 权限）

| 命令 | 说明 |
|------|------|
| /op <玩家> | 授予管理员 |
| /deop <玩家> | 撤销管理员 |
| /ban <玩家> | 封禁玩家 |
| /unban <玩家> | 解封玩家 |
| /kick <玩家> | 踢出玩家 |
| /stop | 停止服务器 |
| /whitelist add <玩家> | 添加白名单 |
| /save-all | 保存世界 |
| /say <消息> | 发送公告 |

**控制台命令**：list（列玩家）、stop（停止）、save-all（保存）"""
            },
        ]

        for card_data in cards_data:
            info_card = self._create_info_card(**card_data)
            layout.addWidget(info_card)

        scroll.setWidget(content)
        return scroll

    def _create_info_card(self, icon: str, title: str, color: str, content: str):
        """创建信息卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border-radius: 10px;
                padding: 14px 16px;
                border-top: 3px solid {color};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        title_label = QLabel(f"<span style='font-size: 20px; margin-right: 8px;'>{icon}</span>"
                           f"<strong style='color: #1c1c1e; font-size: 15px;'>{title}</strong>")
        layout.addWidget(title_label)

        content_edit = QTextEdit()
        content_edit.setReadOnly(True)
        content_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                color: #333333;
                line-height: 1.5;
            }
        """)
        content_edit.setText(content)
        content_edit.setMaximumHeight(200)
        layout.addWidget(content_edit)

        return card

    def _build_faq(self):
        """常见问题页面"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 标题
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e89b4d, stop:1 #d47a5c);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        title_layout = QVBoxLayout(title_frame)
        title = QLabel("❓ 常见问题")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold; margin: 0;")
        desc = QLabel("常见问题和解决方案")
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px;")
        title_layout.addWidget(title)
        title_layout.addWidget(desc)
        layout.addWidget(title_frame)

        faqs = [
            ("玩家无法连接服务器？",
             "检查：1. 服务器是否正在运行；2. 端口是否开放（默认25565）；"
             "3. online-mode 设置（正版true/离线false）；4. IP 地址和端口是否正确；"
             "5. 路由器端口转发和防火墙设置"),
            ("内存不足错误？",
             "解决方法：1. 编辑 user_jvm_args.txt 调小 -Xmx；"
             "2. 关闭其他占用内存的程序；3. 增加物理内存。"
             "推荐：10人内 4GB，20-30人 8GB，50+人 16GB+"),
            ("Forge/NeoForge 安装器失败？",
             "排查：1. Java 版本是否正确（推荐17+）；"
             "2. 安装器文件是否完整（重新下载）；3. 是否以管理员运行；"
             "4. 磁盘空间是否足够；5. 查看控制台错误详情"),
            ("模组加载失败？",
             "排查步骤：1. 检查模组版本兼容性；2. 确认所有依赖模组已安装；"
             "3. 查看 logs/latest.log；4. 逐个移除模组找出问题项；"
             "5. 更新模组到最新版本"),
            ("如何备份服务器？",
             "步骤：1. /stop 停止服务器；2. 复制整个服务器目录；"
             "3. 压缩备份文件；4. 存放到安全位置。"
             "建议频率：小型服务器每天，中型每6小时，大型每1-2小时"),
            ("如何更新服务端？",
             "步骤：1. 备份整个服务器目录；2. 下载新版本安装器/核心；"
             "3. 运行安装器（如需要）；4. 更新模组到兼容版本；5. 测试启动。"
             "注意：不要覆盖 world/ 目录"),
            ("白名单如何设置？",
             "1. server.properties 中设置 white-list=true；2. 重启服务器；"
             "3. 使用 /whitelist add <玩家> 添加；/whitelist list 查看；"
             "/whitelist remove 移除；/whitelist reload 重新加载"),
            ("服务端崩溃怎么办？",
             "排查：1. 查看 crash-reports/ 和 logs/latest.log；"
             "2. 常见原因：内存不足、模组冲突、Java版本问题、世界损坏；"
             "3. 可用 java -jar server.jar --forceUpgrade 修复世界；"
             "4. 无法解决时从备份恢复"),
        ]

        for q, a in faqs:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 10px 14px;
                    border: 1px solid #e8e8ed;
                }
            """)

            layout_card = QVBoxLayout(card)
            layout_card.setSpacing(6)

            q_label = QLabel(f"<span style='color: #2382DE; font-size: 13px; font-weight: 600;'>Q: </span>"
                           f"<span style='color: #1c1c1e; font-size: 13px; font-weight: 500;'>{q}</span>")
            layout_card.addWidget(q_label)

            a_label = QLabel(f"<span style='color: #48484a; font-size: 12px; line-height: 1.5;'>{a}</span>")
            a_label.setWordWrap(True)
            layout_card.addWidget(a_label)

            layout.addWidget(card)

        scroll.setWidget(content)
        return scroll
