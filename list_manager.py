import tkinter as tk
from tkinter import messagebox, ttk
import winsound
from utils import load_player_data, save_player_data, set_dpi_awareness
import os

class ListManager:
    def __init__(self, root):
        self.member_listbox = None
        self.search_entry = None
        self.group_listbox = None
        self.root = root
        self.root.title("目标名单管理器")
        self.root.geometry("820x600")
        self.root.minsize(740, 520)
        
        set_dpi_awareness()
        
        self.data = load_player_data()
        
        # UI Setup
        self.setup_ui()
        self.refresh_group_list()

    def setup_ui(self):
        # Left side: Group list
        left_frame = tk.Frame(self.root, width=240)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=10)
        
        tk.Label(left_frame, text="分组列表", font=("Arial", 9, "bold")).pack(pady=(0, 4))
        self.group_listbox = tk.Listbox(left_frame, exportselection=False)
        self.group_listbox.pack(fill=tk.BOTH, expand=True)
        self.group_listbox.bind('<<ListboxSelect>>', self.on_group_select)
        
        group_btn_frame = tk.Frame(left_frame)
        group_btn_frame.pack(fill=tk.X, pady=6)
        tk.Button(group_btn_frame, text="新增", command=self.add_group, width=6).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(group_btn_frame, text="删除", command=self.delete_group, width=6).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(group_btn_frame, text="重命名", command=self.rename_group, width=6).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Right side: Action buttons (竖排排列置于右下角)
        right_btn_frame = tk.Frame(self.root, padx=5)
        right_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 10), pady=10)

        right_bottom_box = tk.Frame(right_btn_frame)
        right_bottom_box.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Button(right_bottom_box, text="从历史导入", command=self.import_from_history, bg="#e1e1e1", font=("Arial", 9), width=12, pady=3).pack(pady=4, fill=tk.X)
        tk.Button(right_bottom_box, text="混淆字符管理", command=self.open_confusable_manager, bg="#e1e1e1", font=("Arial", 9), width=12, pady=3).pack(pady=4, fill=tk.X)
        tk.Button(right_bottom_box, text="保存更改", command=self.save_changes, bg="green", fg="white", font=("Arial", 9, "bold"), width=12, pady=3).pack(pady=4, fill=tk.X)

        # Center: Member list
        center_frame = tk.Frame(self.root)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        search_frame = tk.Frame(center_frame)
        search_frame.pack(fill=tk.X)
        tk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search)

        tk.Label(center_frame, text="成员列表", font=("Arial", 9, "bold")).pack(pady=(8, 4))
        self.member_listbox = tk.Listbox(center_frame, exportselection=False)
        self.member_listbox.pack(fill=tk.BOTH, expand=True)
        
        member_btn_frame = tk.Frame(center_frame)
        member_btn_frame.pack(fill=tk.X, pady=6)
        tk.Button(member_btn_frame, text="新增 ID", command=self.add_member, width=7).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(member_btn_frame, text="删除 ID", command=self.delete_member, width=7).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(member_btn_frame, text="编辑 ID", command=self.edit_member, width=7).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(member_btn_frame, text="移动", command=self.move_member, width=7).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def refresh_group_list(self):
        self.group_listbox.delete(0, tk.END)
        for group in sorted(self.data["groups"].keys()):
            self.group_listbox.insert(tk.END, group)
        if self.data["groups"]:
            self.group_listbox.selection_set(0)
            self.on_group_select(None)

    def on_group_select(self, event):
        selection = self.group_listbox.curselection()
        if not selection:
            return
        group_name = self.group_listbox.get(selection[0])
        self.refresh_member_list(group_name)

    def refresh_member_list(self, group_name, filter_text=""):
        self.member_listbox.delete(0, tk.END)
        members = self.data["groups"].get(group_name, [])
        for m in sorted(members):
            if not filter_text or filter_text.lower() in m.lower():
                self.member_listbox.insert(tk.END, m)

    def on_search(self, event):
        selection = self.group_listbox.curselection()
        if not selection:
            return
        group_name = self.group_listbox.get(selection[0])
        self.refresh_member_list(group_name, self.search_entry.get())

    def add_group(self):
        new_group = self.ask_input("新增分组", "请输入分组名称:")
        if new_group and new_group not in self.data["groups"]:
            self.data["groups"][new_group] = []
            self.refresh_group_list()
        elif new_group:
            messagebox.showwarning("错误", "分组已存在", parent=self.root)

    def delete_group(self):
        selection = self.group_listbox.curselection()
        if not selection: return
        group_name = self.group_listbox.get(selection[0])
        if messagebox.askyesno("确认", f"确定删除分组 '{group_name}' 及其所有成员吗？", parent=self.root):
            del self.data["groups"][group_name]
            self.refresh_group_list()

    def rename_group(self):
        selection = self.group_listbox.curselection()
        if not selection: return
        old_name = self.group_listbox.get(selection[0])
        new_name = self.ask_input("重命名分组", f"将 '{old_name}' 重命名为:", old_name)
        if new_name and new_name != old_name:
            if new_name in self.data["groups"]:
                messagebox.showwarning("错误", "新分组名称已存在", parent=self.root)
            else:
                self.data["groups"][new_name] = self.data["groups"].pop(old_name)
                self.refresh_group_list()

    def add_member(self):
        selection = self.group_listbox.curselection()
        if not selection: 
            messagebox.showwarning("提示", "请先选择一个分组", parent=self.root)
            return
        group_name = self.group_listbox.get(selection[0])
        new_id = self.ask_input("新增 ID", f"在分组 '{group_name}' 中新增 ID:")
        if new_id:
            if new_id not in self.data["groups"][group_name]:
                self.data["groups"][group_name].append(new_id)
                self.refresh_member_list(group_name)
            else:
                messagebox.showwarning("提示", "ID 已存在于该分组中", parent=self.root)

    def delete_member(self):
        g_selection = self.group_listbox.curselection()
        m_selection = self.member_listbox.curselection()
        if not g_selection or not m_selection: return
        group_name = self.group_listbox.get(g_selection[0])
        member_id = self.member_listbox.get(m_selection[0])
        if messagebox.askyesno("确认", f"确定从 '{group_name}' 中删除 ID '{member_id}' 吗？", parent=self.root):
            if member_id in self.data["groups"][group_name]:
                self.data["groups"][group_name].remove(member_id)
                # 立即持久化更改以避免删除看似无效的问题
                save_player_data(self.data)
                self.refresh_member_list(group_name)
                messagebox.showinfo("成功", f"已从 '{group_name}' 删除 ID '{member_id}' 并保存。", parent=self.root)

    def edit_member(self):
        g_selection = self.group_listbox.curselection()
        m_selection = self.member_listbox.curselection()
        if not g_selection or not m_selection: return
        group_name = self.group_listbox.get(g_selection[0])
        old_id = self.member_listbox.get(m_selection[0])
        new_id = self.ask_input("编辑 ID", "修改 ID 为:", old_id)
        if new_id and new_id != old_id:
            idx = self.data["groups"][group_name].index(old_id)
            self.data["groups"][group_name][idx] = new_id
            self.refresh_member_list(group_name)

    def move_member(self):
        g_selection = self.group_listbox.curselection()
        m_selection = self.member_listbox.curselection()
        if not g_selection or not m_selection: return
        
        source_group = self.group_listbox.get(g_selection[0])
        member_id = self.member_listbox.get(m_selection[0])
        
        # 弹窗选择目标分组
        target_group = self.ask_selection("移动 ID", f"将 ID '{member_id}' 移动到:", sorted(self.data["groups"].keys()))
        
        if target_group and target_group != source_group:
            if member_id in self.data["groups"][target_group]:
                messagebox.showinfo("提示", f"ID '{member_id}' 已在目标分组 '{target_group}' 中", parent=self.root)
            else:
                self.data["groups"][source_group].remove(member_id)
                self.data["groups"][target_group].append(member_id)
                self.refresh_member_list(source_group)
                messagebox.showinfo("成功", f"已成功移动到 '{target_group}'", parent=self.root)

    def import_from_history(self):
        from config import HISTORY_FILE
        history_path = os.path.join(os.path.abspath("."), HISTORY_FILE)
        
        if not os.path.exists(history_path):
            messagebox.showwarning("错误", "未找到历史记录文件", parent=self.root)
            return
            
        try:
            history_list = []
            import json
            with open(history_path, 'r', encoding='utf-8') as f:
                raw = f.read().strip()
                if raw:
                    try:
                        data = json.loads(raw)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "id" in item:
                                    try:
                                        ts_val = int(item.get("ts", 0))
                                    except:
                                        ts_val = 0
                                    history_list.append({"id": item["id"], "ts": ts_val})
                        elif isinstance(data, dict):
                            for k, v in data.items():
                                try:
                                    ts_val = int(v)
                                except:
                                    ts_val = 0
                                history_list.append({"id": k, "ts": ts_val})
                        else:
                            # fallback to line parse
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
                                    history_list.append({"id": pid, "ts": ts_val})
                                else:
                                    history_list.append({"id": line, "ts": 0})
                    except Exception:
                        # 旧行文本格式兼容
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
                                history_list.append({"id": pid, "ts": ts_val})
                            else:
                                history_list.append({"id": line, "ts": 0})

            # 去重并按时间戳降序排序
            tmp = {}
            for item in history_list:
                tmp[item["id"]] = int(item.get("ts", 0))
            history_list = [{"id": k, "ts": v} for k, v in tmp.items()]
            history_list.sort(key=lambda x: x["ts"], reverse=True)
            history_ids = [item["id"] for item in history_list]
        except Exception as e:
            messagebox.showerror("错误", f"读取历史记录失败: {e}", parent=self.root)
            return
            
        if not history_ids:
            messagebox.showinfo("提示", "历史记录为空", parent=self.root)
            return
            
        # 弹窗选择 ID 和 分组
        import_win = tk.Toplevel(self.root)
        import_win.title("从历史导入")
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        import_win.transient(self.root)
        import_win.grab_set()
        
        tk.Label(import_win, text="选择要导入的 ID (多选):").pack(pady=5)
        list_frame = tk.Frame(import_win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        id_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, exportselection=False)
        for hid in history_ids:
            id_listbox.insert(tk.END, hid)
        id_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=id_listbox.yview)
        
        group_frame = tk.Frame(import_win)
        group_frame.pack(fill=tk.X, pady=10, padx=10)
        tk.Label(group_frame, text="导入到分组:").pack(side=tk.LEFT)
        group_combo = ttk.Combobox(group_frame, values=sorted(self.data["groups"].keys()))
        group_combo.set("默认")
        group_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        def do_import():
            selection = id_listbox.curselection()
            target_group = group_combo.get().strip()
            
            if not selection:
                messagebox.showwarning("警告", "请至少选择一个 ID", parent=self.root)
                return
            if not target_group:
                messagebox.showwarning("警告", "请选择目标分组", parent=self.root)
                return
                
            if target_group not in self.data["groups"]:
                self.data["groups"][target_group] = []
                
            added_count = 0
            for idx in selection:
                pid = id_listbox.get(idx)
                if pid not in self.data["groups"][target_group]:
                    self.data["groups"][target_group].append(pid)
                    added_count += 1
            
            messagebox.showinfo("成功", f"成功导入 {added_count} 个 ID 到 '{target_group}'", parent=self.root)
            self.refresh_group_list() # 刷新列表
            import_win.destroy()
            
        tk.Button(import_win, text="确定导入", command=do_import, bg="green", fg="white", height=2).pack(fill=tk.X, padx=10, pady=10)
        # 调整窗口大小以适应内容并居中显示
        import_win.update_idletasks()
        w = max(440, import_win.winfo_width())
        h = max(500, import_win.winfo_height())
        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2))
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2))
        import_win.geometry(f"{w}x{h}+{x}+{y}")
        import_win.minsize(400, 420)

    def ask_selection(self, title, prompt, options):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text=prompt).pack(pady=10)
        combo = ttk.Combobox(dialog, values=options, state="readonly")
        if options: combo.current(0)
        combo.pack(fill=tk.X, padx=20)
        
        res = [None]
        def on_ok():
            res[0] = combo.get()
            dialog.destroy()
            
        tk.Button(dialog, text="确定", command=on_ok, width=10, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(pady=15)
        # 调整对话框大小并居中
        dialog.update_idletasks()
        w = max(340, dialog.winfo_width())
        h = max(160, dialog.winfo_height())
        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2))
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2))
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.minsize(320, 150)
        self.root.wait_window(dialog)
        return res[0]

    def ask_input(self, title, prompt, initialvalue=""):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text=prompt, font=("Arial", 9)).pack(pady=(12, 6), padx=15)
        entry = tk.Entry(dialog, font=("Arial", 10))
        entry.insert(0, initialvalue)
        entry.pack(fill=tk.X, padx=20)
        entry.focus_set()
        entry.bind("<Return>", lambda e: on_ok())
        
        res = [None]
        def on_ok():
            res[0] = entry.get().strip()
            dialog.destroy()
        
        tk.Button(dialog, text="确定", command=on_ok, width=10, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(pady=15)
        # 调整对话框大小并居中
        dialog.update_idletasks()
        w = max(340, dialog.winfo_width())
        h = max(160, dialog.winfo_height())
        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2))
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2))
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.minsize(320, 150)
        self.root.wait_window(dialog)
        return res[0]

    def save_changes(self):
        save_player_data(self.data)
        messagebox.showinfo("成功", "更改已保存到 player_list.json", parent=self.root)
        self.root.destroy()

    def open_confusable_manager(self):
        confusable_win = tk.Toplevel(self.root)
        from confusable_manager import ConfusableManager
        ConfusableManager(confusable_win)

if __name__ == "__main__":
    root = tk.Tk()
    app = ListManager(root)
    root.mainloop()
