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
    """ 从 paid_player_id.txt 加载关键字列表 """
    file_path = get_resource_path("paid_player_id.txt")
    if not os.path.exists(file_path):
        file_path = "paid_player_id.txt"
        
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取文件错误: {e}")
    return ["素质路人88", "川医声在掏"]

def save_keywords(keywords):
    """ 将关键字列表保存到 paid_player_id.txt """
    file_path = get_resource_path("paid_player_id.txt")
    # 如果是在临时目录下（打包后），可能需要检查逻辑，但通常我们希望保存到工作目录
    if hasattr(sys, '_MEIPASS'):
        # 打包模式下，_MEIPASS 是只读的，我们需要保存在程序运行目录
        file_path = os.path.join(os.path.abspath("."), "paid_player_id.txt")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for kw in keywords:
                f.write(f"{kw}\n")
    except Exception as e:
        print(f"保存文件错误: {e}")

KEYWORDS = load_keywords()

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
            messagebox.showwarning("警告", "请输入有效的玩家ID")
            return
        
        if new_id in KEYWORDS:
            messagebox.showinfo("提示", f"ID '{new_id}' 已在名单中")
        else:
            KEYWORDS.append(new_id)
            save_keywords(KEYWORDS)
            self.update_keyword_display()
            messagebox.showinfo("成功", f"已添加并保存: {new_id}")
            self.entry_new_id.delete(0, tk.END)

    def start_monitoring(self):
        if not self.is_running:
            self.is_running = True
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
        # 在主线程中弹出对话框
        messagebox.showinfo("玩家检测提醒", msg)

    def monitor_loop(self):
        with mss() as sct:
            while not self.stop_event.is_set():
                try:
                    screenshot = sct.grab(MONITOR_REGION)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    img_np = np.array(img)
                    
                    results = reader.readtext(img_np, detail=0, paragraph=False)
                    text = " ".join(results)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text:
                        print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text}")
                        matched = [kw for kw in KEYWORDS if kw.lower() in text.lower()]
                        
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

    def on_closing(self):
        self.stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    set_dpi_awareness()
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()