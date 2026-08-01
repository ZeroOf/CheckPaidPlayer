import ctypes
import time
import tkinter as tk
from tkinter import messagebox
import threading
import sys
import re

import winsound
from pathlib import Path

try:
    from mss import mss
    from PIL import Image, ImageEnhance, ImageOps, ImageFilter
    import pytesseract
except ImportError:
    print("缺少依赖库，请先安装：")
    print("pip install mss pillow pytesseract")
    sys.exit(1)

# ================== 配置区（已根据图片适配） ==================
# 监测区域（针对 3840x2160 分辨率的左边玩家列表，按实际分辨率自行微调）
# 格式：(left, top, right, bottom)
MONITOR_REGION = (80, 120, 1040, 1100)   # 覆盖近卫+天灾玩家名字区域

KEYWORDS_FILE = Path(__file__).with_name("paid_player_id.txt")

def load_keywords(file_path):
    """从文件加载要监控的玩家名，一行一个，自动去重并忽略空行"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            keywords = []
            seen = set()

            for line in f:
                name = line.strip()
                if not name:
                    continue

                key = name.lower()
                if key not in seen:
                    keywords.append(name)
                    seen.add(key)

            return keywords
    except FileNotFoundError:
        print(f"未找到玩家名单文件: {file_path}")
        return []

# 要监控的玩家名
KEYWORDS = load_keywords(KEYWORDS_FILE)

CHECK_INTERVAL = 1.0
MAX_RUNTIME_SECONDS = 300
# =============================================================

def preprocess_image(img):
    """针对游戏暗色UI的预处理（反色+增强）"""
    img = img.convert('L')
    img = ImageOps.invert(img)          # 白字黑底 → 黑字白底（Tesseract更友好）
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.2)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    # 二值化
    img = img.point(lambda p: 255 if p > 130 else 0)
    return img

def show_alert(matched_names):
    """线程安全的弹窗（使用Windows原生MessageBox）"""
    msg = "检测到目标玩家！\n\n" + "\n".join(matched_names)

    # 播放提示音
    try:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except:
        print("\a")

    # Windows原生弹窗（可在任意线程调用）
    ctypes.windll.user32.MessageBoxW(
        0,                          # 父窗口
        msg,                        # 内容
        "玩家检测提醒",              # 标题
        0x30 | 0x1000               # 警告图标 + 置顶
    )


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def capture_and_ocr():
    start_time = time.time()

    with mss() as sct:
        while True:
            if time.time() - start_time >= MAX_RUNTIME_SECONDS:
                print(f"已运行 {MAX_RUNTIME_SECONDS} 秒，未检测到目标玩家，程序退出")
                return

            screenshot = sct.grab(MONITOR_REGION)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            img = preprocess_image(img)

            text = pytesseract.image_to_string(
                img,
                lang='chi_sim+eng',
                config=r'--oem 3 --psm 6'
            )
            text = clean_text(text)

            if text:
                print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text[:150]}...")

                matched = [kw for kw in KEYWORDS if kw.lower() in text.lower()]
                if matched:
                    print(f"【触发提醒】匹配到玩家：{matched}")
                    # 直接调用，不需要再开线程
                    show_alert(matched)
                    print("已检测到目标玩家，程序退出")
                    return

            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    print("Warcraft III 玩家监测程序已启动（适配近卫/天灾军团）")
    print(f"监测区域: {MONITOR_REGION}")
    print(f"监控玩家数: {len(KEYWORDS)}")
    print(f"最长运行时间: {MAX_RUNTIME_SECONDS} 秒")
    print("按 Ctrl+C 停止\n")

    if not KEYWORDS:
        print("玩家名单为空，程序退出")
        sys.exit(1)
    print("按 Ctrl+C 停止\n")

    try:
        capture_and_ocr()
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"错误: {e}")