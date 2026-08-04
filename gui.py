import time
import threading
import tkinter as tk
from tkinter import messagebox
import winsound
import re
import numpy as np
from PIL import Image
from mss import mss

from config import MONITOR_REGION, CHECK_INTERVAL, TIMEOUT_SECONDS
from utils import save_keywords, get_variants, load_keywords, get_all_match_keywords
from ocr_engine import engine

class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warcraft III 玩家监测")
        
        # 初始数据加载
        self.keywords = load_keywords()
        self.match_keywords = get_all_match_keywords(self.keywords)
        
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
        self.label_status = tk.Label(root, text="状态: 未运行", fg="red", font=("Arial", 12), width=20)
        self.label_status.pack(pady=10)

        self.btn_start = tk.Button(root, text="开始识别", command=self.start_monitoring, width=15, height=2)
        self.btn_start.pack(pady=5)

        self.btn_stop = tk.Button(root, text="停止识别", command=self.stop_monitoring, width=15, height=2, state=tk.DISABLED)
        self.btn_stop.pack(pady=5)

        # 新增 ID 区域
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
        self.text_keywords.insert(tk.END, "\n".join(self.keywords))
        self.text_keywords.config(state=tk.DISABLED)

    def add_keyword(self):
        new_id = self.entry_new_id.get().strip()
        if not new_id:
            messagebox.showwarning("警告", "请输入有效的玩家ID", parent=self.root)
            return
        
        if new_id in self.keywords:
            messagebox.showinfo("提示", f"ID '{new_id}' 已在名单中", parent=self.root)
            return

        # 1. 更新原始名单并保存
        self.keywords.append(new_id)
        # 再次确保去重并保持顺序
        seen = set()
        self.keywords = [x for x in self.keywords if not (x in seen or seen.add(x))]
        save_keywords(self.keywords)
        
        # 2. 更新内存中的匹配变体名单
        new_variants = get_variants(new_id)
        added_count = 0
        for vid in new_variants:
            if vid not in self.match_keywords:
                self.match_keywords.append(vid)
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
            self.start_time = time.time()
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
        
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        
        messagebox.showinfo("玩家检测提醒", msg, parent=self.root)
        
        self.root.attributes("-topmost", False)

    def monitor_loop(self):
        with mss() as sct:
            while not self.stop_event.is_set():
                elapsed = time.time() - self.start_time
                if elapsed > TIMEOUT_SECONDS:
                    print(f"[{time.strftime('%H:%M:%S')}] 监控超时 ({TIMEOUT_SECONDS}s)，自动停止。")
                    self.root.after(0, self.handle_timeout)
                    break

                try:
                    screenshot = sct.grab(MONITOR_REGION)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    img_np = np.array(img)
                    
                    results = engine.read_text(img_np)
                    text = " ".join(results)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text:
                        print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text}")
                        matched = [kw for kw in self.match_keywords if kw.lower() in text.lower()]
                        
                        if matched:
                            print(f"【触发提醒】匹配到：{matched}")
                            self.root.after(0, self.handle_match, matched)
                            break
                except Exception as e:
                    print(f"识别出错: {e}")
                
                time.sleep(CHECK_INTERVAL)

    def handle_match(self, matched):
        self.stop_monitoring()
        self.show_alert(matched)

    def handle_timeout(self):
        self.stop_monitoring()
        self.label_status.config(text="状态: 监控超时停止", fg="orange")

    def on_closing(self):
        self.stop_event.set()
        try:
            # 过滤空行并排序
            self.keywords = sorted(list(set([k.strip() for k in self.keywords if k.strip()])))
            save_keywords(self.keywords)
            print("名单已排序并保存。")
        except Exception as e:
            print(f"退出保存名单失败: {e}")
        self.root.destroy()
