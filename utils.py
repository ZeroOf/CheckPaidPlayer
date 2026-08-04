import os
import sys
import ctypes
from config import CONFUSABLE_MAP

def set_dpi_awareness():
    """ 设置 DPI 感知，使窗口支持系统缩放 """
    try:
        # 模式 2 表示 Per Monitor DPI Aware，能更好地支持系统缩放
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

def get_resource_path(relative_path):
    """ 获取资源的绝对路径，适配打包后的路径 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_variants(text):
    """ 生成可能的识别错误变体 """
    variants = {text}
    
    # 1. 常见的大小写变体
    variants.add(text.lower())
    variants.add(text.upper())

    # 2. 基于映射的替换 (处理英文和数字)
    chars = list(text)
    for i, char in enumerate(chars):
        if char in CONFUSABLE_MAP:
            for replacement in CONFUSABLE_MAP[char]:
                new_variant = chars[:]
                new_variant[i] = replacement
                variants.add("".join(new_variant))
        
        # 处理对应的大/小写映射
        elif char.lower() in CONFUSABLE_MAP:
            for replacement in CONFUSABLE_MAP[char.lower()]:
                new_variant = chars[:]
                new_variant[i] = replacement
                variants.add("".join(new_variant))

    # 3. 针对特定词汇的整体替换 (如去除符号)
    stripped = text.replace('丶', '').replace('灬', '').strip()
    if stripped:
        variants.add(stripped)

    return list(variants)

def load_keywords():
    """ 从 paid_player_id.txt 加载原始关键字列表 """
    ids = []
    # 优先尝试从程序运行目录读取（用户修改后的名单）
    local_path = os.path.join(os.path.abspath("."), "paid_player_id.txt")
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                ids = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取本地文件错误: {e}")

    # 如果运行目录没有，尝试从资源目录读取（安装包带的默认名单）
    if not ids:
        resource_path = get_resource_path("paid_player_id.txt")
        if os.path.exists(resource_path):
            try:
                with open(resource_path, 'r', encoding='utf-8') as f:
                    ids = [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"读取资源文件错误: {e}")
            
    if not ids:
        ids = ["素质路人88", "川医声在掏"]
    
    # 去重保留原始顺序
    seen = set()
    unique_ids = []
    has_duplicates = False
    for x in ids:
        if x not in seen:
            unique_ids.append(x)
            seen.add(x)
        else:
            has_duplicates = True
    
    # 如果发现重复，则立即清理并写回文件
    if has_duplicates:
        save_keywords(unique_ids)
        print("已自动清理名单中的重复项。")
        
    return unique_ids

def save_keywords(keywords):
    """ 将关键字列表保存到 paid_player_id.txt """
    file_path = os.path.join(os.path.abspath("."), "paid_player_id.txt")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for kw in keywords:
                f.write(f"{kw}\n")
    except Exception as e:
        print(f"保存文件错误: {e}")

def get_all_match_keywords(original_keywords):
    """ 根据原始名单生成所有可能的匹配项（包括变体） """
    all_matches = set()
    for kw in original_keywords:
        all_matches.update(get_variants(kw))
    return list(all_matches)
