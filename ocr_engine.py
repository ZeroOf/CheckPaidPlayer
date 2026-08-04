import easyocr
from utils import get_resource_path

class OCREngine:
    def __init__(self):
        self.use_gpu = False
        self.reader = None
        self._check_gpu()
        self._load_model()

    def _check_gpu(self):
        print("正在检查 GPU 状态...")
        try:
            import torch
            self.use_gpu = torch.cuda.is_available()
            if self.use_gpu:
                print(f"检测到 GPU: {torch.cuda.get_device_name(0)}")
            else:
                print("未检测到可用 GPU，将使用 CPU 模式 (识别速度较慢)")
                print("提示: 如果您有 NVIDIA 显卡，请安装 GPU 版 PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cu118")
        except ImportError:
            self.use_gpu = False
            print("无法导入 torch，尝试使用默认配置")

    def _load_model(self):
        print("正在加载 EasyOCR 模型...")
        model_storage_path = get_resource_path("easyocr_models")
        self.reader = easyocr.Reader(['ch_sim', 'en'], gpu=self.use_gpu, model_storage_directory=model_storage_path) 
        print("模型加载完成！\n")

    def read_text(self, img_np):
        """ 识别图片中的文字 """
        if self.reader:
            return self.reader.readtext(img_np, detail=0, paragraph=False)
        return []

# 全局单例
engine = OCREngine()
