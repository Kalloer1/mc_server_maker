
# 此程序全由豆包制作
# 人类未参与任何制作过程
# 遇到问题请问豆包
# MC Server Maker

> 快速将 Minecraft 整合包转换为服务端的工具

## 功能特性

- 🎯 **自动检测** — 智能识别游戏目录、MC 版本、加载器类型和版本
- 📦 **模组筛选** — 自动分析模组客户端/服务端类型，默认排除客户端模组
- 📂 **灵活配置** — 可选择要复制的配置文件夹，支持手动添加
- 🖼️ **服务器配置** — 自定义服务器图标（64×64 PNG）和 MOTD（支持颜色代码）
- 📄 **文档生成** — 自动生成启动说明文档（README.md）
- 🎨 **内置教程** — 集成软件使用教程和服务器搭建指南

## 支持的加载器

| 加载器 | 状态 | 说明 |
|--------|------|------|
| Forge | ✅ | 下载安装器，需手动运行 |
| NeoForge | ✅ | 下载安装器，需手动运行 |
| Fabric | ✅ | 直接下载服务端核心 |
| Vanilla | ✅ | 直接下载原版服务端 |

## 下载源

- 官方源（Minecraft Forge、NeoForge、Fabric、Mojang）
- BMCLAPI 镜像源（国内加速）

## 系统要求

- **操作系统**：Windows 10/11 / Linux / macOS
- **Python**：3.9+
- **Java**：17+（运行 Minecraft 1.18+ 服务端需要）
- **内存**：建议至少 4GB

## 快速开始

### 方式一：直接运行 EXE（Windows）

1. 下载 `MCServerMaker.exe`
2. 双击运行
3. 按照教程操作

### 方式二：源码运行

```bash
# 克隆项目
git clone <repository-url>
cd maker

# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

## 使用流程

### Step 1：选择游戏目录

点击「📂 浏览文件夹...」选择 Minecraft 版本目录，通常位于：
- Windows：`C:\Users\用户名\AppData\Roaming\.minecraft\versions\版本名称`

点击「🔍 检测」开始分析，工具会自动识别：
- 整合包名称
- MC 版本号
- 加载器类型和版本
- 模组列表和配置文件夹

### Step 2：检查模组和配置

- **模组列表**：查看自动筛选后的模组，客户端模组默认不勾选
- **配置文件夹**：勾选要复制到服务端的文件夹
- **服务器配置**：设置图标和 MOTD

### Step 3：开始生成

- 选择输出目录（留空自动生成）
- 设置内存分配
- 选择 Java 版本

点击「🚀 开始生成」，工具将自动：
1. 下载服务端安装器或核心文件
2. 复制选中的模组和配置
3. 生成启动脚本
4. 生成说明文档

### Step 4：后续步骤

**Forge / NeoForge**：先运行安装器
```bash
java -jar xxx-installer.jar --installServer
```

**Fabric / Vanilla**：直接运行启动脚本
```bash
start.bat      # Windows
./start.sh     # Linux/Mac
```

## MOTD 颜色代码

在 MOTD 中使用 `&` + 颜色代码：

| 代码 | 颜色 | 代码 | 颜色 |
|------|------|------|------|
| &0 | 黑色 | &8 | 深灰 |
| &1 | 深蓝 | &9 | 蓝色 |
| &2 | 深绿 | &a | 绿色 |
| &3 | 深青 | &b | 青色 |
| &4 | 深红 | &c | 红色 |
| &5 | 深紫 | &d | 紫色 |
| &6 | 橙色 | &e | 黄色 |
| &7 | 浅灰 | &f | 白色 |

格式代码：`&l` 加粗、`&o` 斜体、`&n` 下划线、`&m` 删除线、`&r` 重置

## 项目结构

```
maker/
├── main.py                  # 程序入口
├── requirements.txt         # Python 依赖
├── theme/
│   └── theme.qss           # 全局样式表
├── data/
│   ├── readme_template.md  # README 模板
│   └── user_config.json    # 用户配置（运行时生成）
├── ui/
│   ├── main_window.py       # 主窗口
│   ├── tutorial_window.py   # 教程窗口
│   └── worker.py            # 后台工作线程
├── core/
│   ├── generator.py         # 服务端生成逻辑
│   ├── scanner.py           # 游戏目录扫描
│   ├── server_provider.py   # 服务端下载
│   ├── java_manager.py      # Java 检测
│   └── mod_db.py            # 模组数据库
└── utils/
    ├── constants.py         # 常量配置
    └── motd_colors.py       # MOTD 颜色解析
```

## 打包 EXE

使用 PyInstaller 打包：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包（单文件模式）
pyinstaller --onefile --windowed --name MCServerMaker main.py

# 打包（目录模式，推荐用于包含资源文件）
pyinstaller --onedir --windowed --name MCServerMaker main.py
```

## 常见问题

### Q: 玩家无法连接服务器？

检查：1. 服务器是否运行；2. 端口是否开放；3. online-mode 设置；4. IP 地址；5. 防火墙设置

### Q: Forge/NeoForge 安装器失败？

排查：1. Java 版本（推荐17+）；2. 安装器文件完整性；3. 管理员权限；4. 磁盘空间

### Q: 内存不足错误？

调整 `user_jvm_args.txt` 中的 `-Xmx` 参数，或增加物理内存

## 许可证

MIT License
