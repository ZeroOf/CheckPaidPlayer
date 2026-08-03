# Warcraft III 玩家监测程序 使用说明

## 1. 程序简介
本程序通过 OCR（光学字符识别）技术实时监测 Warcraft III 游戏画面中的玩家列表，并在检测到目标玩家时发出声音提醒并弹出窗口。

## 2. 环境依赖
打包后的程序包含大部分依赖，但由于 OCR 引擎的特殊性，您需要手动安装以下外部组件：

### 2.1 Tesseract OCR 引擎（必须）
程序依赖 Tesseract OCR 进行文字识别。
1. **下载安装包**：从 [Tesseract OCR GitHub](https://github.com/UBERMANN/tesseract-windows-builds) 或 [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) 下载 Windows 安装包（推荐 5.0 及以上版本）。
2. **安装**：运行安装程序。在选择组件时，请务必勾选 **"Additional language data (download)"** 中的 **"Chinese (Simplified)"**，否则无法识别中文名。
3. **配置 PATH**：
   - 建议将安装目录（例如 `C:\Program Files\Tesseract-OCR`）添加到系统的 `PATH` 环境变量中。
   - 如果不想配置环境变量，可以右键编辑 `PlayerMonitor.exe` 同级目录下的代码配置文件（如果提供），或在源码中指定 `tesseract_cmd` 路径。

## 3. 使用方法
1. **准备名单**：在 `PlayerMonitor.exe` 同级目录下创建一个名为 `paid_player_id.txt` 的文本文件。
2. **编辑名单**：在文件中输入要监控的玩家 ID，每行一个。
3. **运行程序**：双击运行 `PlayerMonitor.exe`。
4. **游戏设置**：请确保游戏以**窗口模式**或**无边框窗口模式**运行，且分辨率与程序配置匹配（默认适配 3840x2160，若分辨率不同需调整监测区域）。

## 4. 文件结构
- `PlayerMonitor.exe`: 主程序
- `paid_player_id.txt`: 目标玩家名单文件
- `README.md`: 本说明文档

## 5. 注意事项
- 如果程序启动即报错提示找不到 Tesseract，请检查是否已正确安装并添加到 PATH。
- 程序默认运行 300 秒后自动退出，如需长期监控请修改源码配置重新打包。
