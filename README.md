# Subtitle Translation Pipeline

Tool dịch phụ đề SRT hàng loạt cho phim bộ, drama dài tập bằng AI (Gemini, GPT, DeepSeek...), có giao diện đồ họa (PyQt5).

---

## 📦 Cài đặt

### 1. Yêu cầu hệ thống
- Python 3.8 trở lên
- Hệ điều hành: Windows, macOS hoặc Linux
### 2. Cài đặt thư viện
```bash
git clone https://github.com/<your-username>/llm-subtitle-pipeline.git
cd llm-subtitle-pipeline
# Khởi tạo môi trường ảo (khuyên dùng)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
# Cài đặt dependencies
pip install -r requirements.txt

pip install PyQt5 pysrt requests pyqtspinner
