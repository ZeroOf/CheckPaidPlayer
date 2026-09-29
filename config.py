import os
import json

# 监测区域：左，上，宽，高
MONITOR_REGION = {"top": 140, "left": 100, "width": 900, "height": 960}
CHECK_INTERVAL = 0.5
TIMEOUT_SECONDS = 120 #启动后 120s 未检测到目标则停止

import copy

# 默认结构化混淆配置（无冗余存储）
DEFAULT_CONFUSABLE_CONFIG = {
    "groups": [
        ["l", "1", "I", "i"],
        ["0", "o", "O"],
        ["u", "v", "n"],
        ["涛", "寿"],
        ["昊", "吴"],
        ["十", "+"],
        ["J", "」"],
        ["5", "s"],
        ["千", "干"],
        ["四", "D", "凹"],
        ["2", "z"]
    ],
    "mappings": {
        "w": ["vv", "v v"],
        "丿": [" )"]
    },
    "removals": [
        "灬",
        "丶"
    ]
}

def build_runtime_confusable_map(config_data):
    """
    将结构化混淆配置（groups, mappings, removals）转换为运行时的单字/多字替换映射字典。
    """
    if not isinstance(config_data, dict):
        return {}

    # 如果本身是旧格式的扁平字典（没有 groups/mappings/removals 字段）
    if "groups" not in config_data and "mappings" not in config_data and "removals" not in config_data:
        return copy.deepcopy(config_data)

    runtime_map = {}

    # 1. 解析互混淆分组 (groups)
    groups = config_data.get("groups", [])
    for group in groups:
        if not isinstance(group, list):
            continue
        unique_chars = []
        for c in group:
            if c and c not in unique_chars:
                unique_chars.append(c)
        for c in unique_chars:
            if c not in runtime_map:
                runtime_map[c] = []
            for other in unique_chars:
                if other != c and other not in runtime_map[c]:
                    runtime_map[c].append(other)

    # 2. 解析单向替换映射 (mappings)
    mappings = config_data.get("mappings", {})
    if isinstance(mappings, dict):
        for k, v_list in mappings.items():
            if not k:
                continue
            if k not in runtime_map:
                runtime_map[k] = []
            if isinstance(v_list, list):
                for v in v_list:
                    if v not in runtime_map[k]:
                        runtime_map[k].append(v)
            elif isinstance(v_list, str):
                if v_list not in runtime_map[k]:
                    runtime_map[k].append(v_list)

    # 3. 解析消除字符 (removals)
    removals = config_data.get("removals", [])
    if isinstance(removals, list):
        for r in removals:
            if r:
                if r not in runtime_map:
                    runtime_map[r] = []
                if "" not in runtime_map[r]:
                    runtime_map[r].append("")

    return runtime_map

def normalize_confusable_data(data):
    """
    规范化混淆数据结构：若为旧扁平字典则自动转换为结构化数据。
    """
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_CONFUSABLE_CONFIG)

    if "groups" in data or "mappings" in data or "removals" in data:
        return {
            "groups": data.get("groups", []),
            "mappings": data.get("mappings", {}),
            "removals": data.get("removals", [])
        }

    # 从旧格式字典转换
    removals = []
    directed_mappings = {}
    graph = {}

    for key, val_list in data.items():
        if not isinstance(val_list, list):
            continue
        if val_list == [""] or "" in val_list:
            if key not in removals:
                removals.append(key)

        for val in val_list:
            if val == "":
                continue
            reverse_list = data.get(val, [])
            if key in reverse_list and len(key) == 1 and len(val) == 1:
                graph.setdefault(key, set()).add(val)
                graph.setdefault(val, set()).add(key)
            else:
                if key not in directed_mappings:
                    directed_mappings[key] = []
                if val not in directed_mappings[key]:
                    directed_mappings[key].append(val)

    visited = set()
    groups = []
    for node in graph:
        if node not in visited:
            component = []
            queue = [node]
            visited.add(node)
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in graph.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            if len(component) > 1:
                groups.append(component)

    return {
        "groups": groups,
        "mappings": directed_mappings,
        "removals": removals
    }

# 默认混淆字符映射表（扁平字典，向后兼容）
DEFAULT_CONFUSABLE_MAP = build_runtime_confusable_map(DEFAULT_CONFUSABLE_CONFIG)

def load_confusable_config():
    """ 从配置文件加载结构化的混淆配置数据 """
    map_file = "confusable_map.json"
    import sys
    if hasattr(sys, '_MEIPASS'):
        bundle_path = os.path.join(sys._MEIPASS, map_file)
    else:
        bundle_path = os.path.join(os.path.abspath("."), map_file)

    local_path = os.path.join(os.path.abspath("."), map_file)
    target_path = local_path if os.path.exists(local_path) else bundle_path

    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                return normalize_confusable_data(raw_data)
        except Exception as e:
            print(f"加载混淆配置失败: {e}")

    try:
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFUSABLE_CONFIG, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"创建默认混淆配置失败: {e}")

    return copy.deepcopy(DEFAULT_CONFUSABLE_CONFIG)

def save_confusable_config(config_data):
    """ 将结构化混淆配置保存到 confusable_map.json 并同步更新全局 CONFUSABLE_MAP """
    map_file = "confusable_map.json"
    local_path = os.path.join(os.path.abspath("."), map_file)
    structured_data = normalize_confusable_data(config_data)
    try:
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存混淆配置失败: {e}")
        raise e

    global CONFUSABLE_MAP
    CONFUSABLE_MAP.clear()
    CONFUSABLE_MAP.update(build_runtime_confusable_map(structured_data))
    return True

def load_confusable_map():
    """ 从配置文件加载混淆映射表（返回运行时字典，保持兼容） """
    config_data = load_confusable_config()
    return build_runtime_confusable_map(config_data)

def save_confusable_map(data):
    """ 保存混淆映射表并同步更新全局 CONFUSABLE_MAP """
    if isinstance(data, dict) and ("groups" in data or "mappings" in data or "removals" in data):
        return save_confusable_config(data)
    # 如果是旧字典格式，先规范化为结构化数据后保存
    structured_data = normalize_confusable_data(data)
    return save_confusable_config(structured_data)

def reload_confusable_map():
    """ 重新加载混淆映射表并同步更新 CONFUSABLE_MAP """
    config_data = load_confusable_config()
    global CONFUSABLE_MAP
    CONFUSABLE_MAP.clear()
    CONFUSABLE_MAP.update(build_runtime_confusable_map(config_data))
    return CONFUSABLE_MAP

CONFUSABLE_MAP = load_confusable_map()

# 历史记录配置
# 使用 JSON 格式存储历史记录以便更可靠、可扩展
HISTORY_FILE = "history_id.json"
HISTORY_COUNT_TRIGGER = 11
