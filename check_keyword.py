import ctypes
import time
import tkinter as tk
from tkinter import messagebox
import threading
import sys
import re
import os

import winsound
from pathlib import Path

try:
    from mss import MSS
    from PIL import Image, ImageEnhance, ImageOps, ImageFilter
    import pytesseract
except ImportError:
    print("缺少依赖库，请先安装：")
    print("pip install mss pillow pytesseract")
    sys.exit(1)

# ================== 配置区（已根据图片适配） ==================
# Tesseract OCR 引擎路径（如果未加入系统PATH，请在此指定）
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 监测区域（针对 3840x2160 分辨率的左边玩家列表，按实际分辨率自行微调）
# 格式：{"top": y1, "left": x1, "width": w, "height": h}
MONITOR_REGION = {"top": 180, "left": 240, "width": 1040 - 240, "height": 1100 - 180}   # 覆盖近卫+天灾玩家名字区域

if getattr(sys, 'frozen', False):
    # 打包后的路径
    BASE_PATH = Path(sys._MEIPASS)
    # 对于经常需要修改的配置文件，建议放在 exe 同级目录
    KEYWORDS_FILE = Path(sys.executable).parent / "paid_player_id.txt"
    
    # 配置 Tesseract 路径（打包后在 _MEIPASS/tesseract 目录下）
    tesseract_dir = BASE_PATH / "tesseract"
    pytesseract.pytesseract.tesseract_cmd = str(tesseract_dir / "tesseract.exe")
    os.environ["TESSDATA_PREFIX"] = str(tesseract_dir / "tessdata")
else:
    # 开发环境路径
    BASE_PATH = Path(__file__).parent
    KEYWORDS_FILE = BASE_PATH / "paid_player_id.txt"
    # 如果开发环境也需要指定路径，取消下面注释
    # pytesseract.pytesseract.tesseract_cmd = r'H:\Program Files\Tesseract-OCR\tesseract.exe'

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
    """针对白色文字的OCR预处理：提取白字、压暗背景、增强对比度"""
    # 转 RGB，方便按颜色特征提取白色文字
    img = img.convert("RGB")

    # 提取接近白色/浅灰色的像素：
    # Warcraft III UI 中白字通常 RGB 三通道都较高，且通道差异较小
    pixels = img.load()
    new_img = Image.new("RGB", img.size)
    new_pixels = new_img.load()

    for y in range(img.height):
        for x in range(img.width):
            r, g, b = pixels[x, y]
            # 亮度足够高
            bright = r > 155 and g > 155 and b > 155
            # 接近灰白色，避免把彩色图标/边框也保留下来
            near_white = max(r, g, b) - min(r, g, b) < 45
            if bright and near_white:
                new_pixels[x, y] = (255, 255, 255)
            else:
                new_pixels[x, y] = (0, 0, 0)
    
    img = new_img

    # 转灰度
    img = img.convert("L")

    # 白字黑底 → 黑字白底，Tesseract 更容易识别
    img = ImageOps.invert(img)

    # 放大图像，提高小字号识别率
    scale = 2
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)

    # 增强对比度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.5)

    # 自动拉伸对比度
    img = ImageOps.autocontrast(img)

    # 轻微锐化
    img = img.filter(ImageFilter.SHARPEN)

    # 二值化：黑字白底
    img = img.point(lambda p: 0 if p < 170 else 255)

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

    with MSS() as sct:
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
                config=r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
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