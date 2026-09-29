import sys
import tkinter as tk
from gui import MonitorApp
from utils import set_dpi_awareness, SingleInstance, activate_existing_window

def main():
    single_instance = SingleInstance()
    if not single_instance.check():
        activate_existing_window("Warcraft III 玩家监测")
        sys.exit(0)

    # 设置 DPI 感知，使窗口支持系统缩放
    set_dpi_awareness()
    
    root = tk.Tk()
    app = MonitorApp(root)
    try:
        root.mainloop()
    finally:
        single_instance.close()

if __name__ == "__main__":
    main()
