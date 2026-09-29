import csv
import io
import subprocess
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import winsound
import re
import numpy as np
from PIL import Image
from mss import mss
from plyer import notification

import ctypes
from ctypes import wintypes

from config import MONITOR_REGION, CHECK_INTERVAL, TIMEOUT_SECONDS, HISTORY_FILE, HISTORY_COUNT_TRIGGER
from utils import save_keywords, get_variants, load_keywords, get_all_match_keywords, record_history_ids
from list_manager import ListManager
from ocr_engine import engine


def get_war3_window_rect():
    """Return dict {left, top, width, height} of a visible window whose title contains 'warcraft' or 'war3', or None."""
    try:
        import win32gui
        hwnds = []
        def _enum(h, extra):
            hwnds.append(h)
        win32gui.EnumWindows(_enum, None)
        for h in hwnds:
            if win32gui.IsWindowVisible(h):
                title = win32gui.GetWindowText(h) or ""
                if "warcraft" in title.lower() or "war3" in title.lower():
                    l, t, r, b = win32gui.GetWindowRect(h)
                    return {"left": l, "top": t, "width": r - l, "height": b - t}
    except Exception:
        pass

    # ctypes fallback
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    rect_found = []
    def foreach(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if "warcraft" in title.lower() or "war3" in title.lower():
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                rect_found.append((rect.left, rect.top, rect.right, rect.bottom))
                return False
        return True
    user32.EnumWindows(EnumWindowsProc(foreach), 0)
    if rect_found:
        l, t, r, b = rect_found[0]
        return {"left": l, "top": t, "width": r - l, "height": b - t}
    return None


def scale_monitor_region(win_rect, reference_width=3840, reference_height=2160):
    """Scale MONITOR_REGION (defined for reference resolution) to the given window rectangle.

    win_rect: dict with left, top, width, height
    Returns dict suitable for mss.grab: {"left", "top", "width", "height"} or None on error
    """
    try:
        ref = MONITOR_REGION
        win_w = max(1, win_rect['width'])
        win_h = max(1, win_rect['height'])
        sx = win_w / float(reference_width)
        sy = win_h / float(reference_height)
        left = win_rect['left'] + int(ref['left'] * sx)
        top = win_rect['top'] + int(ref['top'] * sy)
        width = int(ref['width'] * sx)
        height = int(ref['height'] * sy)
        # clip to window bounds
        if left < win_rect['left']:
            left = win_rect['left']
        if top < win_rect['top']:
            top = win_rect['top']
        if left + width > win_rect['left'] + win_w:
            width = (win_rect['left'] + win_w) - left
        if top + height > win_rect['top'] + win_h:
            height = (win_rect['top'] + win_h) - top
        if width <= 0 or height <= 0:
            return None
        return {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
    except Exception as e:
        print(f"scale_monitor_region error: {e}")
        return None

class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warcraft III 玩家监测")
        
        # 初始数据加载
        self.grouped_keywords = load_keywords()
        self.keywords = [item.split(":", 1)[1] for item in self.grouped_keywords]
        self.variant_to_original = {}
        self.variant_to_group = {}
        self.match_keywords = self._prepare_match_keywords()
        
        # 获取所有分组
        self.groups = sorted(list(set([item.split(":", 1)[0] for item in self.grouped_keywords])))
        if "默认" not in self.groups:
            self.groups.insert(0, "默认")
        
        self.current_group = tk.StringVar(value="全部")
        self.display_groups = ["全部"] + self.groups
        
        # 初始窗口大小
        base_width = 480
        base_height = 620
        
        self.is_running = False
        self.monitor_thread = None
        self.stop_event = threading.Event()

        # 设置窗口位置到中部偏右侧
        self.root.update_idletasks() # 确保能获取到准确的屏幕参数
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 中部偏右：x 保持靠近右边缘，y 居中
        x = max(0, screen_width - base_width - 10)
        y = max(0, (screen_height - base_height) // 2)
        
        self.root.geometry(f"{base_width}x{base_height}+{x}+{y}")
        self.root.minsize(460, 580)
        self.root.resizable(True, True)
        
        # UI 元素
        self.label_status = tk.Label(root, text="状态: 未运行", fg="red", font=("Arial", 12), width=20)
        self.label_status.pack(pady=10)

        self.btn_start = tk.Button(root, text="开始识别", command=self.start_monitoring, width=15, height=2)
        self.btn_start.pack(pady=5)

        self.btn_stop = tk.Button(root, text="停止识别", command=self.stop_monitoring, width=15, height=2, state=tk.DISABLED)
        self.btn_stop.pack(pady=5)

        # 新增 ID 区域
        frame_add = tk.Frame(root)
        frame_add.pack(pady=5)
        
        tk.Label(frame_add, text="分组:").grid(row=0, column=0, padx=2, pady=2)
        self.combo_group = ttk.Combobox(frame_add, values=self.groups, width=8)
        self.combo_group.set("默认")
        self.combo_group.grid(row=0, column=1, padx=2, pady=2)
        
        tk.Label(frame_add, text="ID:").grid(row=0, column=2, padx=2, pady=2)
        self.entry_new_id = tk.Entry(frame_add, width=14)
        self.entry_new_id.grid(row=0, column=3, padx=2, pady=2)
        
        self.btn_add = tk.Button(frame_add, text="添加", command=self.add_keyword, width=6)
        self.btn_add.grid(row=0, column=4, padx=5, pady=2)

        # 管理工具按钮区域
        frame_tools = tk.Frame(root)
        frame_tools.pack(pady=3)

        self.btn_manage = tk.Button(frame_tools, text="名单管理", command=self.open_manager, width=14, bg="#f0f0f0")
        self.btn_manage.pack(side=tk.LEFT, padx=6)

        self.btn_confusable = tk.Button(frame_tools, text="混淆字符管理", command=self.open_confusable_manager, width=14, bg="#f0f0f0")
        self.btn_confusable.pack(side=tk.LEFT, padx=6)

        # 展示列表区域
        frame_list_header = tk.Frame(root)
        frame_list_header.pack(pady=(10, 0))
        tk.Label(frame_list_header, text="当前目标名单 (").pack(side=tk.LEFT)
        self.option_filter = tk.OptionMenu(frame_list_header, self.current_group, *self.display_groups, command=lambda _: self.update_keyword_display())
        self.option_filter.pack(side=tk.LEFT)
        tk.Label(frame_list_header, text="):").pack(side=tk.LEFT)
        
        self.text_keywords = tk.Text(root, width=40, height=10)
        self.text_keywords.pack(pady=5, padx=10)
        self.update_keyword_display()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _prepare_match_keywords(self):
        """ 准备匹配用的变体名单，并建立变体到原始ID和分组的映射 """
        all_matches = []
        for item in self.grouped_keywords:
            group, kw = item.split(":", 1)
            variants = get_variants(kw)
            for v in variants:
                if v not in self.variant_to_original:
                    self.variant_to_original[v] = kw
                    self.variant_to_group[v] = group
                    all_matches.append(v)
        return all_matches

    def update_keyword_display(self):
        """ 更新多行文本框显示的内容，支持按分组过滤 """
        self.text_keywords.config(state=tk.NORMAL)
        self.text_keywords.delete(1.0, tk.END)
        
        filter_group = self.current_group.get()
        display_list = []
        for item in self.grouped_keywords:
            group, pid = item.split(":", 1)
            if filter_group == "全部" or filter_group == group:
                display_list.append(f"[{group}] {pid}")
        
        self.text_keywords.insert(tk.END, "\n".join(display_list))
        self.text_keywords.config(state=tk.DISABLED)

    def add_keyword(self):
        new_id = self.entry_new_id.get().strip()
        new_group = self.combo_group.get().strip() or "默认"
        
        if not new_id:
            messagebox.showwarning("警告", "请输入有效的玩家ID", parent=self.root)
            return
        
        full_entry = f"{new_group}:{new_id}"
        if full_entry in self.grouped_keywords:
            messagebox.showinfo("提示", f"ID '{new_id}' 已在分组 '{new_group}' 中", parent=self.root)
            return

        # 1. 更新原始名单并保存
        self.grouped_keywords.append(full_entry)
        # 再次确保去重并保持顺序
        seen = set()
        self.grouped_keywords = [x for x in self.grouped_keywords if not (x in seen or seen.add(x))]
        save_keywords(self.grouped_keywords)
        
        # 更新 keywords 列表用于其他逻辑
        self.keywords = [item.split(":", 1)[1] for item in self.grouped_keywords]
        
        # 更新分组列表
        if new_group not in self.groups:
            self.groups.append(new_group)
            self.groups.sort()
            self.combo_group['values'] = self.groups
            # 注意：OptionMenu 动态更新较繁琐，这里简单提示重启或可重新创建
        
        # 2. 更新内存中的匹配变体名单
        new_variants = get_variants(new_id)
        added_count = 0
        for vid in new_variants:
            if vid not in self.match_keywords:
                # 记录变体到原始 ID 的映射
                self.variant_to_original[vid] = new_id
                self.variant_to_group[vid] = new_group
                self.match_keywords.append(vid)
                added_count += 1
        
        # 3. 更新界面
        self.update_keyword_display()
        msg = f"已成功添加目标: {new_id} (分组: {new_group})"
        if added_count > 1:
            msg += f"\n已在后台自动加载 {added_count-1} 个识别变体"
            
        messagebox.showinfo("成功", msg, parent=self.root)
        self.entry_new_id.delete(0, tk.END)

    def open_manager(self):
        """ 打开独立的名单管理器窗口 """
        manager_root = tk.Toplevel(self.root)
        ListManager(manager_root)
        # 等待管理器关闭后刷新界面
        self.root.wait_window(manager_root)
        self.reload_data()

    def open_confusable_manager(self):
        """ 打开独立的混淆字符表管理器窗口 """
        manager_root = tk.Toplevel(self.root)
        from confusable_manager import ConfusableManager
        ConfusableManager(manager_root)
        # 等待混淆管理器关闭后刷新界面和识别变体
        self.root.wait_window(manager_root)
        self.reload_data()

    def reload_data(self):
        """ 重新从文件加载数据并刷新界面 """
        self.grouped_keywords = load_keywords()
        self.keywords = [item.split(":", 1)[1] for item in self.grouped_keywords]
        self.variant_to_original = {}
        self.variant_to_group = {}
        self.match_keywords = self._prepare_match_keywords()
        
        # 更新分组下拉框内容
        self.groups = sorted(list(set([item.split(":", 1)[0] for item in self.grouped_keywords])))
        if "默认" not in self.groups:
            self.groups.insert(0, "默认")
        self.display_groups = ["全部"] + self.groups
        
        # 刷新 UI 元素
        self.combo_group['values'] = self.groups
        # 更新 OptionMenu 比较麻烦，简单处理是重新设置展示列表
        self.update_keyword_display()

    def is_war3_running(self):
        """检查 war3 进程是否已启动。"""
        try:
            # Prevent showing a terminal window when invoking tasklist on Windows
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            output = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], stderr=subprocess.DEVNULL, text=True, creationflags=creation_flags)
        except Exception:
            return False

        for row in csv.reader(io.StringIO(output)):
            if not row:
                continue
            proc_name = row[0].strip().lower()
            if proc_name in {"war3.exe", "warcraft iii.exe", "war3loader.exe"}:
                return True
            if proc_name.endswith("\\war3.exe") or proc_name.endswith("\\warcraft iii.exe"):
                return True
        return False

    def wait_for_war3_start(self):
        while not self.stop_event.is_set():
            if self.is_war3_running():
                self.start_time = time.time()
                self.root.after(0, self.start_monitor_loop)
                return
            time.sleep(CHECK_INTERVAL)

    def start_monitor_loop(self):
        if not self.is_running or self.stop_event.is_set():
            return
        self.label_status.config(text="状态: 正在监控...", fg="green")
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def start_monitoring(self):
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.label_status.config(text="状态: 等待 war3 进程启动...", fg="orange")

            self.monitor_thread = threading.Thread(target=self.wait_for_war3_start, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        if self.is_running:
            self.is_running = False
            self.stop_event.set()
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.label_status.config(text="状态: 已停止", fg="red")

    def show_alert(self, matched_info):
        """
        matched_info: list of tuples (name, group)
        """
        display_msgs = [f"{name} ({group})" for name, group in matched_info]
        msg = "检测到目标玩家：\n" + ", ".join(display_msgs)
        
        # 创建自动消失的弹窗
        top = tk.Toplevel(self.root)
        top.title("玩家检测提醒")
        # 设置置顶
        top.attributes("-topmost", True)
        top.lift()
        # 声音提醒
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        # 根据主窗口限制设置文本最大折行宽度，避免过宽或过窄
        try:
            max_wrap = max(200, min(600, self.root.winfo_width() - 100))
        except Exception:
            max_wrap = 400

        tk.Label(top, text="玩家检测提醒", font=("Arial", 12, "bold"), pady=10).pack()
        tk.Label(top, text=msg, wraplength=max_wrap, pady=5).pack()
        
        btn = tk.Button(top, text="确定 (10s)", command=top.destroy, width=10)
        btn.pack(pady=5)

        # 调整窗口大小以适应内容并居中显示
        top.update_idletasks()
        w = max(380, top.winfo_width() + 40)
        h = max(200, top.winfo_height() + 20)
        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2))
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2))
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.minsize(360, 180)

        # 10秒后自动关闭
        def auto_close(remaining):
            if top.winfo_exists():
                if remaining <= 0:
                    top.destroy()
                else:
                    btn.config(text=f"确定 ({remaining}s)")
                    top.after(1000, lambda: auto_close(remaining - 1))

        top.after(1000, lambda: auto_close(9))

        try:
            # 使用系统通知（不依赖于其成功与否）
            notification.notify(
                title="玩家检测提醒",
                message=msg,
                app_name="Player Monitor",
                timeout=10
            )
        except Exception as e:
            print(f"发送系统通知失败: {e}")

    def monitor_loop(self):
        with mss() as sct:
            while not self.stop_event.is_set():
                elapsed = time.time() - self.start_time
                if elapsed > TIMEOUT_SECONDS:
                    print(f"[{time.strftime('%H:%M:%S')}] 监控超时 ({TIMEOUT_SECONDS}s)，自动停止。")
                    self.root.after(0, self.handle_timeout)
                    break

                try:
                    win_rect = get_war3_window_rect()
                    if not win_rect:
                        # War3 窗口未找到，稍后重试
                        time.sleep(CHECK_INTERVAL)
                        continue
                    scaled = scale_monitor_region(win_rect, reference_width=3840, reference_height=2160)
                    if not scaled:
                        # 计算失败则重试
                        time.sleep(CHECK_INTERVAL)
                        continue
                    screenshot = sct.grab(scaled)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    img_np = np.array(img)
                    
                    results = engine.read_text(img_np)
                    # 记录所有识别到的疑似 ID（用于满足 11 个时的历史记录）
                    detected_ids = [res.strip() for res in results if res.strip()]
                    
                    if len(detected_ids) == HISTORY_COUNT_TRIGGER:
                        print(f"[{time.strftime('%H:%M:%S')}] 检测到 {HISTORY_COUNT_TRIGGER} 个用户，记录历史 ID...")
                        record_history_ids(detected_ids, HISTORY_FILE)

                    text = " ".join(results)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text:
                        print(f"[{time.strftime('%H:%M:%S')}] 识别结果：{text}")
                        # 查找匹配的变体
                        matched_variants = [kw for kw in self.match_keywords if kw.lower() in text.lower()]
                        
                        if matched_variants:
                            # 将变体映射回原始 ID 和分组并去重
                            original_matched_info = []
                            seen_entry = set()
                            for v in matched_variants:
                                orig = self.variant_to_original.get(v, v)
                                group = self.variant_to_group.get(v, "未知")
                                entry = (orig, group)
                                if entry not in seen_entry:
                                    original_matched_info.append(entry)
                                    seen_entry.add(entry)
                            
                            print(f"【触发提醒】匹配变体：{matched_variants} -> 原始信息：{original_matched_info}")
                            self.root.after(0, self.handle_match, original_matched_info)
                            break
                except Exception as e:
                    print(f"识别出错: {e}")
                
                time.sleep(CHECK_INTERVAL)

    def handle_match(self, matched_info):
        self.stop_monitoring()
        self.show_alert(matched_info)

    def handle_timeout(self):
        self.stop_monitoring()
        self.label_status.config(text="状态: 监控超时停止", fg="orange")

    def on_closing(self):
        self.stop_event.set()
        try:
            # 过滤空行并排序
            self.grouped_keywords = sorted(list(set([k.strip() for k in self.grouped_keywords if k.strip()])))
            save_keywords(self.grouped_keywords)
            print("名单已排序并保存。")
        except Exception as e:
            print(f"退出保存名单失败: {e}")
        self.root.destroy()
