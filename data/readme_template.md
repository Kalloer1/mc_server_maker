# Minecraft {loader_name} 服务端

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
编辑此文件来配置服务器的基本设置。

**常用配置项：**

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server-port` | 25565 | 服务器端口 |
| `motd` | A Minecraft Server | 服务器名称（支持颜色代码） |
| `max-players` | 100 | 最大玩家数 |
| `online-mode` | true | true=正版验证，false=离线模式 |
| `difficulty` | easy | 游戏难度 |
| `view-distance` | 10 | 视野距离 |

**示例配置：**
```properties
server-port=25565
motd=&a我的服务器 &c欢迎加入！
max-players=20
online-mode=false
pvp=true
```

> **提示**：修改配置后需要重启服务器才能生效。

### eula.txt（用户协议）
本文件已自动设置为同意 EULA（`eula=true`）。

### user_jvm_args.txt（JVM 参数）
调整服务器内存分配和 JVM 参数。

**示例配置：**
```
# 最小内存 2GB，最大内存 4GB
-Xms2G
-Xmx4G
```

---

## 端口设置

服务器默认使用端口：**25565**

如需修改：
1. 编辑 `server.properties`
2. 找到 `server-port=25565`，修改为其他端口
3. 确保防火墙允许新端口的 TCP 连接

---

## 管理员命令

在游戏内聊天框或服务器控制台执行：

| 命令 | 说明 |
|------|------|
| `/op <玩家名>` | 授予管理员权限 |
| `/deop <玩家名>` | 撤销管理员权限 |
| `/ban <玩家名>` | 封禁玩家 |
| `/unban <玩家名>` | 解封玩家 |
| `/kick <玩家名>` | 踢出玩家 |
| `/stop` | 停止服务器 |
| `/whitelist add <玩家名>` | 添加白名单 |
| `/whitelist remove <玩家名>` | 移除白名单 |

---

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `start.bat` / `start.sh` | 启动脚本 |
| `server.jar` | 服务端核心文件（安装器安装后生成） |
| `{installer_filename}` | 服务端安装器（Forge/NeoForge） |
| `libraries/` | 游戏依赖库（安装器安装后生成） |
| `mods/` | 服务端模组（已筛选，仅服务端模组） |
| `config/` | 模组配置文件 |
| `world/` | 游戏世界数据（首次启动后生成） |
| `server.properties` | 服务器配置文件 |
| `eula.txt` | EULA 协议 |
| `user_jvm_args.txt` | JVM 参数配置 |
| `README.md` | 本说明文档 |

---

## 安全建议

1. **定期备份**：定期备份 `world` 目录
2. **权限管理**：谨慎分配 op 权限
3. **正版模式**：建议使用 `online-mode=true` 正版验证
4. **防火墙**：确保服务器端口已开放
5. **更新**：定期检查并更新服务端版本

---

## 常见问题

### Q: 玩家无法连接服务器？
- 检查服务器是否正在运行
- 检查端口是否正确开放（默认 25565）
- 检查 `online-mode` 设置是否符合需求
- 检查防火墙设置

### Q: 内存不足错误？
- 编辑 `user_jvm_args.txt`
- 减小 `-Xmx` 值或增加物理内存

### Q: 如何添加模组？
- 将模组 JAR 文件放入 `mods` 目录
- 重启服务器
- 注意：只添加服务端兼容的模组

### Q: Forge/NeoForge 安装器运行失败？
- 确保使用正确的 Java 版本（推荐 Java 17 或更高）
- 检查安装器文件是否完整
- 尝试重新下载安装器

---

## 技术支持

如遇到问题，请检查：
1. `logs/` 目录下的日志文件
2. Java 版本（推荐 Java 17 或更高）
3. 防火墙和网络设置

---
*MC Server Maker - 让服务端部署更简单*
