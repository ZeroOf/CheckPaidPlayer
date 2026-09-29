import os
import json
import copy
import re
import tkinter as tk
from tkinter import messagebox, ttk
import winsound
from config import DEFAULT_CONFUSABLE_CONFIG, load_confusable_config, save_confusable_config
from utils import set_dpi_awareness, extract_confusable_diffs


def add_confusable_entry(data, item_type, src, tgt=None):
    """
    向结构化混淆数据中添加/合并项目。
    data 格式: {"groups": [...], "mappings": {...}, "removals": [...]}
    """
    if "groups" not in data: data["groups"] = []
    if "mappings" not in data: data["mappings"] = {}
    if "removals" not in data: data["removals"] = []

    if item_type == "group":
        chars = []
        if isinstance(src, (list, tuple)):
            chars.extend(src)
        elif src:
            chars.append(src)
        if isinstance(tgt, (list, tuple)):
            chars.extend(tgt)
        elif tgt:
            chars.append(tgt)

        chars = [c.strip() for c in chars if c and c.strip()]
        if len(chars) < 2:
            return False

        matched_indices = []
        for idx, g in enumerate(data["groups"]):
            if any(c in g for c in chars):
                matched_indices.append(idx)

        if matched_indices:
            merged_group = []
            for idx in matched_indices:
                merged_group.extend(data["groups"][idx])
            merged_group.extend(chars)
            unique_group = list(dict.fromkeys(merged_group))

            first_idx = matched_indices[0]
            data["groups"][first_idx] = unique_group
            for idx in sorted(matched_indices[1:], reverse=True):
                data["groups"].pop(idx)
        else:
            data["groups"].append(list(dict.fromkeys(chars)))
        return True

    elif item_type == "mapping":
        src = src.strip() if isinstance(src, str) else src
        if not src:
            return False
        if src not in data["mappings"]:
            data["mappings"][src] = []

        reps = tgt if isinstance(tgt, (list, tuple)) else [tgt]
        for r in reps:
            r = r.strip() if isinstance(r, str) else r
            if r and r not in data["mappings"][src]:
                data["mappings"][src].append(r)
        return True

    elif item_type == "removal":
        rem_chars = src if isinstance(src, (list, tuple)) else [src]
        added = False
        for c in rem_chars:
            c = c.strip() if isinstance(c, str) else c
            if c and c not in data["removals"]:
                data["removals"].append(c)
                added = True
        return added

    return False


class ConfusableEditDialog:
    def __init__(self, parent, title="编辑混淆映射", item_type="group", initial_data=None):
        self.parent = parent
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        self.type_var = tk.StringVar(value=item_type)
        self.group_input_var = tk.StringVar()
        self.map_src_var = tk.StringVar()
        self.map_tgt_var = tk.StringVar()
        self.removal_var = tk.StringVar()

        # 填充初始数据
        if initial_data:
            if item_type == "group":
                self.group_input_var.set(", ".join(initial_data))
            elif item_type == "mapping":
                src, tgt_list = initial_data
                self.map_src_var.set(src)
                self.map_tgt_var.set(", ".join(tgt_list))
            elif item_type == "removal":
                self.removal_var.set(", ".join(initial_data) if isinstance(initial_data, list) else str(initial_data))

        self.setup_ui()

        self.dialog.update_idletasks()
        w = max(520, self.dialog.winfo_width())
        h = max(340, self.dialog.winfo_height())
        x = max(0, parent.winfo_x() + (parent.winfo_width() // 2) - (w // 2))
        y = max(0, parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2))
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")
        self.dialog.minsize(480, 320)
        self.dialog.focus_set()

    def setup_ui(self):
        pad_frame = tk.Frame(self.dialog, padx=16, pady=16)
        pad_frame.pack(fill=tk.BOTH, expand=True)

        # 类型选择单选框
        type_frame = tk.LabelFrame(pad_frame, text="混淆类型", font=("Arial", 9, "bold"), padx=10, pady=6)
        type_frame.pack(fill=tk.X, pady=(0, 12))

        types = [
            ("相互混淆组 (多个字符互相等价)", "group"),
            ("单向映射 (原字符/词 替换为 变体)", "mapping"),
            ("消除字符 (识别时直接忽略/删除)", "removal")
        ]
        for text, val in types:
            tk.Radiobutton(
                type_frame, text=text, value=val, variable=self.type_var,
                command=self.on_type_change, font=("Arial", 9)
            ).pack(anchor="w", pady=2)

        # 动态输入容器
        self.container = tk.Frame(pad_frame)
        self.container.pack(fill=tk.BOTH, expand=True)

        # 相互混淆组输入区
        self.frame_group = tk.Frame(self.container)
        tk.Label(self.frame_group, text="互混淆字符列表 (逗号或空格分隔):", anchor="w", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=(0, 4))
        self.entry_group = tk.Entry(self.frame_group, textvariable=self.group_input_var, font=("Arial", 10))
        self.entry_group.pack(fill=tk.X, pady=(0, 6))
        tk.Label(self.frame_group, text="示例: l, 1, I, i 或 涛, 寿 (组内所有字符均可互相替换)", fg="#666666", font=("Arial", 8)).pack(anchor="w")

        # 单向映射输入区
        self.frame_mapping = tk.Frame(self.container)
        tk.Label(self.frame_mapping, text="原字符 / 关键字:", anchor="w", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=(0, 2))
        self.entry_map_src = tk.Entry(self.frame_mapping, textvariable=self.map_src_var, font=("Arial", 10))
        self.entry_map_src.pack(fill=tk.X, pady=(0, 6))

        tk.Label(self.frame_mapping, text="替换变体列表 (逗号分隔):", anchor="w", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=(0, 2))
        self.entry_map_tgt = tk.Entry(self.frame_mapping, textvariable=self.map_tgt_var, font=("Arial", 10))
        self.entry_map_tgt.pack(fill=tk.X, pady=(0, 4))
        tk.Label(self.frame_mapping, text="示例: 原字符 'w' -> 变体 'vv, v v'", fg="#666666", font=("Arial", 8)).pack(anchor="w")

        # 消除字符输入区
        self.frame_removal = tk.Frame(self.container)
        tk.Label(self.frame_removal, text="消除字符列表 (逗号或空格分隔):", anchor="w", font=("Arial", 9, "bold")).pack(fill=tk.X, pady=(0, 4))
        self.entry_removal = tk.Entry(self.frame_removal, textvariable=self.removal_var, font=("Arial", 10))
        self.entry_removal.pack(fill=tk.X, pady=(0, 6))
        tk.Label(self.frame_removal, text="示例: 灬, 丶 (识别时包含这些字符会被自动消除以匹配)", fg="#666666", font=("Arial", 8)).pack(anchor="w")

        self.on_type_change()

        # 底部按钮区
        btn_frame = tk.Frame(pad_frame)
        btn_frame.pack(fill=tk.X, pady=(12, 0), side=tk.BOTTOM)
        tk.Button(btn_frame, text="确定", command=self.on_ok, width=10, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="取消", command=self.dialog.destroy, width=10, font=("Arial", 9)).pack(side=tk.RIGHT, padx=5)

    def on_type_change(self):
        t = self.type_var.get()
        self.frame_group.pack_forget()
        self.frame_mapping.pack_forget()
        self.frame_removal.pack_forget()

        if t == "group":
            self.frame_group.pack(fill=tk.BOTH, expand=True)
            self.entry_group.focus_set()
        elif t == "mapping":
            self.frame_mapping.pack(fill=tk.BOTH, expand=True)
            self.entry_map_src.focus_set()
        elif t == "removal":
            self.frame_removal.pack(fill=tk.BOTH, expand=True)
            self.entry_removal.focus_set()

    def parse_list(self, text):
        if not text:
            return []
        if ',' in text or '，' in text:
            raw = re.split(r'[,，]', text)
        else:
            tokens = text.split()
            raw = tokens if len(tokens) > 1 else [text]
        return [item.strip() for item in raw if item.strip()]

    def on_ok(self):
        t = self.type_var.get()
        if t == "group":
            items = self.parse_list(self.group_input_var.get())
            if len(items) < 2:
                messagebox.showwarning("提示", "相互混淆组至少需要输入 2 个字符！", parent=self.dialog)
                self.entry_group.focus_set()
                return
            # 去重
            unique_items = list(dict.fromkeys(items))
            self.result = ("group", unique_items)

        elif t == "mapping":
            src = self.map_src_var.get().strip()
            if not src:
                messagebox.showwarning("提示", "请输入原字符 / 关键字！", parent=self.dialog)
                self.entry_map_src.focus_set()
                return
            reps = self.parse_list(self.map_tgt_var.get())
            if not reps:
                messagebox.showwarning("提示", "请输入替换变体列表！", parent=self.dialog)
                self.entry_map_tgt.focus_set()
                return
            unique_reps = list(dict.fromkeys(reps))
            self.result = ("mapping", (src, unique_reps))

        elif t == "removal":
            items = self.parse_list(self.removal_var.get())
            if not items:
                messagebox.showwarning("提示", "请输入要消除的字符！", parent=self.dialog)
                self.entry_removal.focus_set()
                return
            unique_items = list(dict.fromkeys(items))
            self.result = ("removal", unique_items)

        self.dialog.destroy()


class UsernameDiffDialog:
    """
    用户名自动比对并添加混淆字段对话框
    """
    def __init__(self, parent, manager):
        self.parent = parent
        self.manager = manager
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("用户名智能对比添加混淆字段")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        self.u1_var = tk.StringVar()
        self.u2_var = tk.StringVar()
        self.diff_items = [] # list of dicts: {"checked": bool, "src": str, "tgt": str, "type": str}

        self.setup_ui()

        self.dialog.update_idletasks()
        w = max(660, self.dialog.winfo_width())
        h = max(520, self.dialog.winfo_height())
        x = max(0, parent.winfo_x() + (parent.winfo_width() // 2) - (w // 2))
        y = max(0, parent.winfo_y() + (parent.winfo_height() // 2) - (h // 2))
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")
        self.dialog.minsize(600, 480)
        self.dialog.focus_set()

    def setup_ui(self):
        main_pad = tk.Frame(self.dialog, padx=14, pady=12)
        main_pad.pack(fill=tk.BOTH, expand=True)

        # 顶部提示区
        tip_frame = tk.Frame(main_pad)
        tip_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            tip_frame,
            text="💡 输入两个用户名（例如真实用户名 vs 识别出的错误名字），系统将自动比对差异并提取混淆字段：",
            justify=tk.LEFT, fg="#333333", font=("Arial", 9)
        ).pack(anchor="w")

        # 用户名输入框
        input_box = tk.LabelFrame(main_pad, text="用户名比对输入", font=("Arial", 9, "bold"), padx=10, pady=8)
        input_box.pack(fill=tk.X, pady=(0, 10))

        # 用户名 1
        r1 = tk.Frame(input_box)
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="用户名 1 (正确/基准名字):", width=20, anchor="w", font=("Arial", 9)).pack(side=tk.LEFT)
        self.entry_u1 = tk.Entry(r1, textvariable=self.u1_var, font=("Arial", 10))
        self.entry_u1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_u1.bind("<KeyRelease>", lambda e: self.do_diff())

        # 用户名 2
        r2 = tk.Frame(input_box)
        r2.pack(fill=tk.X, pady=2)
        tk.Label(r2, text="用户名 2 (识别/混淆名字):", width=20, anchor="w", font=("Arial", 9)).pack(side=tk.LEFT)
        self.entry_u2 = tk.Entry(r2, textvariable=self.u2_var, font=("Arial", 10))
        self.entry_u2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_u2.bind("<KeyRelease>", lambda e: self.do_diff())

        btn_diff = tk.Button(input_box, text="🔍 开始比对", command=self.do_diff, bg="#e3f2fd", font=("Arial", 9, "bold"))
        btn_diff.pack(anchor="e", pady=(4, 0))

        # 比对结果展示列表
        result_box = tk.LabelFrame(main_pad, text="检测到的混淆字段差异", font=("Arial", 9, "bold"), padx=6, pady=6)
        result_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        table_frame = tk.Frame(result_box)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("checked", "src", "tgt", "type_desc", "action_desc")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("checked", text="选择", anchor="center")
        self.tree.heading("src", text="用户名1 字段", anchor="center")
        self.tree.heading("tgt", text="用户名2 字段", anchor="center")
        self.tree.heading("type_desc", text="混淆类型", anchor="center")
        self.tree.heading("action_desc", text="添加操作说明", anchor="w")

        self.tree.column("checked", width=50, minwidth=40, anchor="center")
        self.tree.column("src", width=100, minwidth=70, anchor="center")
        self.tree.column("tgt", width=100, minwidth=70, anchor="center")
        self.tree.column("type_desc", width=100, minwidth=80, anchor="center")
        self.tree.column("action_desc", width=180, minwidth=120, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<space>", lambda e: self.toggle_selected_row())

        # 表格下方快捷操作条
        tbl_actions = tk.Frame(result_box)
        tbl_actions.pack(fill=tk.X, pady=(6, 0))

        tk.Button(tbl_actions, text="全选", command=self.select_all, width=6, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(tbl_actions, text="全不选", command=self.deselect_all, width=6, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)

        tk.Label(tbl_actions, text="修改选中项类型:", font=("Arial", 8), fg="#666666").pack(side=tk.LEFT, padx=(10, 2))
        tk.Button(tbl_actions, text="设为相互混淆", command=lambda: self.set_selected_type("group"), font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(tbl_actions, text="设为单向映射", command=lambda: self.set_selected_type("mapping"), font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(tbl_actions, text="设为消除字符", command=lambda: self.set_selected_type("removal"), font=("Arial", 8)).pack(side=tk.LEFT, padx=2)

        # 底部操作栏
        bottom_frame = tk.Frame(main_pad)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_summary = tk.Label(bottom_frame, text="请输入用户名以对比", font=("Arial", 9), fg="#666666")
        self.lbl_summary.pack(side=tk.LEFT)

        tk.Button(bottom_frame, text="取消", command=self.dialog.destroy, width=9, font=("Arial", 9)).pack(side=tk.RIGHT, padx=4)
        tk.Button(bottom_frame, text="确认添加选中项", command=self.on_confirm, width=15, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=4)

    def do_diff(self):
        u1 = self.u1_var.get().strip()
        u2 = self.u2_var.get().strip()

        if not u1 or not u2:
            self.diff_items = []
            self.refresh_tree()
            self.lbl_summary.config(text="请输入两个用户名进行对比", fg="#666666")
            return

        if u1 == u2:
            self.diff_items = []
            self.refresh_tree()
            self.lbl_summary.config(text="两个用户名完全相同，无差异", fg="#4CAF50")
            return

        raw_diffs = extract_confusable_diffs(u1, u2)
        self.diff_items = []
        for src, tgt, item_type in raw_diffs:
            self.diff_items.append({
                "checked": True,
                "src": src,
                "tgt": tgt,
                "type": item_type
            })

        self.refresh_tree()
        self.lbl_summary.config(
            text=f"已检测到 {len(self.diff_items)} 处混淆字段差异，点击每行可切换勾选状态",
            fg="#1976D2" if self.diff_items else "#666666"
        )

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self.diff_items):
            chk_symbol = "✔" if item["checked"] else "☐"
            src = item["src"]
            tgt = item["tgt"]
            t = item["type"]

            if t == "group":
                type_desc = "相互混淆组"
                action_desc = f"'{src}' 与 '{tgt}' 互相替换"
            elif t == "mapping":
                type_desc = "单向映射"
                action_desc = f"'{src}' 替换为 '{tgt}'"
            elif t == "removal":
                type_desc = "消除字符"
                char = src if src else tgt
                action_desc = f"直接消除/忽略字符 '{char}'"
            else:
                type_desc = "未知"
                action_desc = "-"

            tgt_display = tgt if tgt else "<空>"
            src_display = src if src else "<空>"

            self.tree.insert("", tk.END, iid=str(idx), values=(chk_symbol, src_display, tgt_display, type_desc, action_desc))

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            item_id = self.tree.identify_row(event.y)
            if item_id:
                idx = int(item_id)
                self.diff_items[idx]["checked"] = not self.diff_items[idx]["checked"]
                self.refresh_tree()
                self.tree.selection_set(item_id)

    def toggle_selected_row(self):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            self.diff_items[idx]["checked"] = not self.diff_items[idx]["checked"]
            self.refresh_tree()
            self.tree.selection_set(selected[0])

    def select_all(self):
        for item in self.diff_items:
            item["checked"] = True
        self.refresh_tree()

    def deselect_all(self):
        for item in self.diff_items:
            item["checked"] = False
        self.refresh_tree()

    def set_selected_type(self, new_type):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在表格中选择一项差异！", parent=self.dialog)
            return
        idx = int(selected[0])
        self.diff_items[idx]["type"] = new_type
        self.refresh_tree()
        self.tree.selection_set(selected[0])

    def on_confirm(self):
        selected_items = [it for it in self.diff_items if it["checked"]]
        if not selected_items:
            messagebox.showwarning("提示", "请至少勾选一项要添加的混淆字段！", parent=self.dialog)
            return

        added_count = 0
        for it in selected_items:
            t = it["type"]
            src = it["src"]
            tgt = it["tgt"]
            if t == "group":
                if src and tgt:
                    if add_confusable_entry(self.manager.data, "group", src, tgt):
                        added_count += 1
            elif t == "mapping":
                if src and tgt:
                    if add_confusable_entry(self.manager.data, "mapping", src, tgt):
                        added_count += 1
            elif t == "removal":
                char = src if src else tgt
                if char:
                    if add_confusable_entry(self.manager.data, "removal", char):
                        added_count += 1

        self.manager.refresh_table()
        messagebox.showinfo("添加成功", f"已成功添加/合并 {added_count} 项混淆映射到混淆表中！\n请记得点击【保存更改】使其生效。", parent=self.manager.root)
        self.dialog.destroy()


class ConfusableManager:
    def __init__(self, root):
        self.root = root
        self.root.title("混淆字符表管理")
        self.root.geometry("840x580")
        self.root.minsize(780, 500)

        set_dpi_awareness()

        # 加载结构化配置
        self.data = copy.deepcopy(load_confusable_config())
        self.initial_data = copy.deepcopy(self.data)

        self.setup_ui()
        self.refresh_table()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def setup_ui(self):
        # 顶部搜索栏与类型过滤
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Label(top_frame, text="搜索:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(top_frame, font=("Arial", 9))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.search_entry.bind("<KeyRelease>", self.on_search)

        tk.Button(top_frame, text="清空", command=self.clear_search, width=5, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)

        tk.Label(top_frame, text="类型过滤:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(8, 2))
        self.filter_type_var = tk.StringVar(value="全部")
        self.filter_combo = ttk.Combobox(top_frame, textvariable=self.filter_type_var, values=["全部", "相互混淆组", "单向映射", "消除字符"], state="readonly", width=10)
        self.filter_combo.pack(side=tk.LEFT, padx=2)
        self.filter_combo.bind("<<ComboboxSelected>>", self.on_search)

        self.lbl_count = tk.Label(top_frame, text="共 0 项", font=("Arial", 9), fg="#666666")
        self.lbl_count.pack(side=tk.RIGHT, padx=5)

        # 中间表格和操作按钮区
        main_frame = tk.Frame(self.root, padx=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        table_frame = tk.Frame(main_frame)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("category", "source", "target", "count")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("category", text="类型", command=lambda: self.sort_column("category", False))
        self.tree.heading("source", text="关键字符 / 原词", command=lambda: self.sort_column("source", False))
        self.tree.heading("target", text="替换变体 / 成员列表", command=lambda: self.sort_column("target", False))
        self.tree.heading("count", text="变体数", command=lambda: self.sort_column("count", False))

        self.tree.column("category", width=100, minwidth=80, anchor="center")
        self.tree.column("source", width=140, minwidth=90, anchor="center")
        self.tree.column("target", width=330, minwidth=180, anchor="w")
        self.tree.column("count", width=70, minwidth=50, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", lambda e: self.edit_mapping())
        self.tree.bind("<Delete>", lambda e: self.delete_mapping())
        self.tree.bind("<Return>", lambda e: self.edit_mapping())

        # 右侧操作按钮栏
        btn_side_frame = tk.Frame(main_frame, padx=10)
        btn_side_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Button(btn_side_frame, text="新增混淆", command=self.add_mapping, width=17, height=1, bg="#e3f2fd", font=("Arial", 9)).pack(pady=4)
        tk.Button(btn_side_frame, text="🔍 用户名对比添加", command=self.open_diff_dialog, width=17, height=1, bg="#e8f5e9", fg="#2e7d32", font=("Arial", 9, "bold")).pack(pady=4)
        tk.Button(btn_side_frame, text="编辑选中项", command=self.edit_mapping, width=17, height=1, font=("Arial", 9)).pack(pady=4)
        tk.Button(btn_side_frame, text="删除选中项", command=self.delete_mapping, width=17, height=1, fg="#c62828", font=("Arial", 9)).pack(pady=4)

        tk.Frame(btn_side_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=12)

        tk.Button(btn_side_frame, text="恢复默认", command=self.reset_default, width=17, height=1, font=("Arial", 9)).pack(pady=4)

        # 底部操作栏
        bottom_frame = tk.Frame(self.root, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        lbl_tip = tk.Label(bottom_frame, text="💡 双击行可快速编辑，支持通过【用户名对比添加】自动识别混淆字段", fg="#888888", font=("Arial", 9))
        lbl_tip.pack(side=tk.LEFT)

        tk.Button(bottom_frame, text="取消", command=self.on_closing, width=10, font=("Arial", 9)).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom_frame, text="保存更改", command=self.save_changes, width=12, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=5)

    def refresh_table(self, filter_text=None, filter_type=None):
        if filter_text is None:
            filter_text = self.search_entry.get().strip().lower()
        if filter_type is None:
            filter_type = self.filter_type_var.get()

        self.tree.delete(*self.tree.get_children())

        # 遍历解析数据项
        items_to_display = []

        # 1. 相互混淆组
        for idx, group in enumerate(self.data.get("groups", [])):
            if not group: continue
            cat = "相互混淆组"
            src = ", ".join(group)
            tgt = f"互相等价替换 ({len(group)} 个字符)"
            count = len(group)
            iid = f"group_{idx}"
            items_to_display.append((iid, cat, src, tgt, count, group))

        # 2. 单向映射
        for k, v in self.data.get("mappings", {}).items():
            if not k: continue
            cat = "单向映射"
            src = k
            reps = v if isinstance(v, list) else [v]
            tgt = ", ".join(reps)
            count = len(reps)
            iid = f"mapping_{k}"
            items_to_display.append((iid, cat, src, tgt, count, (k, reps)))

        # 3. 消除字符
        for idx, char in enumerate(self.data.get("removals", [])):
            if not char: continue
            cat = "消除字符"
            src = char
            tgt = "(直接忽略/消除)"
            count = 1
            iid = f"removal_{idx}"
            items_to_display.append((iid, cat, src, tgt, count, char))

        display_count = 0
        for iid, cat, src, tgt, count, _ in items_to_display:
            if filter_type != "全部" and cat != filter_type:
                continue
            if filter_text:
                if filter_text not in cat.lower() and filter_text not in src.lower() and filter_text not in tgt.lower():
                    continue
            self.tree.insert("", tk.END, iid=iid, values=(cat, src, tgt, count))
            display_count += 1

        g_len = len(self.data.get("groups", []))
        m_len = len(self.data.get("mappings", {}))
        r_len = len(self.data.get("removals", []))
        self.lbl_count.config(text=f"共 {display_count} / {g_len + m_len + r_len} 项 (组:{g_len}, 映射:{m_len}, 消除:{r_len})")

    def on_search(self, event=None):
        self.refresh_table(self.search_entry.get().strip().lower(), self.filter_type_var.get())

    def clear_search(self):
        self.search_entry.delete(0, tk.END)
        self.filter_type_var.set("全部")
        self.refresh_table()

    def sort_column(self, col, reverse):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        if col == "count":
            def parse_num(val):
                try: return int(val)
                except: return 0
            items.sort(key=lambda t: parse_num(t[0]), reverse=reverse)
        else:
            items.sort(reverse=reverse)

        for index, (val, k) in enumerate(items):
            self.tree.move(k, "", index)

        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def open_diff_dialog(self):
        UsernameDiffDialog(self.root, self)

    def add_mapping(self):
        dlg = ConfusableEditDialog(self.root, title="新增混淆映射")
        self.root.wait_window(dlg.dialog)
        if dlg.result:
            item_type, val = dlg.result
            if item_type == "group":
                add_confusable_entry(self.data, "group", val)
            elif item_type == "mapping":
                src, reps = val
                add_confusable_entry(self.data, "mapping", src, reps)
            elif item_type == "removal":
                add_confusable_entry(self.data, "removal", val)
            self.refresh_table()

    def edit_mapping(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要编辑的混淆项！", parent=self.root)
            return

        iid = selected[0]
        if iid.startswith("group_"):
            idx = int(iid.split("_", 1)[1])
            if idx < len(self.data.get("groups", [])):
                curr_group = self.data["groups"][idx]
                dlg = ConfusableEditDialog(self.root, title="编辑相互混淆组", item_type="group", initial_data=curr_group)
                self.root.wait_window(dlg.dialog)
                if dlg.result:
                    item_type, val = dlg.result
                    self.data["groups"].pop(idx)
                    if item_type == "group":
                        add_confusable_entry(self.data, "group", val)
                    elif item_type == "mapping":
                        src, reps = val
                        add_confusable_entry(self.data, "mapping", src, reps)
                    elif item_type == "removal":
                        add_confusable_entry(self.data, "removal", val)
                    self.refresh_table()

        elif iid.startswith("mapping_"):
            key = iid.split("_", 1)[1]
            if key in self.data.get("mappings", {}):
                curr_reps = self.data["mappings"][key]
                dlg = ConfusableEditDialog(self.root, title=f"编辑单向映射 '{key}'", item_type="mapping", initial_data=(key, curr_reps))
                self.root.wait_window(dlg.dialog)
                if dlg.result:
                    item_type, val = dlg.result
                    del self.data["mappings"][key]
                    if item_type == "group":
                        add_confusable_entry(self.data, "group", val)
                    elif item_type == "mapping":
                        src, reps = val
                        add_confusable_entry(self.data, "mapping", src, reps)
                    elif item_type == "removal":
                        add_confusable_entry(self.data, "removal", val)
                    self.refresh_table()

        elif iid.startswith("removal_"):
            idx = int(iid.split("_", 1)[1])
            if idx < len(self.data.get("removals", [])):
                curr_char = self.data["removals"][idx]
                dlg = ConfusableEditDialog(self.root, title=f"编辑消除字符 '{curr_char}'", item_type="removal", initial_data=curr_char)
                self.root.wait_window(dlg.dialog)
                if dlg.result:
                    item_type, val = dlg.result
                    self.data["removals"].pop(idx)
                    if item_type == "group":
                        add_confusable_entry(self.data, "group", val)
                    elif item_type == "mapping":
                        src, reps = val
                        add_confusable_entry(self.data, "mapping", src, reps)
                    elif item_type == "removal":
                        add_confusable_entry(self.data, "removal", val)
                    self.refresh_table()

    def delete_mapping(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的混淆项！", parent=self.root)
            return

        iid = selected[0]
        if iid.startswith("group_"):
            idx = int(iid.split("_", 1)[1])
            if idx < len(self.data.get("groups", [])):
                g = self.data["groups"][idx]
                if messagebox.askyesno("确认删除", f"确定要删除相互混淆组 {g} 吗？", parent=self.root):
                    self.data["groups"].pop(idx)
                    self.refresh_table()

        elif iid.startswith("mapping_"):
            key = iid.split("_", 1)[1]
            if key in self.data.get("mappings", {}):
                if messagebox.askyesno("确认删除", f"确定要删除单向映射 '{key}' 吗？", parent=self.root):
                    del self.data["mappings"][key]
                    self.refresh_table()

        elif iid.startswith("removal_"):
            idx = int(iid.split("_", 1)[1])
            if idx < len(self.data.get("removals", [])):
                c = self.data["removals"][idx]
                if messagebox.askyesno("确认删除", f"确定要删除消除字符 '{c}' 吗？", parent=self.root):
                    self.data["removals"].pop(idx)
                    self.refresh_table()

    def reset_default(self):
        if messagebox.askyesno("恢复默认", "确定要将混淆字符表恢复为系统默认配置吗？\n当前未保存的自定义修改将被重置。", parent=self.root):
            self.data = copy.deepcopy(DEFAULT_CONFUSABLE_CONFIG)
            self.refresh_table()
            messagebox.showinfo("提示", "已恢复为默认配置，请点击【保存更改】使其生效。", parent=self.root)

    def save_changes(self):
        try:
            save_confusable_config(self.data)
            self.initial_data = copy.deepcopy(self.data)
            messagebox.showinfo("成功", "混淆字符表已成功保存并即时生效！", parent=self.root)
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存混淆字符表失败: {e}", parent=self.root)

    def on_closing(self):
        if self.data != self.initial_data:
            res = messagebox.askyesnocancel("提示", "检测到混淆字符表有未保存的修改，是否在关闭前保存？", parent=self.root)
            if res is True:
                self.save_changes()
            elif res is False:
                self.root.destroy()
            else:
                return
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ConfusableManager(root)
    root.mainloop()
