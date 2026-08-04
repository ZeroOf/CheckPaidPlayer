import time
import sys
import re
import ctypes
import winsound
import os
from concurrent.futures import ThreadPoolExecutor

try:
    from mss import mss
    from PIL import Image
    import easyocr
    import numpy as np
except ImportError:
    print("请先安装依赖：")
    print("pip install mss pillow easyocr")
    sys.exit(1)

# ================== 配置区 ==================
# 针对你截图的分辨率（3840x2160），请根据实际微调
MONITOR_REGION = (100, 140, 1000, 1100)   # 覆盖近卫+天灾全部玩家名

CHECK_INTERVAL = 1.2          # EasyOCR稍慢，建议1.0~1.5秒
TIMEOUT = 300                 # 300秒超时退出
# ===========================================

def get_resource_path(relative_path):
    """ 获取资源的绝对路径，适配打包后的路径 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def load_keywords():
    """ 从 paid_player_id.txt 加载关键字列表 """
    file_path = get_resource_path("paid_player_id.txt")
    if not os.path.exists(file_path):
        # 尝试从当前目录加载，如果打包时没放进去
        file_path = "paid_player_id.txt"
        
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    else:
        print(f"警告: 未找到 {file_path}，使用内置默认列表")
        return ["素质路人88", "川医声在掏"]

KEYWORDS = load_keywords()

# 初始化 EasyOCR（支持中英文）
print("正在加载 EasyOCR 模型（首次运行需要下载）...")
# 预先指定模型路径，方便打包
model_storage_path = get_resource_path("easyocr_models")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=True, model_storage_directory=model_storage_path) 
print("模型加载完成！\n")

def show_alert(matched_names):
    """线程安全的 Windows 弹窗"""
    msg = "检测到目标玩家！\n\n" + "\n".join(matched_names)
    try:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except:
        print("\a")

    ctypes.windll.user32.MessageBoxW(0, msg, "玩家检测提醒", 0x30 | 0x1000)

def capture_and_ocr():
    with mss() as sct:
        last_matched = set()
        start_time = time.time()

        while True:
            # 检查超时
            elapsed_time = time.time() - start_time
            if elapsed_time > TIMEOUT:
                print(f"[{time.strftime('%H:%M:%S')}] 已监控超过 {TIMEOUT} 秒，程序退出。")
                break

            screenshot = sct.grab(MONITOR_REGION)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            # 转成 numpy 给 EasyOCR
            img_np = np.array(img)

            # EasyOCR 识别（detail=0 只返回文字）
            results = reader.readtext(img_np, detail=0, paragraph=False)

            text = " ".join(results)
            text = re.sub(r'\s+', ' ', text).strip()

            if text:
                print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text}")

                matched = [kw for kw in KEYWORDS if kw.lower() in text.lower()]

                # 只在新匹配到时弹窗
                current = set(matched)
                if current:
                    print(f"【触发提醒】匹配到：{matched}")
                    show_alert(matched)
                    print("检测到关键字，程序即将退出。")
                    break # 检测到关键字后退出
                else:
                    last_matched = set()

            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("Warcraft III 玩家监测程序（EasyOCR 版）")
    print(f"监测区域: {MONITOR_REGION}")
    print(f"监控玩家: {len(KEYWORDS)} 个")
    print(f"监控超时: {TIMEOUT} 秒")
    print("按 Ctrl+C 停止\n")

    try:
        capture_and_ocr()
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"错误: {e}")
    
    # 保持窗口一下，方便看结果
    time.sleep(2)