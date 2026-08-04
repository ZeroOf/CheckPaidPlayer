import tkinter as tk
from gui import MonitorApp
from utils import set_dpi_awareness

def main():
    # 设置 DPI 感知，使窗口支持系统缩放
    set_dpi_awareness()
    
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
