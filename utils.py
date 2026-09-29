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
    import re
    variants = {text}
    
    # 1. 常见的大小写变体
    variants.add(text.lower())
    variants.add(text.upper())

    # 2. 基于映射的替换 (处理英文和数字以及单字替换)
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

    # 3. 处理多字符混淆映射
    for conf_key, replacements in CONFUSABLE_MAP.items():
        if len(conf_key) > 1 and conf_key in text:
            for replacement in replacements:
                variants.add(text.replace(conf_key, replacement))

    # 4. 针对特定词汇的整体替换 (基于映射中为空字符串的项)
    current_text = text
    for char, replacements in CONFUSABLE_MAP.items():
        if '' in replacements:
            current_text = current_text.replace(char, '')
    
    stripped = current_text.strip()
    if stripped and stripped != text:
        variants.add(stripped)

    return list(variants)

def extract_confusable_diffs(s1, s2):
    """
    通过两个用户名对比，自动提取可能被混淆的字符或片段。
    返回列表，每个元素为元组: (src, tgt, type)
    type 取值:
      - 'group': 相互混淆组（如 '8' 与 'B', '声' 与 '生'）
      - 'mapping': 单向/多字符映射（如 'w' 与 'vv'）
      - 'removal': 消除/忽略字符（如 '灬' 与 ''）
    """
    if not s1 or not s2 or s1 == s2:
        return []

    n, m = len(s1), len(s2)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i * 1.01
    for j in range(m + 1):
        dp[0][j] = j * 1.01

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(
                    dp[i - 1][j - 1] + 1.0,  # 替换
                    dp[i - 1][j] + 1.01,     # 删除
                    dp[i][j - 1] + 1.01      # 插入
                )

    # 回溯
    i, j = n, m
    ops = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and s1[i - 1] == s2[j - 1] and abs(dp[i][j] - dp[i - 1][j - 1]) < 1e-5:
            ops.append(('equal', s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and abs(dp[i][j] - (dp[i - 1][j - 1] + 1.0)) < 1e-5:
            ops.append(('replace', s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and abs(dp[i][j] - (dp[i - 1][j] + 1.01)) < 1e-5:
            ops.append(('delete', s1[i - 1], ''))
            i -= 1
        elif j > 0:
            ops.append(('insert', '', s2[j - 1]))
            j -= 1
        else:
            break

    ops.reverse()

    # 合并相邻差异块
    merged = []
    k = 0
    while k < len(ops):
        tag, c1, c2 = ops[k]
        if tag == 'equal':
            k += 1
            continue

        sub1 = [c1] if c1 else []
        sub2 = [c2] if c2 else []
        next_k = k + 1
        while next_k < len(ops) and ops[next_k][0] != 'equal':
            if ops[next_k][1]:
                sub1.append(ops[next_k][1])
            if ops[next_k][2]:
                sub2.append(ops[next_k][2])
            next_k += 1

        str1 = ''.join(sub1)
        str2 = ''.join(sub2)

        if str1 and not str2:
            for ch in str1:
                merged.append((ch, '', 'removal'))
        elif not str1 and str2:
            for ch in str2:
                merged.append((ch, '', 'removal'))
        elif len(str1) == len(str2):
            for ch1, ch2 in zip(str1, str2):
                if ch1 != ch2:
                    merged.append((ch1, ch2, 'group'))
        elif len(str1) == 1 or len(str2) == 1:
            if len(str1) == 1:
                merged.append((str1, str2, 'mapping'))
            else:
                merged.append((str2, str1, 'mapping'))
        else:
            merged.append((str1, str2, 'mapping'))

        k = next_k

    seen = set()
    result = []
    for item in merged:
        key = (item[0], item[1], item[2])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

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
    将 ID 列表记录到历史文件，使用 JSON 格式保存为列表对象：
    [ {"id": "xxx", "ts": 1234567890}, ... ]
    如果 ID 已存在，则刷新其时间戳；最终按时间戳降序保存（最新在前）。
    向后兼容旧的文本格式（id|ts 或单独 id）。
    """
    if not id_list:
        return

    file_path = os.path.join(os.path.abspath("."), history_file)
    import time
    import json
    current_ts = int(time.time())

    # 读取现有历史（支持 JSON 或旧文本格式）
    history = []  # list of {"id":..., "ts":...}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw = f.read().strip()
                if not raw:
                    history = []
                else:
                    try:
                        data = json.loads(raw)
                        # 支持 dict/map 或 list
                        if isinstance(data, dict):
                            for k, v in data.items():
                                try:
                                    ts_val = int(v)
                                except:
                                    ts_val = 0
                                history.append({"id": k, "ts": ts_val})
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "id" in item:
                                    try:
                                        ts_val = int(item.get("ts", 0))
                                    except:
                                        ts_val = 0
                                    history.append({"id": item["id"], "ts": ts_val})
                    except Exception:
                        # 兼容旧的行文本格式
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            if "|" in line:
                                pid, ts = line.rsplit("|", 1)
                                try:
                                    ts_val = int(ts)
                                except:
                                    ts_val = 0
                                history.append({"id": pid, "ts": ts_val})
                            else:
                                history.append({"id": line, "ts": 0})
        except Exception as e:
            print(f"读取历史记录失败: {e}")

    # 合并并刷新时间戳（新出现或重新出现都刷新为 current_ts）
    existing = {item["id"]: int(item.get("ts", 0)) for item in history}
    changed = False
    for pid in id_list:
        if existing.get(pid) != current_ts:
            existing[pid] = current_ts
            changed = True

    # 构造排序后的列表（按 ts 降序）
    new_history = [{"id": k, "ts": v} for k, v in existing.items()]
    new_history.sort(key=lambda x: x["ts"], reverse=True)

    if changed:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_history, f, ensure_ascii=False, indent=2)
            print(f"[{os.path.basename(file_path)}] 更新了历史 ID 记录。")
        except Exception as e:
            print(f"写入历史记录失败: {e}")

def get_all_match_keywords(original_keywords):
    """ 根据原始名单生成所有可能的匹配项（包括变体） """
    all_matches = set()
    for kw in original_keywords:
        all_matches.update(get_variants(kw))
    return list(all_matches)
