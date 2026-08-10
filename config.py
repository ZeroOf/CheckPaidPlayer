import os
import json

# 监测区域：左，上，宽，高
MONITOR_REGION = {"top": 140, "left": 100, "width": 900, "height": 960}
CHECK_INTERVAL = 0.5
TIMEOUT_SECONDS = 300  # 启动后 300s 未检测到目标则停止

# 默认混淆字符映射表
DEFAULT_CONFUSABLE_MAP = {
    'l': ['1', 'I', 'i'],
    '1': ['l', 'I'],
    'I': ['l', '1', 'i'],
    '0': ['o', 'O'],
    'o': ['0', 'O'],
    'O': ['0', 'o'],
    'u': ['v', 'n'],
    'v': ['u', 'n'],
    'n': ['u', 'v'],
    'w': ['vv', 'v v'],
    '涛': ['寿'],
    '寿': ['涛'],
    '昊': ['吴'],
    '吴': ['昊'],
    '灬': [''],
    '丶': [''],
    '十': ['+'],
    '+': ['十'],
    '丿': [' )']
}

def load_confusable_map():
    """ 从配置文件加载混淆映射表 """
    map_file = "confusable_map.json"
    # 打包后的路径处理
    import sys
    if hasattr(sys, '_MEIPASS'):
        bundle_path = os.path.join(sys._MEIPASS, map_file)
    else:
        bundle_path = os.path.join(os.path.abspath("."), map_file)
    
    # 优先使用运行目录下的配置文件（允许用户修改）
    local_path = os.path.join(os.path.abspath("."), map_file)
    
    target_path = local_path if os.path.exists(local_path) else bundle_path
    
    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载混淆配置失败: {e}")
    
    # 如果都没有，则创建默认配置文件
    try:
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFUSABLE_MAP, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"创建默认混淆配置失败: {e}")
        
    return DEFAULT_CONFUSABLE_MAP

CONFUSABLE_MAP = load_confusable_map()

# 历史记录配置
HISTORY_FILE = "history_id.txt"
HISTORY_COUNT_TRIGGER = 11
