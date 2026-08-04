import time
import sys
import re
import ctypes
import winsound
import os
import threading
import tkinter as tk
from tkinter import messagebox

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
# 监测区域：左，上，宽，高
MONITOR_REGION = {"top": 140, "left": 100, "width": 900, "height": 960}
CHECK_INTERVAL = 0.5
TIMEOUT_SECONDS = 300  # 启动后 300s 未检测到目标则停止

# 混淆字符映射表
CONFUSABLE_MAP = {
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
}

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

# ===========================================

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
    for x in ids:
        if x not in seen:
            unique_ids.append(x)
            seen.add(x)
    return unique_ids

def save_keywords(keywords):
    """ 将关键字列表保存到 paid_player_id.txt """
    file_path = os.path.join(os.path.abspath("."), "paid_player_id.txt")
    # 如果是在临时目录下（打包后），get_resource_path 会指向 _MEIPASS，那是只读的
    # 我们始终尝试保存在程序运行目录，这样用户修改才能持久化
    
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

KEYWORDS = load_keywords()
MATCH_KEYWORDS = get_all_match_keywords(KEYWORDS)

# 初始化 EasyOCR
print("正在检查 GPU 状态...")
try:
    import torch
    use_gpu = torch.cuda.is_available()
    if use_gpu:
        print(f"检测到 GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("未检测到可用 GPU，将使用 CPU 模式 (识别速度较慢)")
        print("提示: 如果您有 NVIDIA 显卡，请安装 GPU 版 PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cu118")
except ImportError:
    use_gpu = False
    print("无法导入 torch，尝试使用默认配置")

print("正在加载 EasyOCR 模型...")
model_storage_path = get_resource_path("easyocr_models")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=use_gpu, model_storage_directory=model_storage_path) 
print("模型加载完成！\n")

class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warcraft III 玩家监测")
        
        # 初始窗口大小
        base_width = 400
        base_height = 550
        
        self.is_running = False
        self.monitor_thread = None
        self.stop_event = threading.Event()

        # 设置窗口位置到中部偏右侧
        self.root.update_idletasks() # 确保能获取到准确的屏幕参数
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 中部偏右：x 保持靠近右边缘，y 居中
        x = screen_width - base_width - 10 
        y = (screen_height - base_height) // 2 
        
        self.root.geometry(f"{base_width}x{base_height}+{x}+{y}")
        self.root.resizable(False, False) 
        
        # UI 元素
        # 使用固定宽度以防止文本变化时布局抖动
        self.label_status = tk.Label(root, text="状态: 未运行", fg="red", font=("Arial", 12), width=20)
        self.label_status.pack(pady=10)

        self.btn_start = tk.Button(root, text="开始识别", command=self.start_monitoring, width=15, height=2)
        self.btn_start.pack(pady=5)

        self.btn_stop = tk.Button(root, text="停止识别", command=self.stop_monitoring, width=15, height=2, state=tk.DISABLED)
        self.btn_stop.pack(pady=5)

        # 新增 ID 区域 (移动到按钮下方)
        frame_add = tk.Frame(root)
        frame_add.pack(pady=10)
        
        tk.Label(frame_add, text="新增玩家ID:").pack(side=tk.LEFT)
        self.entry_new_id = tk.Entry(frame_add, width=15)
        self.entry_new_id.pack(side=tk.LEFT, padx=5)
        self.btn_add = tk.Button(frame_add, text="添加", command=self.add_keyword)
        self.btn_add.pack(side=tk.LEFT)

        # 展示列表区域
        tk.Label(root, text="当前目标名单:").pack(pady=(10, 0))
        self.text_keywords = tk.Text(root, width=40, height=10)
        self.text_keywords.pack(pady=5, padx=10)
        self.update_keyword_display()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_keyword_display(self):
        """ 更新多行文本框显示的内容 """
        self.text_keywords.config(state=tk.NORMAL)
        self.text_keywords.delete(1.0, tk.END)
        self.text_keywords.insert(tk.END, "\n".join(KEYWORDS))
        self.text_keywords.config(state=tk.DISABLED)

    def add_keyword(self):
        new_id = self.entry_new_id.get().strip()
        if not new_id:
            messagebox.showwarning("警告", "请输入有效的玩家ID", parent=self.root)
            return
        
        if new_id in KEYWORDS:
            messagebox.showinfo("提示", f"ID '{new_id}' 已在名单中", parent=self.root)
            return

        # 1. 更新原始名单并保存
        KEYWORDS.append(new_id)
        save_keywords(KEYWORDS)
        
        # 2. 更新内存中的匹配变体名单
        global MATCH_KEYWORDS
        new_variants = get_variants(new_id)
        added_count = 0
        for vid in new_variants:
            if vid not in MATCH_KEYWORDS:
                MATCH_KEYWORDS.append(vid)
                added_count += 1
        
        # 3. 更新界面
        self.update_keyword_display()
        msg = f"已成功添加目标: {new_id}"
        if added_count > 1:
            msg += f"\n已在后台自动加载 {added_count-1} 个识别变体"
            
        messagebox.showinfo("成功", msg, parent=self.root)
        self.entry_new_id.delete(0, tk.END)

    def start_monitoring(self):
        if not self.is_running:
            self.is_running = True
            self.start_time = time.time()  # 记录开始时间
            self.stop_event.clear()
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.label_status.config(text="状态: 正在监控...", fg="green")
            
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        if self.is_running:
            self.is_running = False
            self.stop_event.set()
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.label_status.config(text="状态: 已停止", fg="red")

    def show_alert(self, matched_names):
        msg = "检测到目标玩家！\n\n" + "\n".join(matched_names)
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except:
            pass
        
        # 确保窗口并弹出到最前面
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        
        # 在主线程中弹出对话框
        messagebox.showinfo("玩家检测提醒", msg, parent=self.root)
        
        # 弹窗关闭后取消最前端显示，以免影响其他操作
        self.root.attributes("-topmost", False)

    def monitor_loop(self):
        with mss() as sct:
            while not self.stop_event.is_set():
                # 检查是否超时
                elapsed = time.time() - self.start_time
                if elapsed > TIMEOUT_SECONDS:
                    print(f"[{time.strftime('%H:%M:%S')}] 监控超时 ({TIMEOUT_SECONDS}s)，自动停止。")
                    self.root.after(0, self.handle_timeout)
                    break

                try:
                    screenshot = sct.grab(MONITOR_REGION)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    img_np = np.array(img)
                    
                    results = reader.readtext(img_np, detail=0, paragraph=False)
                    text = " ".join(results)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text:
                        print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text}")
                        matched = [kw for kw in MATCH_KEYWORDS if kw.lower() in text.lower()]
                        
                        if matched:
                            print(f"【触发提醒】匹配到：{matched}")
                            # 切换回主线程停止并弹窗
                            self.root.after(0, self.handle_match, matched)
                            break
                except Exception as e:
                    print(f"识别出错: {e}")
                
                time.sleep(CHECK_INTERVAL)

    def handle_match(self, matched):
        self.stop_monitoring()
        self.show_alert(matched)

    def handle_timeout(self):
        """ 处理检测超时 """
        self.stop_monitoring()
        self.label_status.config(text="状态: 监控超时停止", fg="orange")

    def on_closing(self):
        self.stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    set_dpi_awareness()
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()