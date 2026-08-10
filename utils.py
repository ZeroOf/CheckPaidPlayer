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

    # 3. 针对特定词汇的整体替换 (基于映射中为空字符串的项)
    current_text = text
    for char, replacements in CONFUSABLE_MAP.items():
        if '' in replacements:
            current_text = current_text.replace(char, '')
    
    stripped = current_text.strip()
    if stripped and stripped != text:
        variants.add(stripped)

    return list(variants)

import json

def load_player_data():
    """ 从 player_list.json 加载玩家数据，支持分组 """
    # 数据结构: {"groups": {"group_name": ["id1", "id2"], ...}}
    file_name = "player_list.json"
    local_path = os.path.join(os.path.abspath("."), file_name)
    data = None

    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"读取本地 JSON 错误: {e}")

    if not data:
        resource_path = get_resource_path(file_name)
        if os.path.exists(resource_path):
            try:
                with open(resource_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"读取资源 JSON 错误: {e}")

    # 兼容旧版本 txt 协议迁移
    if not data:
        old_ids = load_keywords_legacy()
        data = {"groups": {}}
        for item in old_ids:
            if ":" in item:
                group, pid = item.split(":", 1)
            else:
                group, pid = "默认", item
            if group not in data["groups"]:
                data["groups"][group] = []
            if pid not in data["groups"][group]:
                data["groups"][group].append(pid)
        if data["groups"]:
            save_player_data(data)

    if not data or not data.get("groups"):
        data = {"groups": {"默认": ["素质路人88", "川医声在掏"]}}
    
    return data

def save_player_data(data):
    """ 将玩家数据保存到 player_list.json """
    file_path = os.path.join(os.path.abspath("."), "player_list.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存 JSON 错误: {e}")

def load_keywords_legacy():
    """ 旧版 txt 名单加载逻辑，仅用于迁移 """
    grouped_ids = []
    local_path = os.path.join(os.path.abspath("."), "paid_player_id.txt")
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                grouped_ids = [line.strip() for line in f if line.strip()]
        except Exception:
            pass
    return grouped_ids

def load_keywords():
    """ 
    重新封装 load_keywords 以匹配旧的调用约定，但内部使用新协议。
    返回格式: ["分组:ID", ...]
    """
    data = load_player_data()
    result = []
    for group, pids in data["groups"].items():
        for pid in pids:
            result.append(f"{group}:{pid}")
    return result

def save_keywords(grouped_keywords):
    """
    重新封装 save_keywords 以匹配旧的调用约定，但内部使用新协议。
    """
    data = {"groups": {}}
    for item in grouped_keywords:
        if ":" in item:
            group, pid = item.split(":", 1)
        else:
            group, pid = "默认", item
        if group not in data["groups"]:
            data["groups"][group] = []
        if pid not in data["groups"][group]:
            data["groups"][group].append(pid)
    save_player_data(data)

def record_history_ids(id_list, history_file):
    """ 
    将 ID 列表记录到历史文件，记录格式为 ID|timestamp。
    如果 ID 已存在，则更新其时间戳。
    """
    if not id_list:
        return

    file_path = os.path.join(os.path.abspath("."), history_file)
    import time
    current_ts = int(time.time())
    
    # 读取所有记录: {id: timestamp}
    history_data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if "|" in line:
                        pid, ts = line.rsplit("|", 1)
                        history_data[pid] = ts
                    elif line:
                        history_data[line] = str(current_ts)
        except Exception as e:
            print(f"读取历史记录失败: {e}")

    # 更新或添加新 ID
    changed = False
    for pid in id_list:
        history_data[pid] = str(current_ts)
        changed = True

    if changed:
        try:
            # 写入文件，按时间戳降序排序（可选，此处直接覆盖写入即可，导入时排序更灵活）
            # 为了方便读取，保持格式一致
            with open(file_path, 'w', encoding='utf-8') as f:
                for pid, ts in history_data.items():
                    f.write(f"{pid}|{ts}\n")
            print(f"[{os.path.basename(file_path)}] 更新了历史 ID 记录。")
        except Exception as e:
            print(f"写入历史记录失败: {e}")

def get_all_match_keywords(original_keywords):
    """ 根据原始名单生成所有可能的匹配项（包括变体） """
    all_matches = set()
    for kw in original_keywords:
        all_matches.update(get_variants(kw))
    return list(all_matches)
