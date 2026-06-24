# motd_colors.py —— Minecraft MOTD 颜色代码解析
# 职责：
#   1. 解析 Minecraft 颜色代码（§ 或 & 前缀）
#   2. 转换为 HTML 富文本用于预览
#   3. 转换为 server.properties 格式（使用 \u00A7）

from typing import Tuple

# Minecraft 颜色代码映射
# 格式代码: §0-9, §a-f (颜色), §k-o (格式), §r (重置)
MINECRAFT_COLORS = {
    '0': '#000000',  # 黑色 Black
    '1': '#0000AA',  # 深蓝 Dark Blue
    '2': '#00AA00',  # 深绿 Dark Green
    '3': '#00AAAA',  # 深青 Dark Aqua
    '4': '#AA0000',  # 深红 Dark Red
    '5': '#AA00AA',  # 深紫 Dark Purple
    '6': '#FFAA00',  # 金色 Gold
    '7': '#AAAAAA',  # 灰色 Gray
    '8': '#555555',  # 深灰 Dark Gray
    '9': '#5555FF',  # 蓝色 Blue
    'a': '#55FF55',  # 绿色 Green
    'b': '#55FFFF',  # 青色 Aqua
    'c': '#FF5555',  # 红色 Red
    'd': '#FF55FF',  # 粉色 Light Purple
    'e': '#FFFF55',  # 黄色 Yellow
    'f': '#FFFFFF',  # 白色 White
}

# 格式代码
MINECRAFT_FORMATS = {
    'k': 'obfuscated',   # 混淆（闪烁）
    'l': 'bold',         # 加粗
    'm': 'strikethrough', # 删除线
    'n': 'underline',    # 下划线
    'o': 'italic',       # 斜体
    'r': 'reset',        # 重置
}


def parse_motd_to_html(text: str) -> str:
    """
    将 Minecraft MOTD 文本转换为 HTML 富文本。
    支持 § 和 & 作为颜色前缀。
    
    参数：
        text: 原始 MOTD 文本，如 "&cHello &aWorld"
    
    返回：
        HTML 富文本，如 '<span style="color:#FF5555">Hello</span>...'
    """
    if not text:
        return ""
    
    result = []
    current_style = {}
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # 检查颜色代码前缀
        if char in ('§', '&', '\\'):
            # 处理转义的 Unicode 格式 \u00A7
            if char == '\\' and i + 5 < len(text) and text[i:i+6].lower() == '\\u00a7':
                code_char = text[i+6] if i + 6 < len(text) else None
                if code_char and (code_char in MINECRAFT_COLORS or code_char in MINECRAFT_FORMATS):
                    if code_char == 'r':
                        current_style = {}
                    elif code_char in MINECRAFT_COLORS:
                        current_style['color'] = MINECRAFT_COLORS[code_char]
                        # 重置格式但保留颜色
                        current_style.pop('bold', None)
                        current_style.pop('italic', None)
                        current_style.pop('underline', None)
                        current_style.pop('strikethrough', None)
                    elif code_char in MINECRAFT_FORMATS:
                        if code_char != 'r':
                            current_style[MINECRAFT_FORMATS[code_char]] = True
                    i += 7
                    continue
            
            # 处理 § 或 & 前缀
            if char in ('§', '&') and i + 1 < len(text):
                code_char = text[i + 1]
                if code_char in MINECRAFT_COLORS or code_char in MINECRAFT_FORMATS:
                    if code_char == 'r':
                        current_style = {}
                    elif code_char in MINECRAFT_COLORS:
                        current_style['color'] = MINECRAFT_COLORS[code_char]
                    elif code_char in MINECRAFT_FORMATS:
                        if code_char != 'r':
                            current_style[MINECRAFT_FORMATS[code_char]] = True
                    i += 2
                    continue
        
        # 普通字符，应用当前样式
        if current_style:
            style_str = ""
            if 'color' in current_style:
                style_str += f"color:{current_style['color']};"
            if current_style.get('bold'):
                style_str += "font-weight:bold;"
            if current_style.get('italic'):
                style_str += "font-style:italic;"
            if current_style.get('underline'):
                style_str += "text-decoration:underline;"
            if current_style.get('strikethrough'):
                style_str += "text-decoration:line-through;"
            if current_style.get('obfuscated'):
                # 混淆效果用闪烁模拟
                style_str += "animation:blink 0.5s infinite;"
            
            result.append(f'<span style="{style_str}">{char}</span>')
        else:
            result.append(char)
        
        i += 1
    
    return ''.join(result)


def convert_motd_to_server_properties(text: str) -> str:
    """
    将用户输入的 MOTD 转换为 server.properties 格式。
    & 前缀转换为 \u00A7（Unicode 格式）。
    
    参数：
        text: 用户输入，如 "&cHello &aWorld"
    
    返回：
        server.properties 格式，如 "\\u00A7cHello \\u00A7aWorld"
    """
    if not text:
        return ""
    
    result = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # 将 & 或 § 转换为 \u00A7
        if char in ('§', '&') and i + 1 < len(text):
            code_char = text[i + 1]
            if code_char in MINECRAFT_COLORS or code_char in MINECRAFT_FORMATS or code_char == 'r':
                result.append('\\u00A7')
                result.append(code_char)
                i += 2
                continue
        
        # 已经是 Unicode 格式的保持不变
        if char == '\\' and i + 5 < len(text) and text[i:i+6].lower() == '\\u00a7':
            result.append(text[i:i+8])  # \u00A7 + code
            i += 8
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


def convert_server_properties_to_display(text: str) -> str:
    """
    将 server.properties 格式的 MOTD 转换为显示格式（使用 § 前缀）。
    
    参数：
        text: server.properties 格式，如 "\\u00A7cHello"
    
    返回：
        显示格式，如 "§cHello"
    """
    if not text:
        return ""
    
    result = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # \u00A7 转换为 §
        if char == '\\' and i + 5 < len(text) and text[i:i+6].lower() == '\\u00a7':
            result.append('§')
            if i + 6 < len(text):
                result.append(text[i + 6])
            i += 7
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


def strip_color_codes(text: str) -> str:
    """
    移除所有颜色代码，返回纯文本。
    
    参数：
        text: 包含颜色代码的文本
    
    返回：
        纯文本
    """
    if not text:
        return ""
    
    result = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # 跳过颜色代码
        if char in ('§', '&') and i + 1 < len(text):
            code_char = text[i + 1]
            if code_char in MINECRAFT_COLORS or code_char in MINECRAFT_FORMATS or code_char == 'r':
                i += 2
                continue
        
        # 跳过 Unicode 格式的颜色代码
        if char == '\\' and i + 5 < len(text) and text[i:i+6].lower() == '\\u00a7':
            i += 7
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)


def get_color_preview_html() -> str:
    """
    生成颜色代码预览的 HTML 表格。
    用于帮助用户了解可用的颜色代码。
    
    返回：
        HTML 表格字符串
    """
    rows = []
    for code, color in MINECRAFT_COLORS.items():
        rows.append(
            f'<span style="color:{color};font-weight:bold;">&{code}</span> '
            f'<span style="color:{color};">示例</span>'
        )
    return ' | '.join(rows)